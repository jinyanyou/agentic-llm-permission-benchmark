#!/usr/bin/env python3
# plot_radar_fix.py — radar_envs.png 재생성
# 원인: make_charts.py가 META["category"]만 보는데 다 "attack"이라 1축만 그려짐
# 수정: scenario_id 직접 매핑 (정상 + 5 보안 시나리오)

import json
import math
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Apple SD Gothic Neo"
plt.rcParams["axes.unicode_minus"] = False

JSONL = "$HOME/project/runner/results/phase3_v2_merged_20260528.jsonl"
OUT = "$HOME/project/reports/phase3/radar_envs.png"

# 축 정의: 정상 8종 통합 + 5 보안 시나리오
AXES = [
    ("정상 업무\n(N1~N8)", lambda s: s.startswith("N")),
    ("직접 요청\n(C_direct)", lambda s: s == "C_direct"),
    ("우회 요청\n(C_indirect)", lambda s: s == "C_indirect"),
    ("역할 위장\n(C_role)", lambda s: s == "C_role"),
    ("긴급 위장\n(C_urgency)", lambda s: s == "C_urgency"),
    ("혼합 맥락\n(C_mixed)", lambda s: s == "C_mixed"),
]

ENV_COLOR = {"openclaw": "#d62728", "nemoclaw": "#1f77b4"}
ENV_LABEL = {"openclaw": "env A (OpenClaw, 무샌드박스)",
             "nemoclaw": "env B (NemoClaw, 샌드박스)"}

# 데이터 집계: env × axis → pass rate
stats = defaultdict(lambda: defaultdict(lambda: {"pass": 0, "total": 0}))
with open(JSONL) as f:
    for line in f:
        if not line.strip():
            continue
        r = json.loads(line)
        s = r["scenario_id"]
        e = r["env"]
        for label, pred in AXES:
            if pred(s):
                stats[e][label]["total"] += 1
                if r.get("passed"):
                    stats[e][label]["pass"] += 1
                break

# 검증 출력
print("=== axis × env pass rate ===")
for env in ["openclaw", "nemoclaw"]:
    print(f"\n{env}:")
    for label, _ in AXES:
        d = stats[env][label]
        pct = (d["pass"] / d["total"] * 100) if d["total"] else 0
        print(f"  {label!r:<22} {d['pass']}/{d['total']} = {pct:.1f}%")

# 레이더 그리기
labels = [lab for lab, _ in AXES]
N = len(labels)
angles = [n / N * 2 * math.pi for n in range(N)]
angles += angles[:1]

fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
ax.set_theta_offset(math.pi / 2)
ax.set_theta_direction(-1)

for env in ["openclaw", "nemoclaw"]:
    vals = []
    for label, _ in AXES:
        d = stats[env][label]
        pct = (d["pass"] / d["total"] * 100) if d["total"] else 0
        vals.append(pct)
    vals += vals[:1]
    ax.plot(angles, vals, label=ENV_LABEL[env],
            color=ENV_COLOR[env], lw=2.5, marker="o", markersize=7)
    ax.fill(angles, vals, color=ENV_COLOR[env], alpha=0.20)
    # 값 라벨
    for ang, v, lab in zip(angles[:-1], vals[:-1], labels):
        ax.text(ang, v + 4, f"{v:.0f}%", ha="center", va="center",
                fontsize=9, color=ENV_COLOR[env], fontweight="bold")

ax.set_xticks(angles[:-1])
ax.set_xticklabels(labels, fontsize=10)
ax.set_ylim(0, 110)
ax.set_yticks([20, 40, 60, 80, 100])
ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8, color="#888")
ax.set_rlabel_position(180 / N)
ax.grid(True, alpha=0.4)

ax.set_title("환경별 통과율 — 정상 업무 + 5 보안 시나리오\n"
             "(Phase 3 v2, 840런, n=20/시나리오)",
             fontsize=13, fontweight="bold", pad=30)

ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08),
          ncol=2, frameon=False, fontsize=10)

# 해석 박스
fig.text(0.5, 0.02,
         "정상 업무: 양 환경 동등 통과(편의)  |  보안 시나리오: env B가 넓은 다각형 = 차단률 우위(보안)",
         ha="center", va="bottom", fontsize=9, color="#555", style="italic")

plt.tight_layout(rect=[0, 0.05, 1, 0.96])
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT, dpi=160, bbox_inches="tight")
print(f"\nsaved {OUT}")
