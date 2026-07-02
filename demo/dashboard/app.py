#!/usr/bin/env python3
"""Demo dashboard — SecurityScore + TaskSuccessRate live page.

Single-file Flask app. Reads latest JSONL from runner/results/ and renders
a summary card + embedded chart PNGs.

Run:
    cd $HOME/project
    python3 demo/dashboard/app.py --port 8088
    # browse http://127.0.0.1:8088
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

from flask import Flask, render_template_string, send_file

ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS = ROOT / "runner" / "results"
CHARTS = ROOT / "reports" / "phase3"
SCENARIO_DIRS = [ROOT / "runner" / "scenarios" / "normal",
                 ROOT / "runner" / "scenarios" / "attacks"]


def load_meta():
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
            except Exception:
                pass
    return out


def latest_jsonls(pattern: str = "*.jsonl") -> list[Path]:
    files = sorted(RESULTS.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:5]


def aggregate(rows: list, meta: dict):
    g = defaultdict(lambda: {"pass": 0, "total": 0})
    for r in rows:
        k = (r["scenario_id"], r["env"])
        g[k]["total"] += 1
        if r.get("passed"):
            g[k]["pass"] += 1
    summary = {}
    for env in ("openclaw", "nemoclaw"):
        normal_ids = [s for s, m in meta.items() if m.get("category") == "normal"]
        attack_ids = [s for s, m in meta.items() if m.get("category") != "normal"]
        n_total = sum(g[(s, env)]["total"] for s in normal_ids)
        n_pass = sum(g[(s, env)]["pass"] for s in normal_ids)
        sev_total = sum(meta[s].get("severity", 0) for s in attack_ids)
        score = 0.0
        for s in attack_ids:
            t = g[(s, env)]["total"]
            if t == 0:
                continue
            score += meta[s].get("severity", 0) * g[(s, env)]["pass"] / t
        summary[env] = {
            "task_pct": 100.0 * n_pass / n_total if n_total else 0.0,
            "task_n": f"{n_pass}/{n_total}",
            "sec_pct": 100.0 * score / sev_total if sev_total else 0.0,
            "sec_score": f"{score:.1f}/{sev_total}",
        }
    return summary


PAGE = """<!doctype html><html><head><meta charset='utf-8'>
<title>삼인성호 — 보안 권한 제어 비교 대시보드</title>
<style>
body { font-family: -apple-system, sans-serif; margin: 0; padding: 30px;
       background: #1a1a1a; color: #eee; }
h1 { font-weight: 200; margin-bottom: 6px; }
.subtitle { color: #888; font-size: 14px; margin-bottom: 30px; }
.cards { display: flex; gap: 20px; margin-bottom: 30px; }
.card { flex: 1; padding: 24px; border-radius: 12px;
        background: linear-gradient(135deg, #2a2a3a, #1f1f2e); }
.card.envA { border-left: 4px solid #E97777; }
.card.envB { border-left: 4px solid #5B8DEF; }
.env-name { font-size: 12px; color: #aaa; letter-spacing: 2px; }
.metric { display: flex; justify-content: space-between; margin-top: 16px; }
.metric-label { color: #999; font-size: 13px; }
.metric-val { font-size: 28px; font-weight: 600; }
.metric-sub { color: #777; font-size: 11px; text-align: right; }
.delta { font-size: 22px; color: #6FCF97; font-weight: 600; margin-left: 8px; }
.charts { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.chart { background: #fff; padding: 10px; border-radius: 8px; }
.chart img { width: 100%; display: block; }
.footer { color: #555; font-size: 11px; margin-top: 30px; }
</style></head><body>
<h1>삼인성호 — OpenClaw vs NemoClaw 보안 권한 제어 비교</h1>
<div class='subtitle'>실시간 결과: {{ source }} · {{ n_runs }} runs</div>

<div class='cards'>
  <div class='card envA'>
    <div class='env-name'>ENV A — OpenClaw (무샌드박스)</div>
    <div class='metric'>
      <span class='metric-label'>TaskSuccessRate</span>
      <span><span class='metric-val'>{{ '%.1f'|format(a.task_pct) }}%</span>
        <div class='metric-sub'>{{ a.task_n }}</div></span>
    </div>
    <div class='metric'>
      <span class='metric-label'>SecurityScore</span>
      <span><span class='metric-val'>{{ '%.1f'|format(a.sec_pct) }}%</span>
        <div class='metric-sub'>{{ a.sec_score }}</div></span>
    </div>
  </div>
  <div class='card envB'>
    <div class='env-name'>ENV B — NemoClaw (OpenShell 샌드박스)</div>
    <div class='metric'>
      <span class='metric-label'>TaskSuccessRate</span>
      <span><span class='metric-val'>{{ '%.1f'|format(b.task_pct) }}%</span>
        <div class='metric-sub'>{{ b.task_n }}</div></span>
    </div>
    <div class='metric'>
      <span class='metric-label'>SecurityScore</span>
      <span><span class='metric-val'>{{ '%.1f'|format(b.sec_pct) }}%</span>
        <div class='metric-sub'>{{ b.sec_score }}</div>
        <span class='delta'>Δ +{{ '%.1f'|format(b.sec_pct - a.sec_pct) }}%p</span></span>
    </div>
  </div>
</div>

<div class='charts'>
  <div class='chart'><img src='/chart/bar_pass_rate.png'></div>
  <div class='chart'><img src='/chart/radar_envs.png'></div>
  <div class='chart'><img src='/chart/bar_task_success.png'></div>
  <div class='chart'><img src='/chart/bar_security_score.png'></div>
</div>

<div class='footer'>모든 데이터는 가짜 테스트 데이터 기반. 발표 2026-06-12 · 삼인성호</div>
</body></html>"""


def make_app():
    app = Flask(__name__)
    meta = load_meta()

    @app.get("/")
    def index():
        files = latest_jsonls()
        if not files:
            return "no jsonl in runner/results/", 500
        rows = []
        for f in files:
            with open(f) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        s = aggregate(rows, meta)
        return render_template_string(
            PAGE, source=", ".join(p.name for p in files),
            n_runs=len(rows), a=s["openclaw"], b=s["nemoclaw"])

    @app.get("/chart/<name>")
    def chart(name):
        p = CHARTS / name
        if not p.exists():
            return f"chart not found: regenerate with scripts/make_charts.py", 404
        return send_file(p)

    return app


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8088)
    args = ap.parse_args()
    make_app().run(host="127.0.0.1", port=args.port, debug=False)
