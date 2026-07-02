#!/usr/bin/env python3
# measure_throughput_v2.py — 검증 재측정
# 의심 포인트 4종 점검:
#   (A) generation 길이별 (50/100/200/400/800/1200) — ramp-up 영향
#   (B) 동시 요청 (1/2/4) — 다중 사용자 시 per-user throughput
#   (C) TTFT (time to first token) — stream API
#   (D) prompt eval 신뢰도 — 무시해도 되는지

import json
import time
import urllib.request
import statistics
import threading
from datetime import datetime
import os

OLLAMA = "http://127.0.0.1:11434"
MODEL = "gemma4:26b"
OUT = "$HOME/project/reports/phase3/throughput_a6000_v2.json"

PROMPT = ("사내 호텔 예약 시스템을 Python Flask로 만들 때 핵심 라이브러리 3개와 "
          "그 이유를 단계별로 설명해줘. 보안·확장성·유지보수성 측면도 짚어줘.")


def call(prompt: str, num_predict: int) -> dict:
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"num_predict": num_predict, "temperature": 0.0},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate", data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read())
    wall = time.time() - t0
    return {
        "wall_s": round(wall, 3),
        "eval_count": data.get("eval_count", 0),
        "eval_duration_ns": data.get("eval_duration", 0),
        "prompt_eval_count": data.get("prompt_eval_count", 0),
        "prompt_eval_duration_ns": data.get("prompt_eval_duration", 0),
        "load_duration_ns": data.get("load_duration", 0),
        "total_duration_ns": data.get("total_duration", 0),
        "tok_per_sec": round(
            data["eval_count"] / (data["eval_duration"] / 1e9), 2
        ) if data.get("eval_duration") else 0,
    }


def call_stream_ttft(prompt: str, num_predict: int) -> dict:
    """stream=True로 첫 토큰까지 시간 측정"""
    body = json.dumps({
        "model": MODEL, "prompt": prompt, "stream": True,
        "options": {"num_predict": num_predict, "temperature": 0.0},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate", data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    ttft = None
    final = None
    with urllib.request.urlopen(req, timeout=600) as r:
        for line in r:
            if not line.strip():
                continue
            chunk = json.loads(line)
            # 첫 응답 chunk 도착 시점 = TTFT (response 비어있어도 chunk 받은 거)
            if ttft is None:
                ttft = time.time() - t0
            if chunk.get("done"):
                final = chunk
                break
    wall = time.time() - t0
    return {
        "ttft_s": round(ttft, 3) if ttft else None,
        "wall_s": round(wall, 3),
        "eval_count": final.get("eval_count", 0) if final else 0,
        "tok_per_sec": round(
            final["eval_count"] / (final["eval_duration"] / 1e9), 2
        ) if final and final.get("eval_duration") else 0,
    }


def concurrent_run(prompt: str, num_predict: int, n_concurrent: int) -> dict:
    """n_concurrent개 요청 동시 발사, 각자의 tok/s와 wall 측정"""
    results = [None] * n_concurrent
    def worker(idx):
        results[idx] = call(prompt, num_predict)
    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_concurrent)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_wall = time.time() - t0
    per_user_tok = [r["tok_per_sec"] for r in results]
    return {
        "n_concurrent": n_concurrent,
        "total_wall_s": round(total_wall, 3),
        "per_request_tok_per_sec_mean": round(statistics.mean(per_user_tok), 2),
        "per_request_tok_per_sec_min": round(min(per_user_tok), 2),
        "per_request_tok_per_sec_max": round(max(per_user_tok), 2),
        "aggregate_tok_per_sec": round(
            sum(r["eval_count"] for r in results) / total_wall, 2
        ),
        "runs": results,
    }


def main():
    print(f"# v2 measure {datetime.now().isoformat()}")
    out = {"model": MODEL, "host": "KNU A6000",
           "timestamp": datetime.now().isoformat()}

    # warmup
    print("warmup ...")
    call(PROMPT, 50)

    # A) generation 길이별 (각 길이당 3회 평균)
    print("\n=== A) generation length sweep ===")
    out["length_sweep"] = {}
    for L in [50, 100, 200, 400, 800, 1200]:
        runs = []
        for _ in range(3):
            runs.append(call(PROMPT, L))
        toks = [r["tok_per_sec"] for r in runs]
        out["length_sweep"][L] = {
            "tok_per_sec_mean": round(statistics.mean(toks), 2),
            "tok_per_sec_stdev": round(statistics.stdev(toks), 2) if len(toks) > 1 else 0,
            "actual_eval_counts": [r["eval_count"] for r in runs],
            "runs": runs,
        }
        s = out["length_sweep"][L]
        print(f"  num_predict={L:>5}: mean={s['tok_per_sec_mean']:>6} "
              f"stdev={s['tok_per_sec_stdev']:>5} eval_counts={s['actual_eval_counts']}")

    # B) 동시 요청 — 각 nc 측정 직전 warmup 1회
    print("\n=== B) concurrent requests (with pre-warmup) ===")
    out["concurrent"] = {}
    for nc in [1, 2, 4]:
        call(PROMPT, 50)  # pre-warmup to flush load_duration
        r = concurrent_run(PROMPT, 200, nc)
        out["concurrent"][nc] = r
        print(f"  n={nc}: per_req={r['per_request_tok_per_sec_mean']:>6} "
              f"(min {r['per_request_tok_per_sec_min']}, max {r['per_request_tok_per_sec_max']}) "
              f"aggregate={r['aggregate_tok_per_sec']} tok/s  wall={r['total_wall_s']}s")

    # C) TTFT (3회)
    print("\n=== C) TTFT (time to first token) ===")
    ttfts = []
    for _ in range(3):
        r = call_stream_ttft(PROMPT, 100)
        ttfts.append(r)
        print(f"  ttft={r['ttft_s']}s  total_wall={r['wall_s']}s  tok/s={r['tok_per_sec']}")
    ttft_vals = [t["ttft_s"] for t in ttfts if t["ttft_s"] is not None]
    out["ttft"] = {
        "mean_s": round(statistics.mean(ttft_vals), 3) if ttft_vals else None,
        "stdev_s": round(statistics.stdev(ttft_vals), 3) if len(ttft_vals) > 1 else 0,
        "runs": ttfts,
    }

    # D) prompt eval 노이즈 확인 — 동일 prompt 5회
    print("\n=== D) prompt eval noise check ===")
    pe_vals = []
    for _ in range(5):
        r = call(PROMPT, 50)
        if r["prompt_eval_duration_ns"] > 0:
            pe = r["prompt_eval_count"] / (r["prompt_eval_duration_ns"] / 1e9)
            pe_vals.append(round(pe, 2))
    out["prompt_eval_noise"] = {
        "values": pe_vals,
        "min": min(pe_vals), "max": max(pe_vals),
        "ratio_max_over_min": round(max(pe_vals) / min(pe_vals), 2) if pe_vals else 0,
    }
    print(f"  prompt_tok_per_sec values: {pe_vals}")
    print(f"  ratio max/min = {out['prompt_eval_noise']['ratio_max_over_min']}x "
          f"(>2x = nanosecond 측정 노이즈)")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
