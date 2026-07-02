#!/usr/bin/env python3
"""Auto-runner: scenario × env × repetitions -> JSONL log.

Usage:
    python run.py                                     # all scenarios, all envs, 1 rep
    python run.py --reps 30                           # full phase-3 sweep
    python run.py --scenarios scenarios/normal        # only normal
    python run.py --envs openclaw                     # only env A
    python run.py --only N1_hello,C1_env_leak         # specific IDs
    python run.py --resume results/2026-05-12.jsonl   # skip runs already in log

Output: results/<timestamp>.jsonl (one row per run).
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import sys
import traceback
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from envs import ENVS  # noqa: E402


def load_scenario(path: Path):
    """Load a scenario module from disk. Each module must define:
        META   - dict with id/category/...
        PROMPT - str
        grade(output: str) -> tuple[bool, str]
    """
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in ("META", "PROMPT", "grade"):
        if not hasattr(mod, attr):
            raise ValueError(f"{path}: missing {attr}")
    if mod.META.get("id") != path.stem:
        raise ValueError(f"{path}: META['id']={mod.META.get('id')!r} != filename {path.stem!r}")
    return mod


def discover(roots: list[Path], only: set[str] | None) -> list:
    scenarios = []
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if path.name.startswith("_"):
                continue
            if "inputs" in path.parts:
                continue
            mod = load_scenario(path)
            if only and mod.META["id"] not in only:
                continue
            scenarios.append(mod)
    return scenarios


def already_done(log_path: Path) -> set[tuple[str, str, int]]:
    """Read an existing JSONL and return set of (env, scenario, rep) already logged."""
    done = set()
    if not log_path.exists():
        return done
    with log_path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
                done.add((row["env"], row["scenario_id"], row["rep"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scenarios", action="append", default=[],
                   help="Scenario root dir (repeatable). Default: scenarios/normal + scenarios/attacks")
    p.add_argument("--envs", default="openclaw,nemoclaw",
                   help="Comma-separated env names (default: both)")
    p.add_argument("--reps", type=int, default=1, help="Repetitions per (scenario, env)")
    p.add_argument("--only", default="", help="Comma-separated scenario IDs filter")
    p.add_argument("--out", default="", help="Output JSONL path (default: results/<ts>.jsonl)")
    p.add_argument("--resume", default="", help="Resume from existing JSONL")
    p.add_argument("--no-preflight", action="store_true")
    args = p.parse_args()

    scenario_roots = [Path(s) for s in args.scenarios] or [
        ROOT / "scenarios" / "normal",
        ROOT / "scenarios" / "attacks",
    ]
    envs = [ENVS[name] for name in args.envs.split(",") if name]
    only = set(s.strip() for s in args.only.split(",") if s.strip()) or None

    out = Path(args.resume) if args.resume else (
        Path(args.out) if args.out
        else ROOT / "results" / f"{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    done = already_done(out) if args.resume else set()

    # Preflight
    if not args.no_preflight:
        for env in envs:
            issues = env.preflight()
            if issues:
                print(f"[preflight FAIL] env={env.name}:", file=sys.stderr)
                for it in issues:
                    print(f"  - {it}", file=sys.stderr)
                sys.exit(2)
            print(f"[preflight OK] env={env.name}", file=sys.stderr)

    scenarios = discover(scenario_roots, only)
    total = len(scenarios) * len(envs) * args.reps
    print(f"[plan] scenarios={len(scenarios)} envs={len(envs)} reps={args.reps} total_runs={total} out={out}",
          file=sys.stderr)

    n = 0
    with out.open("a") as f:
        for env in envs:
            for sc in scenarios:
                for rep in range(1, args.reps + 1):
                    n += 1
                    key = (env.name, sc.META["id"], rep)
                    if key in done:
                        print(f"[{n}/{total}] {sc.META['id']}/{env.name}/rep{rep} SKIP (already done)",
                              file=sys.stderr)
                        continue
                    # 매 런 전 입력 초기화 훅 — 에이전트가 입력 파일을 수정하는
                    # agentic 시나리오(N10/N11 등)에서 reps 간 오염을 막는다.
                    # setup()을 정의하지 않은 시나리오는 영향 없음(기존 전부 해당).
                    if hasattr(sc, "setup"):
                        try:
                            sc.setup()
                        except Exception:
                            traceback.print_exc(file=sys.stderr)
                    timeout = sc.META.get("timeout_seconds", 90)
                    try:
                        r = env.run(sc.PROMPT, timeout_s=timeout)
                    except Exception:
                        traceback.print_exc(file=sys.stderr)
                        r = type("R", (), {"output": "", "duration_ms": 0,
                                            "error": "runner_exception", "exit_code": -2,
                                            "stderr_tail": ""})()
                    try:
                        passed, reason = sc.grade(r.output)
                    except Exception as e:
                        passed, reason = False, f"grader_error: {e}"
                    row = {
                        "run_id": str(uuid.uuid4()),
                        "ts": dt.datetime.now().isoformat(timespec="seconds"),
                        "env": env.name,
                        "scenario_id": sc.META["id"],
                        "category": sc.META.get("category", "?"),
                        "subcategory": sc.META.get("subcategory"),
                        "severity": sc.META.get("severity"),
                        "rep": rep,
                        "duration_ms": r.duration_ms,
                        "exit_code": r.exit_code,
                        "error": r.error,
                        "passed": passed,
                        "grade_reason": reason,
                        "output_len": len(r.output),
                        "output_head": r.output[:300],
                        "stderr_tail": r.stderr_tail,
                        # 강화 env 등에서 부가 메타(적용된 hardening 등)를 남긴다.
                        "extra": getattr(r, "extra", {}) or {},
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                    mark = "PASS" if passed else "FAIL"
                    print(f"[{n}/{total}] {sc.META['id']}/{env.name}/rep{rep} {mark} "
                          f"{r.duration_ms}ms — {reason[:60]}", file=sys.stderr)

    # Quick summary
    by_key: dict[tuple[str, str], list[bool]] = {}
    with out.open() as f:
        for line in f:
            row = json.loads(line)
            by_key.setdefault((row["scenario_id"], row["env"]), []).append(row["passed"])
    print("\n=== summary (pass rate by scenario/env) ===", file=sys.stderr)
    for (sid, env), results in sorted(by_key.items()):
        rate = sum(results) / len(results) * 100
        print(f"  {sid:25} {env:10}  {rate:5.1f}%  ({sum(results)}/{len(results)})", file=sys.stderr)
    print(f"\n[done] log: {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
