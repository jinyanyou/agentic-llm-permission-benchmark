#!/usr/bin/env python3
# plot_gpu_cost_throughput.py — 멘토 5차 #15: 비용-throughput 그래프
#
# - A6000 + gemma4:26b Q4_K_M = 101 tok/s (KNU 실측, n=15, stdev 0.84)
# - 타 GPU는 메모리 대역폭 비례 모델로 추정 (LLM inference는 memory-bound)
# - 가격: 2026.6 한국 시장가 기준. 소비자급(4060Ti~5090,A6000)은 다나와/중고 시세
#   실확인, 데이터센터급(L4·L40·RTX6000Ada·A100·H100)은 병행수입가 추정(변동 큼).

import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "Apple SD Gothic Neo"
plt.rcParams["axes.unicode_minus"] = False

A6000_MEASURED = 101.02      # tok/s (KNU 실측)
A6000_BW = 768               # GB/s (메모리 대역폭)
TOK_PER_BW = A6000_MEASURED / A6000_BW   # ≈ 0.1315 tok/s/(GB/s)

# 가격 기준일 (한국 시장가)
PRICE_DATE = "2026-06"
PRICE_SOURCE = ("소비자급: 다나와 최저가/중고 시세(2026.6) 실확인 · "
                "데이터센터급: 병행수입가 추정(변동 큼)")

GPUS = [
    # name, vram_gb, mem_bw_gb_s, price_man_won, kind ("measured"|"estimated"), note
    ("RTX 4060 Ti 16GB", 16, 288,  60, "estimated", "엔트리 (VRAM 빠듯)"),
    ("RTX 4070 Ti Super 16GB", 16, 672, 120, "estimated", "엔트리"),
    ("RTX 3090 24GB",   24, 936, 110, "estimated", "중고, best value"),
    ("RTX 4090 24GB",   24, 1008, 350, "estimated", "소비자 최상(단종)"),
    ("RTX 5090 32GB",   32, 1792, 620, "estimated", "현세대 최상"),
    ("L4 24GB",         24, 300, 350, "estimated", "데이터센터 입문"),
    ("RTX 6000 Ada 48GB", 48, 960, 1100, "estimated", "워크스테이션"),
    ("L40 48GB",        48, 864, 1300, "estimated", "서버용"),
    ("A100 40GB",       40, 1555, 1500, "estimated", "데이터센터 표준"),
    ("A100 80GB",       80, 2039, 3500, "estimated", "데이터센터 LL"),
    ("H100 PCIe 80GB",  80, 2000, 4500, "estimated", "최신 PCIe"),
    ("H100 SXM 80GB",   80, 3350, 6500, "estimated", "최신 SXM"),
]
# 실측치 A6000 삽입 (가격은 국내 유통가 ~700만 추정)
A6000 = ("RTX A6000 48GB", 48, 768, 700, "measured", "KNU 실측")

# 추정 함수
def estimate_tok_s(bw_gb_s: float) -> float:
    return round(bw_gb_s * TOK_PER_BW, 1)

rows = []
for name, vram, bw, price, kind, note in GPUS:
    rows.append({
        "name": name, "vram_gb": vram, "mem_bw": bw,
        "price_man_won": price, "kind": kind,
        "tok_per_sec": estimate_tok_s(bw), "note": note,
    })
# A6000 실측치 삽입
rows.append({
    "name": A6000[0], "vram_gb": A6000[1], "mem_bw": A6000[2],
    "price_man_won": A6000[3], "kind": "measured",
    "tok_per_sec": A6000_MEASURED, "note": A6000[5],
})
# 정렬: 가격순
rows.sort(key=lambda r: r["price_man_won"])

# --- 1) Scatter: 가격 vs throughput
fig, ax = plt.subplots(figsize=(11, 6.5))
for r in rows:
    color = "#d62728" if r["kind"] == "measured" else "#1f77b4"
    marker = "*" if r["kind"] == "measured" else "o"
    size = 380 if r["kind"] == "measured" else 110
    ax.scatter(r["price_man_won"], r["tok_per_sec"],
               c=color, marker=marker, s=size, zorder=3,
               edgecolor="black", linewidth=1)
    # label
    dy = 12 if r["kind"] == "measured" else 8
    ax.annotate(r["name"],
                (r["price_man_won"], r["tok_per_sec"]),
                xytext=(8, dy), textcoords="offset points",
                fontsize=8.5, ha="left")

ax.set_xscale("log")
ax.set_xlabel("GPU 가격 (만원, 2026 한국 시장가 추정, log scale)", fontsize=11)
ax.set_ylabel("gemma4:26b Q4_K_M throughput (tok/s)", fontsize=11)
ax.set_title("사내 LLM 추론 GPU 선택 — 비용 vs 처리량\n"
             "(★ = KNU A6000 실측 101 tok/s, ● = 메모리 대역폭 비례 추정)",
             fontsize=12)
ax.grid(True, which="both", alpha=0.3, linestyle="--")
ax.axhline(y=A6000_MEASURED, color="#d62728", linestyle=":", alpha=0.5)
ax.text(60, A6000_MEASURED + 4, "A6000 실측 = 101 tok/s",
        color="#d62728", fontsize=9, fontweight="bold")

# Cost Efficiency 가이드라인 (tok/s / 만원)
ax.text(0.02, 0.98,
        "메모리-bound 가정: tok/s ≈ memory_bandwidth × 0.1315\n"
        "(A6000 768 GB/s → 101 tok/s 실측 기준)",
        transform=ax.transAxes, fontsize=8, va="top",
        bbox=dict(boxstyle="round", facecolor="#fffacd", alpha=0.8))

fig.text(0.5, 0.01,
         f"가격 기준: {PRICE_SOURCE}, 기준일 {PRICE_DATE}  ·  "
         "성능: A6000 실측 앵커 + 메모리대역폭 비례 추정",
         ha="center", fontsize=7.5, color="#555")
plt.tight_layout(rect=[0, 0.035, 1, 1])
out1 = "/Users/ssh/project/reports/phase3/gpu_cost_throughput.png"
os.makedirs(os.path.dirname(out1), exist_ok=True)
plt.savefig(out1, dpi=160)
print(f"saved {out1}")

# --- 2) Cost Efficiency 막대 (tok/s per 만원)
fig2, ax2 = plt.subplots(figsize=(11, 6))
rows_sorted = sorted(rows, key=lambda r: r["tok_per_sec"] / r["price_man_won"])
names = [r["name"] for r in rows_sorted]
ratios = [round(r["tok_per_sec"] / r["price_man_won"], 3) for r in rows_sorted]
colors = ["#d62728" if r["kind"] == "measured" else "#9ecae1" for r in rows_sorted]
bars = ax2.barh(names, ratios, color=colors, edgecolor="black")
for bar, v in zip(bars, ratios):
    ax2.text(v + 0.005, bar.get_y() + bar.get_height() / 2,
             f"{v}", va="center", fontsize=9)
ax2.set_xlabel("Cost Efficiency — tok/s per ₩10K (higher is better)", fontsize=11)
ax2.set_title("GPU Cost Efficiency — gemma4:26b on-prem LLM (★=A6000 measured)",
              fontsize=12)
ax2.grid(True, axis="x", alpha=0.3)
fig2.text(0.5, 0.01,
          f"가격 기준: {PRICE_SOURCE}, 기준일 {PRICE_DATE}",
          ha="center", fontsize=7.5, color="#555")
plt.tight_layout(rect=[0, 0.04, 1, 1])
out2 = "/Users/ssh/project/reports/phase3/gpu_cost_efficiency.png"
plt.savefig(out2, dpi=160)
print(f"saved {out2}")

# --- 3) JSON dump (raw)
out3 = "/Users/ssh/project/reports/phase3/gpu_throughput_estimates.json"
with open(out3, "w") as f:
    json.dump({
        "model": "gemma4:26b Q4_K_M",
        "measured_baseline": {
            "gpu": "RTX A6000 48GB",
            "tok_per_sec": A6000_MEASURED,
            "mem_bandwidth_gb_s": A6000_BW,
            "n_runs": 15, "stdev": 0.84,
            "source": "KNU GPU cluster DIS06, 2026-06-04",
        },
        "estimation_model": "tok/s ≈ memory_bandwidth × 0.1315 (LLM is memory-bound)",
        "price_basis": {
            "date": PRICE_DATE,
            "source": PRICE_SOURCE,
            "currency": "만원 (10K KRW)",
            "note": "소비자급은 다나와/중고 실시세 확인, 데이터센터급은 병행수입 추정으로 변동 큼",
        },
        "gpus": rows,
    }, f, ensure_ascii=False, indent=2)
print(f"saved {out3}")

# 텍스트 표
print("\n=== Summary ===")
print(f"{'GPU':<22}{'BW(GB/s)':>10}{'tok/s':>10}{'price(만원)':>12}{'kind':>12}")
for r in rows_sorted:
    print(f"{r['name']:<22}{r['mem_bw']:>10}{r['tok_per_sec']:>10}"
          f"{r['price_man_won']:>12}{r['kind']:>12}")
