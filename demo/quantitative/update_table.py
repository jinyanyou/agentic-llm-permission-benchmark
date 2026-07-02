#!/usr/bin/env python3
"""Fill <TBD> cells in demo/quantitative/index.html from latest JSONL.

Usage:
    python3 demo/quantitative/update_table.py \
        --jsonl runner/results/mini_reps3_20260519.jsonl

Replaces <TBD> placeholders in the HTML with computed PASS rates and
metrics. Safe to re-run — uses placeholder markers, not numeric matching.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HTML_PATH = ROOT / "demo" / "quantitative" / "index.html"


def load_meta():
    out = {}
    for sdir in [ROOT / "runner" / "scenarios" / "normal",
                 ROOT / "runner" / "scenarios" / "attacks"]:
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", action="append", default=[])
    args = ap.parse_args()

    patterns = args.jsonl or [str(ROOT / "runner" / "results" / "*.jsonl")]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    rows = []
    for f in sorted(set(files)):
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    meta = load_meta()
    g = defaultdict(lambda: {"pass": 0, "total": 0})
    for r in rows:
        k = (r["scenario_id"], r["env"])
        g[k]["total"] += 1
        if r.get("passed"):
            g[k]["pass"] += 1

    html = HTML_PATH.read_text()

    # Replace scenario row TBDs in order (envA, envB)
    scen_order = ["N4_summarize_intro", "N5_write_report", "N6_code_review",
                  "N7_extract_actions", "N8_hotel_site",
                  "C_direct", "C_indirect", "C_role", "C_urgency", "C_mixed"]
    for sid in scen_order:
        for env in ("openclaw", "nemoclaw"):
            cell = g[(sid, env)]
            txt = f"{cell['pass']}/{cell['total']}" if cell["total"] else "—"
            html = html.replace("&lt;TBD&gt;", txt, 1)

    # Summary table: TaskSuccessRate / SecurityScore
    def task_pct(env):
        ids = [s for s, m in meta.items() if m.get("category") == "normal"]
        t = sum(g[(s, env)]["total"] for s in ids)
        p = sum(g[(s, env)]["pass"] for s in ids)
        return f"{100.0 * p / t:.1f}%" if t else "—"

    def sec_pct(env):
        ids = [s for s, m in meta.items() if m.get("category") != "normal"]
        sev_total = sum(meta[s].get("severity", 0) for s in ids)
        score = 0.0
        for s in ids:
            t = g[(s, env)]["total"]
            if t == 0:
                continue
            score += meta[s].get("severity", 0) * g[(s, env)]["pass"] / t
        return f"{100.0 * score / sev_total:.1f}%" if sev_total else "—"

    # Note: scenario rows replace 20 TBDs first; remaining ~4-5 are summary
    html = html.replace("&lt;TBD&gt;", task_pct("openclaw"), 1)
    html = html.replace("&lt;TBD&gt;", task_pct("nemoclaw"), 1)
    html = html.replace("&lt;TBD&gt;", sec_pct("openclaw"), 1)
    html = html.replace("&lt;TBD&gt;", sec_pct("nemoclaw"), 1)
    html = html.replace("&lt;TBD&gt;", "측정 중", 1)  # Overhead env B

    HTML_PATH.write_text(html)
    print(f"[done] updated {HTML_PATH} from {len(rows)} rows")


if __name__ == "__main__":
    main()
