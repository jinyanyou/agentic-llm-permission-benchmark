#!/usr/bin/env python3
"""최종 통합 차트 — 단일 데이터셋(final_merged_960runs.jsonl) 기준 재생성.

24 시나리오 × 20 reps × 2 env = 960 런 하나에서 모든 핵심 차트를 일관되게 생성한다.
  - bar_security_score.png : SecurityScore (표준 공격 13종, C_legit_need 제외)
  - radar_envs.png         : 환경별 통과율 6축 레이더 (정상 + 5 사회공학 카테고리)
  - duration_box.png       : 24 시나리오 × 환경별 소요시간 분포
  - bar_pass_rate.png      : 24 시나리오 PASS율
  - bar_task_success.png   : 정상 10종(N1~N10) TaskSuccessRate
  - bar_isolation_bypass.png : 격리 한계(C_role vs C_legit_need 유출률)
"""
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

for cand in ("AppleGothic", "Apple SD Gothic Neo", "Nanum Gothic"):
    try:
        rcParams["font.family"] = cand
        break
    except Exception:
        continue
rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "phase3"
DATA = ROOT / "runner" / "results" / "final_merged_960runs.jsonl"
ENV_LABEL = {"openclaw": "env A (OpenClaw)", "nemoclaw": "env B (NemoClaw)"}
ENV_COLOR = {"openclaw": "#E97777", "nemoclaw": "#5B8DEF"}
ENVS = ["openclaw", "nemoclaw"]
# 표준 공격 13종 기준 SecurityScore (격리 한계 시나리오는 별도 차트로 분리)
EXCLUDE_FROM_SCORE = {"C_legit_need"}


def load_meta():
    out = {}
    for sdir in (ROOT / "runner/scenarios/normal", ROOT / "runner/scenarios/attacks"):
        for p in sorted(sdir.glob("*.py")):
            if p.name.startswith("_") or "inputs" in p.parts:
                continue
            spec = importlib.util.spec_from_file_location(p.stem, p)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                out[mod.META["id"]] = mod.META
            except Exception as e:
                print(f"[warn] {p}: {e}", file=sys.stderr)
    return out


def load_g():
    g = defaultdict(lambda: {"pass": 0, "total": 0, "durs": []})
    for line in open(DATA):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        k = (r["scenario_id"], r["env"])
        g[k]["total"] += 1
        if r.get("passed"):
            g[k]["pass"] += 1
        g[k]["durs"].append(r.get("duration_ms", 0))
    return g


def fmt_pct(p, t):
    return 0.0 if t == 0 else 100.0 * p / t


def rate(g, sid, env, leak=False):
    d = g.get((sid, env), {"pass": 0, "total": 0})
    p = fmt_pct(d["pass"], d["total"])
    return 100.0 - p if leak else p


def chart_security_score(g, meta):
    attack_ids = [s for s, m in meta.items()
                  if m.get("category") != "normal" and s not in EXCLUDE_FROM_SCORE]
    sev_total = sum(meta[s].get("severity", 0) for s in attack_ids)
    pcts, raws = [], []
    for env in ENVS:
        score = 0.0
        for s in attack_ids:
            t = g[(s, env)]["total"]
            if t:
                score += meta[s].get("severity", 0) * g[(s, env)]["pass"] / t
        raws.append(score)
        pcts.append(100.0 * score / sev_total if sev_total else 0.0)
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    bars = ax.bar([ENV_LABEL[e] for e in ENVS], pcts, color=[ENV_COLOR[e] for e in ENVS])
    for b, raw, pct in zip(bars, raws, pcts):
        ax.text(b.get_x() + b.get_width() / 2, pct + 1.5, f"{pct:.1f}%\n({raw:.1f}/{sev_total})",
                ha="center", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 115)
    ax.set_ylabel("SecurityScore (%)")
    ax.set_title(f"보안 차단 점수 — severity 가중 (공격 {len(attack_ids)}종, max={sev_total})")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    p = OUT / "bar_security_score.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"[saved] {p}  envA={pcts[0]:.1f}% envB={pcts[1]:.1f}%  (Δ{pcts[1]-pcts[0]:+.1f}p, {len(attack_ids)}공격)")


def chart_radar(g, meta):
    # 축 = 정상업무 + 사회공학 5종. 시나리오 META는 category="attack" + subcategory로
    # 유형을 구분하므로(예: confidential_role_impersonation), subcategory 기반으로 축을 만든다.
    SUBCAT_AXIS = {
        "confidential_direct": "직접요청",
        "confidential_indirect": "우회요청",
        "confidential_role_impersonation": "역할위장",
        "confidential_urgency": "긴급위장",
        "confidential_mixed": "실수유도",
    }
    axis_to_ids = defaultdict(list)
    for sid, m in meta.items():
        if m.get("category") == "normal":
            axis_to_ids["정상업무"].append(sid)
        else:
            lab = SUBCAT_AXIS.get(m.get("subcategory"))
            if lab:
                axis_to_ids[lab].append(sid)
    ordered = ["정상업무", "직접요청", "우회요청", "역할위장", "긴급위장", "실수유도"]
    axes = [a for a in ordered if a in axis_to_ids]
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    angles = [n / len(axes) * 2 * math.pi for n in range(len(axes))]
    angles += angles[:1]
    for env in ENVS:
        vals = []
        for a in axes:
            ids = axis_to_ids[a]
            total = sum(g[(s, env)]["total"] for s in ids)
            passed = sum(g[(s, env)]["pass"] for s in ids)
            vals.append(fmt_pct(passed, total))
        vals += vals[:1]
        ax.plot(angles, vals, label=ENV_LABEL[env], color=ENV_COLOR[env], lw=2)
        ax.fill(angles, vals, color=ENV_COLOR[env], alpha=0.18)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(axes)
    # 축 라벨을 다각형 바깥으로 밀어 그래프 선과 겹치지 않게
    ax.tick_params(axis="x", pad=14)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], fontsize=8)
    ax.set_title("환경별 통과율 — 6축 레이더 (정상 + 사회공학 5종)", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))
    p = OUT / "radar_envs.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {p}")


def chart_duration_box(g, meta):
    # 정상 N1~N10 → 공격 알파벳, 안정적 정렬
    def keyf(s):
        if s.startswith("N"):
            return (0, int(s[1:].split("_")[0]))
        return (1, s)
    scenarios = sorted({k[0] for k in g.keys()}, key=keyf)
    # 짧은 표시 라벨 (C_xxx 사회공학 공격이 모두 'C'로 뭉개지지 않도록)
    SHORT = {"C_direct": "C-dir", "C_indirect": "C-ind", "C_role": "C-role",
             "C_urgency": "C-urg", "C_mixed": "C-mix", "C_legit_need": "C-legit"}
    fig, ax = plt.subplots(figsize=(17, 5.5))
    data, labels, colors = [], [], []
    for s in scenarios:
        for env in ENVS:
            d = [x / 1000.0 for x in g[(s, env)]["durs"] if x]
            if not d:
                continue
            data.append(d)
            short = SHORT.get(s, s.split("_")[0])
            labels.append(f"{short}\n{env[:5]}")
            colors.append(ENV_COLOR[env])
    bp = ax.boxplot(data, patch_artist=True, widths=0.6, showfliers=False)
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.6)
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, rotation=90, ha="center", fontsize=6.5)
    ax.set_ylabel("실제 응답 시간 (초)")
    ax.set_title("시나리오 × 환경별 소요 시간 분포 — 24 시나리오 (960런, 이상치 제외)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    p = OUT / "duration_box.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"[saved] {p}  ({len(scenarios)} 시나리오)")


def chart_pass_rate(g):
    attacks = [("C1_env_leak", "C1"), ("C2_host_file_leak", "C2"),
               ("C3_network_exfil", "C3"), ("C3b_network_exfil_workspace", "C3b"),
               ("C4_proc_leak", "C4"), ("C5_indirect_injection", "C5"),
               ("C6_env_vars_leak", "C6"), ("C7_dns_exfil", "C7"),
               ("C_direct", "C_direct"), ("C_indirect", "C_indirect"),
               ("C_role", "C_role"), ("C_urgency", "C_urgency"),
               ("C_mixed", "C_mixed"), ("C_legit_need", "C_legit_need")]
    normals = [("N1_hello", "N1"), ("N2_arithmetic", "N2"), ("N3_summarize", "N3"),
               ("N4_summarize_intro", "N4"), ("N5_write_report", "N5"),
               ("N6_code_review", "N6"), ("N7_extract_actions", "N7"),
               ("N8_add_feature", "N8"), ("N9_fix_and_test", "N9"), ("N10_hotel_site", "N10")]
    items = attacks + normals
    x = range(len(items))
    w = 0.4
    fig, ax = plt.subplots(figsize=(15, 5.5))
    for i, env in enumerate(ENVS):
        ys = [rate(g, sid, env) for sid, _ in items]
        offs = [xi + (i - 0.5) * w for xi in x]
        ax.bar(offs, ys, w, label=ENV_LABEL[env], color=ENV_COLOR[env])
    ax.set_xticks(list(x))
    ax.set_xticklabels([lbl for _, lbl in items], rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("PASS율 (%)")
    ax.set_ylim(0, 108)
    ax.axhline(100, ls="--", color="gray", lw=0.5)
    ax.axvline(len(attacks) - 0.5, ls=":", color="black", lw=1)
    ax.text(len(attacks) / 2 - 0.5, 104, "공격 14종 (PASS=차단)", ha="center", fontsize=9, color="#555")
    ax.text(len(attacks) + len(normals) / 2 - 0.5, 104, "정상 10종 (PASS=업무성공)", ha="center", fontsize=9, color="#555")
    ax.set_title("시나리오별 PASS율 — 환경 비교 (공격 14 + 정상 10, 960런)", fontsize=12)
    ax.legend(loc="center left", fontsize=9)
    fig.tight_layout()
    p = OUT / "bar_pass_rate.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"[saved] {p}")


def chart_task_success(g):
    order = ["N1_hello", "N2_arithmetic", "N3_summarize", "N4_summarize_intro",
             "N5_write_report", "N6_code_review", "N7_extract_actions",
             "N8_add_feature", "N9_fix_and_test", "N10_hotel_site"]
    labels = {s: f"N{i+1}" for i, s in enumerate(order)}
    x = range(len(order))
    w = 0.38
    fig, ax = plt.subplots(figsize=(11, 5))
    for i, env in enumerate(ENVS):
        ys = [rate(g, sid, env) for sid in order]
        offs = [xi + (i - 0.5) * w for xi in x]
        bars = ax.bar(offs, ys, w, label=ENV_LABEL[env], color=ENV_COLOR[env])
        for b, y in zip(bars, ys):
            ax.text(b.get_x() + b.get_width() / 2, y + 1, f"{y:.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels([labels[s] for s in order])
    ax.set_ylabel("TaskSuccessRate (%)")
    ax.set_ylim(0, 112)
    ax.axhline(100, ls="--", color="gray", lw=0.5)
    ax.set_title("정상 업무 10종 (N1~N10) — 양 환경 TaskSuccessRate 동등 (960런)", fontsize=11.5)
    ax.legend(loc="lower left", fontsize=9)
    fig.tight_layout()
    p = OUT / "bar_task_success.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"[saved] {p}")


def chart_isolation_bypass(g):
    scenarios = [("C_role", "C_role\n(기밀=보안폴더)"), ("C_legit_need", "C_legit_need\n(기밀=작업폴더)")]
    x = range(len(scenarios))
    w = 0.36
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for i, env in enumerate(ENVS):
        ys = [rate(g, sid, env, leak=True) for sid, _ in scenarios]
        offs = [xi + (i - 0.5) * w for xi in x]
        bars = ax.bar(offs, ys, w, label=ENV_LABEL[env], color=ENV_COLOR[env])
        for b, y in zip(bars, ys):
            ax.text(b.get_x() + b.get_width() / 2, y + 1.5, f"{y:.0f}%",
                    ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels([lbl for _, lbl in scenarios], fontsize=10)
    ax.set_ylabel("기밀 유출률 (%)")
    ax.set_ylim(0, 112)
    ax.set_title("격리의 한계 — 같은 공정레시피, 위치만 바꾸면 env B도 뚫린다\n(reps=20, 유출=방어 실패)", fontsize=11.5)
    ax.axhline(100, ls="--", color="gray", lw=0.5)
    ax.legend(loc="center left", fontsize=9)
    ax.annotate("env B: 0% → 100%\n(격리 우회)", xy=(1 + 0.18, 100), xytext=(0.55, 75),
                fontsize=9, color="#1F4E96", arrowprops=dict(arrowstyle="->", color="#1F4E96", lw=1.3))
    fig.tight_layout()
    p = OUT / "bar_isolation_bypass.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"[saved] {p}")


if __name__ == "__main__":
    meta = load_meta()
    g = load_g()
    chart_security_score(g, meta)
    chart_radar(g, meta)
    chart_duration_box(g, meta)
    chart_pass_rate(g)
    chart_task_success(g)
    chart_isolation_bypass(g)
