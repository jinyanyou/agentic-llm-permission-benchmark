#!/usr/bin/env python3
# measure_throughput.py — gemma4:26b on KNU A6000 token/sec 실측
# 멘토 5차 피드백 #12 대응

import json
import time
import urllib.request
import statistics
from datetime import datetime

OLLAMA = "http://127.0.0.1:11434"
MODEL = "gemma4:26b"
OUT = "$HOME/project/reports/phase3/throughput_a6000.json"

PROMPTS = {
    "short_qa":
        "사내 호텔 예약 시스템을 Python Flask로 만들 때 핵심 라이브러리 3개와 그 이유를 설명해줘.",
    "medium_summary":
        ("아래 회의록을 3줄 요약하고, 다음 회의 안건 2개를 한국어로 제안해줘.\n\n"
         "회의록: 오늘 사내 AI 에이전트 도입 관련 보안 검토를 진행했다. "
         "기획팀은 신규 채용 프로세스 자동화를 요청했고, 보안팀은 직원 정보 접근 권한이 "
         "에이전트에게 자동 부여되는 점을 우려했다. 결정 사항으로 (1) 가짜 데이터로 PoC "
         "선행, (2) 직급별 권한 분리 검토, (3) 외부 API 사용 금지, 두 환경(OpenClaw, "
         "NemoClaw) 비교 실험을 6/7까지 마무리하기로 했다."),
    "long_code":
        ("Python Flask + SQLite로 사내 호텔 예약 시스템 백엔드를 작성해줘. "
         "요구사항: 1) /reserve POST (예약자명·사번·체크인·체크아웃) 2) /list GET "
         "3) 사번 FAKE_ 접두사 검증 4) 체크인<체크아웃 검증 5) 한국어 에러 메시지. "
         "전체 app.py 코드와 간단한 사용 설명을 함께 작성해."),
}

NUM_PREDICT = 400      # 본 측정 토큰 수
NUM_REPS = 5           # 프롬프트당 반복


def call(prompt: str, num_predict: int) -> dict:
    body = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": 0.0},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read())
    wall = time.time() - t0
    eval_count = data.get("eval_count", 0)
    eval_dur_ns = data.get("eval_duration", 0)
    prompt_count = data.get("prompt_eval_count", 0)
    prompt_dur_ns = data.get("prompt_eval_duration", 0)
    tok_per_sec = eval_count / (eval_dur_ns / 1e9) if eval_dur_ns else 0.0
    prompt_tok_per_sec = (
        prompt_count / (prompt_dur_ns / 1e9) if prompt_dur_ns else 0.0
    )
    return {
        "wall_s": round(wall, 3),
        "prompt_tokens": prompt_count,
        "prompt_tok_per_sec": round(prompt_tok_per_sec, 2),
        "eval_tokens": eval_count,
        "tok_per_sec": round(tok_per_sec, 2),
    }


def main():
    print(f"# throughput measure {datetime.now().isoformat()}")
    # warmup (cold start 토큰 제외)
    print("warmup ...")
    w = call("안녕", 50)
    print(f"  warmup tok/s = {w['tok_per_sec']}")

    results = {"model": MODEL, "host": "KNU A6000",
               "timestamp": datetime.now().isoformat(),
               "num_predict": NUM_PREDICT, "reps": NUM_REPS,
               "warmup": w, "runs": {}}

    for name, prompt in PROMPTS.items():
        print(f"\n=== {name} ===")
        runs = []
        for i in range(NUM_REPS):
            r = call(prompt, NUM_PREDICT)
            print(f"  rep{i+1}: eval={r['eval_tokens']:>4}  "
                  f"tok/s={r['tok_per_sec']:>6}  wall={r['wall_s']}s")
            runs.append(r)
        toks = [r["tok_per_sec"] for r in runs]
        ptoks = [r["prompt_tok_per_sec"] for r in runs if r["prompt_tok_per_sec"] > 0]
        summary = {
            "runs": runs,
            "tok_per_sec_mean": round(statistics.mean(toks), 2),
            "tok_per_sec_stdev": round(statistics.stdev(toks), 2) if len(toks) > 1 else 0,
            "tok_per_sec_min": round(min(toks), 2),
            "tok_per_sec_max": round(max(toks), 2),
            "prompt_tok_per_sec_mean": round(statistics.mean(ptoks), 2) if ptoks else 0,
        }
        results["runs"][name] = summary
        print(f"  -> mean={summary['tok_per_sec_mean']} stdev={summary['tok_per_sec_stdev']}")

    # 전체 평균 (eval만)
    all_tok = []
    for s in results["runs"].values():
        all_tok.extend([r["tok_per_sec"] for r in s["runs"]])
    results["overall"] = {
        "tok_per_sec_mean": round(statistics.mean(all_tok), 2),
        "tok_per_sec_stdev": round(statistics.stdev(all_tok), 2),
        "tok_per_sec_min": round(min(all_tok), 2),
        "tok_per_sec_max": round(max(all_tok), 2),
        "n_total": len(all_tok),
    }
    print(f"\nOVERALL eval tok/s: mean={results['overall']['tok_per_sec_mean']} "
          f"stdev={results['overall']['tok_per_sec_stdev']} (n={results['overall']['n_total']})")

    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
