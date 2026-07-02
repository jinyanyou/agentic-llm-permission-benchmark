#!/usr/bin/env python3
"""Analyze runner JSONL log(s) and produce the 3-axis project metrics.

Usage:
    python analyze.py                          # auto-scan results/*.jsonl, combined
    python analyze.py results/20260512_*.jsonl # explicit files
    python analyze.py --csv summary.csv        # also dump CSV
    python analyze.py --by-env-only            # skip category breakdown

Outputs to stdout:
    1. Per-(scenario, env) pass rate + mean duration ± stddev
    2. Aggregate: SecurityScore (Σ severity × defense), TaskSuccessRate, Overhead
    3. By attack subcategory: pass rate per env

Scenario metadata (severity, subcategory) is loaded from scenarios/ on disk and
joined with log rows on scenario_id.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent


def load_scenarios() -> dict:
    """Map scenario_id -> META dict."""
    out = {}
    for sdir in [ROOT / "scenarios" / "normal", ROOT / "scenarios" / "attacks"]:
        if not sdir.exists():
            continue
        for p in sdir.glob("*.py"):
            if p.name.startswith("_"):
                continue
            spec = importlib.util.spec_from_file_location(p.stem, p)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                out[mod.META["id"]] = mod.META
            except Exception as e:
                print(f"[warn] failed to load {p}: {e}", file=sys.stderr)
    return out


def load_rows(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        with p.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def stat_pct(values: list[bool]) -> tuple[float, int, int]:
    """Return (pct, passed, total)."""
    if not values:
        return 0.0, 0, 0
    return sum(values) / len(values) * 100, sum(values), len(values)


def stat_ms(values: list[int]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return float(values[0]), 0.0
    return statistics.mean(values), statistics.stdev(values)


def fmt_dur(ms: float) -> str:
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [len(h) for h in headers]
    for r in rows:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(str(c)))
    sep = "  "
    lines = [sep.join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append(sep.join("-" * widths[i] for i in range(len(headers))))
    for r in rows:
        lines.append(sep.join(str(c).ljust(widths[i]) for i, c in enumerate(r)))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="JSONL files. Default: results/*.jsonl")
    ap.add_argument("--csv", help="Also export per-scenario summary to CSV")
    ap.add_argument("--md", help="Also export markdown tables (for paste-into-report)")
    ap.add_argument("--by-env-only", action="store_true")
    args = ap.parse_args()

    paths = [Path(f) for f in args.files] if args.files else sorted((ROOT / "results").glob("*.jsonl"))
    if not paths:
        print("No JSONL files found.", file=sys.stderr)
        sys.exit(1)
    print(f"# Analyzing {len(paths)} file(s):", file=sys.stderr)
    for p in paths:
        print(f"#   {p}", file=sys.stderr)

    rows = load_rows(paths)
    if not rows:
        print("No rows loaded.", file=sys.stderr)
        sys.exit(1)

    scenarios = load_scenarios()

    # ── 1. Per (scenario, env) ────────────────────────────────────────
    by_se: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_se[(r["scenario_id"], r["env"])].append(r)

    # Fixed env order: env A (baseline) before env B (treatment).
    # Δ metrics are computed as (B − A), so positive = NemoClaw improvement.
    preferred = ["openclaw", "nemoclaw", "openclaw-infer", "nemoclaw-infer"]
    found = set(r["env"] for r in rows)
    envs = [e for e in preferred if e in found] + sorted(found - set(preferred))
    scenario_ids = sorted({r["scenario_id"] for r in rows})

    print()
    print("=" * 70)
    print(" 1. Per-scenario pass rate × mean duration")
    print("=" * 70)
    header = ["scenario", "cat", "sev"]
    for env in envs:
        header += [f"{env}_pass", f"{env}_dur"]
    if len(envs) == 2:
        header += ["Δ pass"]
    tbl_rows = []
    for sid in scenario_ids:
        meta = scenarios.get(sid, {})
        cat = meta.get("category", "?")
        sev = str(meta.get("severity", "—"))
        row = [sid, cat, sev]
        env_pcts = {}
        for env in envs:
            results = by_se.get((sid, env), [])
            passed_list = [r["passed"] for r in results]
            dur_list = [r["duration_ms"] for r in results]
            pct, n_pass, n = stat_pct(passed_list)
            mean, sd = stat_ms(dur_list)
            env_pcts[env] = pct
            dur_str = f"{fmt_dur(mean)}" + (f"±{fmt_dur(sd)}" if sd else "")
            row += [f"{pct:5.1f}% ({n_pass}/{n})", dur_str]
        if len(envs) == 2:
            d = env_pcts[envs[1]] - env_pcts[envs[0]]
            row += [f"{d:+.1f}%"]
        tbl_rows.append(row)
    print(table(tbl_rows, header))

    # ── 2. Aggregate metrics ──────────────────────────────────────────
    print()
    print("=" * 70)
    print(" 2. Aggregate metrics")
    print("=" * 70)

    # SecurityScore: sum of (severity * defended) over attack scenarios
    print("\n[SecurityScore = Σ severity × defense, attacks only]")
    sec_rows = []
    for env in envs:
        attack_rows = [r for r in rows
                       if r["env"] == env
                       and scenarios.get(r["scenario_id"], {}).get("category") == "attack"]
        # average over reps: per-scenario defense fraction × severity
        score = 0.0
        max_score = 0.0
        per_sc: dict[str, list[bool]] = defaultdict(list)
        for r in attack_rows:
            per_sc[r["scenario_id"]].append(r["passed"])
        for sid, passes in per_sc.items():
            sev = scenarios.get(sid, {}).get("severity", 1)
            defense_rate = sum(passes) / len(passes)
            score += sev * defense_rate
            max_score += sev
        pct = (score / max_score * 100) if max_score else 0
        sec_rows.append([env, f"{score:.2f}", f"{max_score:.0f}", f"{pct:.1f}%"])
    print(table(sec_rows, ["env", "score", "max", "%"]))
    if len(envs) == 2:
        a_score = float(sec_rows[0][1]); b_score = float(sec_rows[1][1])
        max_s = float(sec_rows[0][2])
        delta = (b_score - a_score) / max_s * 100 if max_s else 0
        sign = "improvement" if delta > 0 else ("regression" if delta < 0 else "no change")
        print(f"  Δ SecurityScore = {delta:+.1f} %p   ({envs[1]} − {envs[0]} → {sign})")

    # Normal task success
    print("\n[TaskSuccessRate, normal scenarios only]")
    normal_rows = []
    for env in envs:
        normal = [r for r in rows
                  if r["env"] == env
                  and scenarios.get(r["scenario_id"], {}).get("category") == "normal"]
        pct, n_pass, n = stat_pct([r["passed"] for r in normal])
        normal_rows.append([env, f"{pct:.1f}%", f"{n_pass}/{n}"])
    print(table(normal_rows, ["env", "rate", "passed/total"]))

    # Performance overhead
    print("\n[Performance overhead = T_B / T_A − 1, all scenarios]")
    if len(envs) == 2:
        # match by scenario for fair comparison
        a_durs, b_durs = [], []
        for sid in scenario_ids:
            a = [r["duration_ms"] for r in by_se.get((sid, envs[0]), [])]
            b = [r["duration_ms"] for r in by_se.get((sid, envs[1]), [])]
            if a and b:
                a_durs.append(statistics.mean(a))
                b_durs.append(statistics.mean(b))
        if a_durs and b_durs:
            t_a = statistics.mean(a_durs)
            t_b = statistics.mean(b_durs)
            overhead = (t_b - t_a) / t_a * 100
            sign = "slower" if overhead > 0 else ("faster" if overhead < 0 else "equal")
            print(f"  T_{envs[0]} (baseline) = {fmt_dur(t_a)}")
            print(f"  T_{envs[1]} (treatment) = {fmt_dur(t_b)}")
            print(f"  overhead = {overhead:+.1f}%   ({envs[1]} is {abs(overhead):.1f}% {sign} than {envs[0]})")
        else:
            print("  (not enough paired data)")

    # ── 3. By attack subcategory ──────────────────────────────────────
    if not args.by_env_only:
        print()
        print("=" * 70)
        print(" 3. By attack subcategory")
        print("=" * 70)
        sub_rows = []
        seen_subs: list[str] = []
        for sid in scenario_ids:
            meta = scenarios.get(sid, {})
            if meta.get("category") != "attack":
                continue
            sub = meta.get("subcategory", "?")
            if sub not in seen_subs:
                seen_subs.append(sub)
        for sub in seen_subs:
            row = [sub]
            for env in envs:
                vals = []
                for r in rows:
                    if r["env"] != env:
                        continue
                    if scenarios.get(r["scenario_id"], {}).get("subcategory") != sub:
                        continue
                    vals.append(r["passed"])
                pct, p, n = stat_pct(vals)
                row.append(f"{pct:5.1f}% ({p}/{n})")
            sub_rows.append(row)
        print(table(sub_rows, ["subcategory"] + envs))

    # ── CSV export ────────────────────────────────────────────────────
    # ── Markdown export ──────────────────────────────────────────────
    if args.md:
        out = Path(args.md)
        lines = []
        lines.append("## 표 1 — 시나리오별 차단률 × 평균 소요시간\n")
        lines.append("| 시나리오 | 카테고리 | 가중치 | " + " | ".join(envs)
                     + " 차단률 | " + envs[-1] + " 평균 | Δ |"
                     if len(envs) == 2
                     else "| 시나리오 | 카테고리 | 가중치 | " + " | ".join(f"{e} 차단률" for e in envs) + " |")
        # rebuild properly
        lines = [
            "## 표 1 — 시나리오별 차단률 × 평균 소요시간",
            "",
            "| 시나리오 | 카테고리 | 가중치 | " + " | ".join(
                f"{e} 차단률 | {e} 평균(s)" for e in envs
            ) + (" | Δ |" if len(envs) == 2 else " |"),
            "|---|---|---|" + "|".join(["---|---"] * len(envs)) + ("|---|" if len(envs) == 2 else "|"),
        ]
        for sid in scenario_ids:
            meta = scenarios.get(sid, {})
            cat = meta.get("category", "?")
            sev = str(meta.get("severity", "—"))
            cells = [sid, cat, sev]
            env_pcts = {}
            for env in envs:
                results = by_se.get((sid, env), [])
                passed_list = [r["passed"] for r in results]
                dur_list = [r["duration_ms"] for r in results]
                pct, p, n = stat_pct(passed_list)
                mean, _ = stat_ms(dur_list)
                env_pcts[env] = pct
                cells += [f"{pct:.0f}% ({p}/{n})", f"{mean / 1000:.1f}"]
            if len(envs) == 2:
                cells += [f"{env_pcts[envs[1]] - env_pcts[envs[0]]:+.0f}%p"]
            lines.append("| " + " | ".join(cells) + " |")

        lines.append("")
        lines.append("## 표 2 — 합산 지표")
        lines.append("")
        lines.append("| 지표 | " + " | ".join(envs) + " | Δ |")
        lines.append("|---|" + "|".join(["---"] * (len(envs) + 1)) + "|")
        # SecurityScore
        sec_cells = ["SecurityScore (Σ severity × defense, max " + sec_rows[0][2] + ")"]
        for r in sec_rows:
            sec_cells.append(f"{r[1]} ({r[3]})")
        if len(envs) == 2:
            sec_cells.append(f"{(float(sec_rows[1][1]) - float(sec_rows[0][1])) / float(sec_rows[0][2]) * 100:+.1f}%p")
        lines.append("| " + " | ".join(sec_cells) + " |")
        # TaskSuccessRate
        ts_cells = ["TaskSuccessRate (정상)"]
        for nr in normal_rows:
            ts_cells.append(nr[1])
        if len(envs) == 2:
            # crude pct diff
            try:
                a_v = float(normal_rows[0][1].rstrip("%"))
                b_v = float(normal_rows[1][1].rstrip("%"))
                ts_cells.append(f"{b_v - a_v:+.1f}%p")
            except Exception:
                ts_cells.append("—")
        lines.append("| " + " | ".join(ts_cells) + " |")
        out.write_text("\n".join(lines) + "\n")
        print(f"\n[md] wrote {out}", file=sys.stderr)

    if args.csv:
        out = Path(args.csv)
        with out.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["scenario", "category", "subcategory", "severity"]
                       + sum([[f"{e}_pass_n", f"{e}_total", f"{e}_pass_rate", f"{e}_mean_ms"] for e in envs], []))
            for sid in scenario_ids:
                meta = scenarios.get(sid, {})
                cells = [sid, meta.get("category", ""), meta.get("subcategory", ""), meta.get("severity", "")]
                for env in envs:
                    results = by_se.get((sid, env), [])
                    passed = [r["passed"] for r in results]
                    durs = [r["duration_ms"] for r in results]
                    pct, p, n = stat_pct(passed)
                    mean, _ = stat_ms(durs)
                    cells += [p, n, f"{pct:.2f}", f"{mean:.0f}"]
                w.writerow(cells)
        print(f"\n[csv] wrote {out}", file=sys.stderr)

    print()


if __name__ == "__main__":
    main()
