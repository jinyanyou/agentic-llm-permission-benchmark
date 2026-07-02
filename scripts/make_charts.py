#!/usr/bin/env python3
"""Generate presentation charts from runner JSONL logs.

Usage:
    python3 scripts/make_charts.py \
        --jsonl runner/results/mini_reps3_20260519.jsonl \
        --outdir reports/phase3

    # multiple files merged
    python3 scripts/make_charts.py --jsonl 'runner/results/*.jsonl' --outdir reports/phase3

Outputs (PNG, 150 DPI):
    bar_pass_rate.png       - per-scenario PASS rate, env A vs env B
    bar_task_success.png    - TaskSuccessRate (normal only) per env
    bar_security_score.png  - SecurityScore (severity-weighted) per env
    radar_envs.png          - 5-axis radar: TaskSuccess + 4 attack categories
    duration_box.png        - per-scenario duration distribution

Korean font: tries AppleGothic (macOS default). Falls back to DejaVu Sans.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

# Korean font (macOS)
for cand in ("AppleGothic", "Apple SD Gothic Neo", "Nanum Gothic"):
    try:
        rcParams["font.family"] = cand
        break
    except Exception:
        continue
rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIRS = [ROOT / "runner" / "scenarios" / "normal",
                 ROOT / "runner" / "scenarios" / "attacks"]
ENV_LABEL = {"openclaw": "env A (OpenClaw)", "nemoclaw": "env B (NemoClaw)"}
ENV_COLOR = {"openclaw": "#E97777", "nemoclaw": "#5B8DEF"}


def load_meta() -> dict:
    out = {}
    for sdir in SCENARIO_DIRS:
        if not sdir.exists():
            continue
        for p in sdir.glob("*.py"):
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


def load_rows(patterns: list[str]) -> list:
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    rows = []
    for f in sorted(set(files)):
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def aggregate(rows: list, meta: dict) -> dict:
    """Returns nested: per_scenario[(scenario, env)] = {pass, total, durs}."""
    g = defaultdict(lambda: {"pass": 0, "total": 0, "durs": []})
    for r in rows:
        key = (r["scenario_id"], r["env"])
        g[key]["total"] += 1
        if r.get("passed"):
            g[key]["pass"] += 1
        g[key]["durs"].append(r.get("duration_ms", 0))
    return g


def fmt_pct(p, t):
    return 0.0 if t == 0 else 100.0 * p / t


def chart_pass_rate(g: dict, meta: dict, outdir: Path):
    scenarios = sorted({k[0] for k in g.keys()}, key=lambda s: (s[0], s))
    envs = ["openclaw", "nemoclaw"]
    x = list(range(len(scenarios)))
    w = 0.38
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for i, env in enumerate(envs):
        ys = [fmt_pct(g[(s, env)]["pass"], g[(s, env)]["total"]) for s in scenarios]
        offsets = [xi + (i - 0.5) * w for xi in x]
        ax.bar(offsets, ys, w, label=ENV_LABEL[env], color=ENV_COLOR[env])
        for xi, y in zip(offsets, ys):
            ax.text(xi, y + 1.5, f"{y:.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=30, ha="right")
    ax.set_ylim(0, 110)
    ax.set_ylabel("PASS율 (%)")
    ax.set_title("시나리오별 PASS율 — 환경 비교")
    ax.axhline(100, ls="--", color="gray", lw=0.5)
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    p = outdir / "bar_pass_rate.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def chart_task_success(g: dict, meta: dict, outdir: Path):
    normal_ids = [sid for sid, m in meta.items() if m.get("category") == "normal"]
    envs = ["openclaw", "nemoclaw"]
    ys = []
    for env in envs:
        total = sum(g[(s, env)]["total"] for s in normal_ids)
        passed = sum(g[(s, env)]["pass"] for s in normal_ids)
        ys.append(fmt_pct(passed, total))
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    bars = ax.bar([ENV_LABEL[e] for e in envs], ys,
                  color=[ENV_COLOR[e] for e in envs])
    for b, y in zip(bars, ys):
        ax.text(b.get_x() + b.get_width() / 2, y + 1.5, f"{y:.1f}%",
                ha="center", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 110)
    ax.set_ylabel("TaskSuccessRate (%)")
    ax.set_title("정상 업무 통과율 (N4~N8 누적)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    p = outdir / "bar_task_success.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def chart_security_score(g: dict, meta: dict, outdir: Path):
    # SecurityScore = sum(severity * defense_rate) for category != normal
    attack_ids = [sid for sid, m in meta.items() if m.get("category") != "normal"]
    sev_total = sum(meta[s].get("severity", 0) for s in attack_ids)
    envs = ["openclaw", "nemoclaw"]
    ys, pcts = [], []
    for env in envs:
        score = 0.0
        for s in attack_ids:
            t = g[(s, env)]["total"]
            if t == 0:
                continue
            dr = g[(s, env)]["pass"] / t
            score += meta[s].get("severity", 0) * dr
        ys.append(score)
        pcts.append(100.0 * score / sev_total if sev_total else 0.0)
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    bars = ax.bar([ENV_LABEL[e] for e in envs], pcts,
                  color=[ENV_COLOR[e] for e in envs])
    for b, raw, pct in zip(bars, ys, pcts):
        ax.text(b.get_x() + b.get_width() / 2, pct + 1.5,
                f"{pct:.1f}%\n({raw:.1f}/{sev_total})",
                ha="center", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 115)
    ax.set_ylabel("SecurityScore (%)")
    ax.set_title(f"보안 차단 점수 — severity 가중 (max={sev_total})")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    p = outdir / "bar_security_score.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def chart_radar(g: dict, meta: dict, outdir: Path):
    # axes: TaskSuccess + per attack category
    categories = []
    cat_to_ids = defaultdict(list)
    for sid, m in meta.items():
        c = m.get("category", "normal")
        cat_to_ids[c].append(sid)
    # ordered axes
    ordered = ["normal", "direct", "indirect",
               "role_impersonation", "urgency", "mixed_context"]
    axes = [c for c in ordered if c in cat_to_ids]
    pretty = {"normal": "정상업무", "direct": "직접요청",
              "indirect": "우회요청", "role_impersonation": "역할위장",
              "urgency": "긴급위장", "mixed_context": "실수유도"}
    envs = ["openclaw", "nemoclaw"]
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    angles = [n / len(axes) * 2 * math.pi for n in range(len(axes))]
    angles += angles[:1]
    for env in envs:
        vals = []
        for c in axes:
            ids = cat_to_ids[c]
            total = sum(g[(s, env)]["total"] for s in ids)
            passed = sum(g[(s, env)]["pass"] for s in ids)
            vals.append(fmt_pct(passed, total))
        vals += vals[:1]
        ax.plot(angles, vals, label=ENV_LABEL[env],
                color=ENV_COLOR[env], lw=2)
        ax.fill(angles, vals, color=ENV_COLOR[env], alpha=0.18)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([pretty.get(c, c) for c in axes])
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], fontsize=8)
    ax.set_title("환경별 통과율 — 6축 레이더", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))
    p = outdir / "radar_envs.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def chart_duration_box(g: dict, outdir: Path):
    scenarios = sorted({k[0] for k in g.keys()})
    fig, ax = plt.subplots(figsize=(11, 5))
    data, labels, colors = [], [], []
    for s in scenarios:
        for env in ("openclaw", "nemoclaw"):
            d = [x / 1000.0 for x in g[(s, env)]["durs"] if x]
            if not d:
                continue
            data.append(d)
            labels.append(f"{s}\n{env[:5]}")
            colors.append(ENV_COLOR[env])
    bp = ax.boxplot(data, patch_artist=True, widths=0.6)
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.6)
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("소요 시간 (초)")
    ax.set_title("시나리오 × 환경별 소요 시간 분포")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    p = outdir / "duration_box.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", action="append", default=[],
                    help="JSONL path (glob ok). Repeatable. "
                         "Default: runner/results/*.jsonl")
    ap.add_argument("--outdir", default="reports/phase3")
    args = ap.parse_args()

    patterns = args.jsonl or [str(ROOT / "runner" / "results" / "*.jsonl")]
    rows = load_rows(patterns)
    if not rows:
        print(f"[error] no rows from {patterns}", file=sys.stderr)
        sys.exit(1)
    meta = load_meta()
    g = aggregate(rows, meta)

    outdir = Path(args.outdir)
    if not outdir.is_absolute():
        outdir = ROOT / outdir
    outdir.mkdir(parents=True, exist_ok=True)

    out = []
    out.append(chart_pass_rate(g, meta, outdir))
    out.append(chart_task_success(g, meta, outdir))
    out.append(chart_security_score(g, meta, outdir))
    out.append(chart_radar(g, meta, outdir))
    out.append(chart_duration_box(g, outdir))

    print(f"[done] {len(rows)} rows from {len(patterns)} pattern(s)")
    print(f"[done] {len(g)} (scenario, env) groups")
    for p in out:
        print(f"  -> {p}")


if __name__ == "__main__":
    main()
