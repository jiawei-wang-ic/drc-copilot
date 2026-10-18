#!/usr/bin/python3
"""Triage a regression of RTL simulation logs.

    /usr/bin/python3 run_sim.py work/sim/logs                 # needs ZHIPUAI_API_KEY in .env
    /usr/bin/python3 run_sim.py work/sim/logs --no-llm        # grouping + candidate lines + baseline only
"""
import argparse
import glob
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from drc_copilot import sim_explain, simlog

HERE = os.path.dirname(os.path.abspath(__file__))


def render(runs, groups, rows) -> str:
    s = simlog.summary(runs)
    lines = ["# Simulation regression triage", "",
             f"- Runs: **{len(runs)}** — " + ", ".join(f"{k} {v}" for k, v in sorted(s.items())),
             f"- Failing runs grouped into **{len(groups)}** failure signatures (build + first symptom)", "",
             "| # | Build | Design | Signature | Runs | Baseline line | Model line |", "|---|---|---|---|---|---|---|"]
    for i, (g, base, ex) in enumerate(rows, 1):
        ml = "—" if ex is None or ex.error else ex.suspect_line
        lines.append(f"| {i} | `{g.build}` | {g.design} | {g.signature} | {g.count} | {base} | {ml} |")
    for i, (g, base, ex) in enumerate(rows, 1):
        r0 = g.runs[0]
        lines += ["", f"## {i}. `{g.build}` · {g.signature}", "",
                  f"**Runs:** {g.count} (seeds {', '.join(r.seed for r in g.runs)})  ",
                  "**Evidence:**", "```", *(r0.evidence or [r0.first_error]), "```",
                  "**Candidate RTL lines:**", "```verilog", *(f"{n:>3}: {l}" for n, l in g.context), "```",
                  f"**Baseline (no model):** line {base}"]
        if ex is None:
            continue
        if ex.error:
            lines.append(f"_Model unavailable: {ex.error}_")
            continue
        lines += [f"**Model suspect line:** {ex.suspect_line}", f"**Hypothesis:** {ex.hypothesis}",
                  f"**Fix:** `{ex.fix}`", f"**Next step:** {ex.next_step}"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logdir")
    ap.add_argument("--out", default=os.path.join(HERE, "out/sim_report.md"))
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--mode", choices=["first", "set"], default="first")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    t0 = time.time()
    runs, groups = simlog.triage(sorted(glob.glob(os.path.join(a.logdir, "*.log"))), root=HERE, mode=a.mode)
    bases = [sim_explain.baseline_line(g, root=HERE) for g in groups]
    exs = [None] * len(groups)
    if not a.no_llm:
        with ThreadPoolExecutor(max_workers=max(1, a.workers)) as pool:
            exs = list(pool.map(sim_explain.explain, groups))
        for g, ex in zip(groups, exs):
            print(f"{g.build}: " + (f"fallback ({ex.error})" if ex.error else f"line {ex.suspect_line}"))
    rows = list(zip(groups, bases, exs))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(render(runs, groups, rows))
    dump = {"runs": len(runs), "summary": simlog.summary(runs), "seconds": round(time.time() - t0, 1),
            "groups": [{"build": g.build, "design": g.design, "status": g.status, "signature": g.signature,
                        "count": g.count, "context_lines": [n for n, _ in g.context], "baseline_line": b,
                        "explanation": None if ex is None else ex.__dict__} for g, b, ex in rows]}
    with open(os.path.splitext(a.out)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=1, ensure_ascii=False)
    print(f"{len(runs)} runs, {len(groups)} groups -> {a.out} ({dump['seconds']} s)")


if __name__ == "__main__":
    main()
