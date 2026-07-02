#!/usr/bin/env python3
# plot_architecture.py — env A vs env B 권한 구조 비교 다이어그램
# 발표 슬라이드 5 메인 시각 (멘토 #13: 데모<시각화)

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

plt.rcParams["font.family"] = "Apple SD Gothic Neo"
plt.rcParams["axes.unicode_minus"] = False

OUT = "$HOME/project/reports/phase3/architecture_envA_vs_envB.png"

# ---- 색 팔레트 ----
C_USER = "#dbe9f4"
C_AGENT = "#f9e3a4"
C_POLICY = "#9ad4a3"
C_RES = "#f3f3f3"
C_DENY = "#f3aaa6"
C_ALLOW = "#a7d99a"
C_GAP = "#f5d061"

ARROW_OK = dict(color="#2a7a3a", lw=2.0,
                arrowstyle="-|>,head_length=8,head_width=6",
                connectionstyle="arc3,rad=0.0")
ARROW_DENY = dict(color="#b22222", lw=2.0,
                  arrowstyle="-|>,head_length=8,head_width=6",
                  connectionstyle="arc3,rad=0.0", linestyle="--")
ARROW_GAP = dict(color="#c89b1c", lw=2.0,
                 arrowstyle="-|>,head_length=8,head_width=6",
                 connectionstyle="arc3,rad=0.0")


def box(ax, xy, w, h, label, fc=C_RES, ec="#444", lw=1.2, fs=10, fw="normal"):
    """둥근 사각형 박스."""
    x, y = xy
    patch = FancyBboxPatch((x, y), w, h,
                           boxstyle="round,pad=0.04,rounding_size=0.18",
                           fc=fc, ec=ec, lw=lw, zorder=2)
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, label,
            ha="center", va="center", fontsize=fs, fontweight=fw, zorder=3)


def arrow(ax, src, dst, style):
    a = FancyArrowPatch(src, dst, **style, zorder=2.5)
    ax.add_patch(a)


def label_arrow(ax, src, dst, text, color, offset=(0, 0), fs=8):
    mx = (src[0] + dst[0]) / 2 + offset[0]
    my = (src[1] + dst[1]) / 2 + offset[1]
    ax.text(mx, my, text, ha="center", va="center",
            fontsize=fs, color=color, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85),
            zorder=4)


# ===== Figure layout =====
fig, (axA, axB) = plt.subplots(1, 2, figsize=(16, 9))
for ax in (axA, axB):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis("off")

# ---- 패널 제목 ----
axA.text(5, 11.6, "env A — OpenClaw (무샌드박스)",
         ha="center", va="center", fontsize=15, fontweight="bold", color="#b22222")
axA.text(5, 11.1, "SecurityScore 34.8%   ·   사회공학 유출 100%",
         ha="center", va="center", fontsize=10, color="#666")

axB.text(5, 11.6, "env B — NemoClaw (OpenShell 샌드박스)",
         ha="center", va="center", fontsize=15, fontweight="bold", color="#2a7a3a")
axB.text(5, 11.1, "SecurityScore 81.5%   ·   사회공학 유출 0%   ·   Δ +46.7%p",
         ha="center", va="center", fontsize=10, color="#666")


# =========================
#  env A — 무샌드박스
# =========================
box(axA, (3.2, 9.5), 3.6, 1.0, "사용자 (사내 직원)", fc=C_USER, fs=11, fw="bold")
box(axA, (3.0, 7.8), 4.0, 1.1, "AI 에이전트\n(gemma4:26b)", fc=C_AGENT, fs=11, fw="bold")

# 자원 행 (y=4.0~6.0)
res_y = 4.0
res_h = 1.2
res_w = 1.7
res_gap = 0.25
xs = []
x = 0.4
for _ in range(5):
    xs.append(x)
    x += res_w + res_gap

resources = [
    (xs[0], "워크스페이스\n(.openclaw/)", C_RES),
    (xs[1], "사내 기밀 폴더\n(인사·IP·재무)", C_RES),
    (xs[2], "워크스페이스 .env\n(API 키)", C_RES),
    (xs[3], "호스트 FS\n(/etc, /Users/)", C_RES),
    (xs[4], "외부 네트워크\n(임의 도메인)", C_RES),
]
for xx, label, fc in resources:
    box(axA, (xx, res_y), res_w, res_h, label, fc=fc, fs=8.5)

# 사용자 -> 에이전트
arrow(axA, (5.0, 9.5), (5.0, 8.9), ARROW_OK)

# 에이전트 -> 모든 자원 (다 통과 = 빨강 X marker)
agent_bot = (5.0, 7.8)
for xx, label, _ in resources:
    src = agent_bot
    dst = (xx + res_w / 2, res_y + res_h)
    arrow(axA, src, dst, ARROW_OK)

# 결과 라벨 (자원 박스 아래)
label_y = res_y - 0.55
labels_A = [
    (xs[0] + res_w/2, "정상 ✓", "#2a7a3a"),
    (xs[1] + res_w/2, "100% 유출", "#b22222"),
    (xs[2] + res_w/2, "100% 유출", "#b22222"),
    (xs[3] + res_w/2, "100% 유출", "#b22222"),
    (xs[4] + res_w/2, "90% 유출", "#b22222"),
]
for xx, txt, col in labels_A:
    axA.text(xx, label_y, txt, ha="center", va="center",
             fontsize=9, fontweight="bold", color=col)

# 가설 한 줄
axA.text(5, 2.1,
         "권한 제어 = OS chmod만\n"
         "에이전트 UID가 접근 권한 = 모든 파일 접근",
         ha="center", va="center", fontsize=10,
         bbox=dict(boxstyle="round,pad=0.5", fc="#fff5f5", ec="#b22222", lw=1.2))


# =========================
#  env B — OpenShell Policy
# =========================
box(axB, (3.2, 9.5), 3.6, 1.0, "사용자 (사내 직원)", fc=C_USER, fs=11, fw="bold")
box(axB, (3.0, 7.8), 4.0, 1.1, "AI 에이전트\n(gemma4:26b — 동일 모델)",
    fc=C_AGENT, fs=11, fw="bold")

# 정책 레이어 (env B에만 있는 차별점)
box(axB, (0.5, 6.0), 9.0, 0.9,
    "OpenShell Policy Layer  (Landlock + Declarative Whitelist)",
    fc=C_POLICY, ec="#1e6f33", lw=1.6, fs=11, fw="bold")

# 자원 행
xs_b = xs
resources_B = [
    (xs_b[0], "워크스페이스\n(/sandbox/)", C_RES),
    (xs_b[1], "사내 기밀 폴더\n(paths.deny)", C_DENY),
    (xs_b[2], "워크스페이스 .env\n(gap — §3.2)", C_GAP),
    (xs_b[3], "호스트 FS\n(invisible)", C_DENY),
    (xs_b[4], "외부 네트워크\n(whitelist만)", C_RES),
]
for xx, label, fc in resources_B:
    box(axB, (xx, res_y), res_w, res_h, label, fc=fc, fs=8.5)

# 사용자 -> 에이전트
arrow(axB, (5.0, 9.5), (5.0, 8.9), ARROW_OK)

# 에이전트 -> 정책 레이어
arrow(axB, (5.0, 7.8), (5.0, 6.9), ARROW_OK)

# 정책 -> 자원 (선택적)
policy_bot = 6.0
styles_B = [
    ARROW_OK,    # 워크스페이스 통과
    ARROW_DENY,  # 기밀 폴더 차단
    ARROW_GAP,   # .env gap (통과되지만 §3.2 보완 필요)
    ARROW_DENY,  # 호스트 FS 차단
    ARROW_OK,    # 외부망 whitelist 통과
]
for xx, _, _ in resources_B:
    dst_x = xx + res_w / 2
    src = (dst_x, policy_bot)
    dst = (dst_x, res_y + res_h)
arrow_targets = []  # rebuild explicit for clarity
for (xx, _, _), style in zip(resources_B, styles_B):
    dst_x = xx + res_w / 2
    src = (dst_x, policy_bot)
    dst = (dst_x, res_y + res_h)
    arrow(axB, src, dst, style)

# 결과 라벨
labels_B = [
    (xs_b[0] + res_w/2, "정상 ✓", "#2a7a3a"),
    (xs_b[1] + res_w/2, "0% 유출 ✓", "#2a7a3a"),
    (xs_b[2] + res_w/2, "gap (동일)", "#c89b1c"),
    (xs_b[3] + res_w/2, "0% 유출 ✓", "#2a7a3a"),
    (xs_b[4] + res_w/2, "0% 유출 ✓", "#2a7a3a"),
]
for xx, txt, col in labels_B:
    axB.text(xx, label_y, txt, ha="center", va="center",
             fontsize=9, fontweight="bold", color=col)

# 가설 한 줄
axB.text(5, 2.1,
         "권한 제어 = Policy (Landlock + whitelist)\n"
         "에이전트는 보안 폴더·호스트 FS를 인지하지 못함 (invisible)",
         ha="center", va="center", fontsize=10,
         bbox=dict(boxstyle="round,pad=0.5", fc="#f1faec", ec="#2a7a3a", lw=1.2))


# 공통 — Phase 3 v2 출처
fig.text(0.5, 0.02,
         "Phase 3 v2 본 실험 (n=20/시나리오, 21시나리오 × 2env = 840런, 2026-05-28)",
         ha="center", va="center", fontsize=9, color="#777", style="italic")

# 범례 (위쪽 우측)
legend_elems = [
    Line2D([0], [0], color="#2a7a3a", lw=2.5, label="허용 (통과)"),
    Line2D([0], [0], color="#b22222", lw=2.5, linestyle="--", label="정책 차단"),
    Line2D([0], [0], color="#c89b1c", lw=2.5, label="gap (보완 필요)"),
]
fig.legend(handles=legend_elems, loc="upper center",
           bbox_to_anchor=(0.5, 0.97), ncol=3, frameon=False, fontsize=10)

fig.suptitle("동일 AI 에이전트, 다른 권한 구조 — 사내 기밀 유출 차단률 0%↔100%",
             fontsize=15, fontweight="bold", y=1.0)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
plt.tight_layout(rect=[0, 0.04, 1, 0.93])
plt.savefig(OUT, dpi=160, bbox_inches="tight")
print(f"saved {OUT}")
