#!/usr/bin/python3
"""Score a simulation-log triage run against the seeded-bug ground truth.

    /usr/bin/python3 tools/evaluate_sim.py --truth work/sim/sim_truth.json --run out/sim_report.json
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from drc_copilot import simlog  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.1f}%)" if b else f"{a}/0"


def score(truth_path, run_path):
    truth = json.load(open(truth_path))
    run = json.load(open(run_path))
    builds = {b["build"]: b for b in truth["builds"]}
    logs = sorted(glob.glob(os.path.join(ROOT, "work/sim/logs/*.log")))
    runs = [simlog.parse(p) for p in logs]

    clean = [r for r in runs if builds[r.build]["bug"] is None]
    buggy = [r for r in runs if builds[r.build]["bug"] is not None]
    false_fail = sum(r.status != "PASS" for r in clean)
    caught = sum(r.status != "PASS" for r in buggy)
    bug_builds = [b for b in builds.values() if b["bug"]]
    detected_builds = {r.build for r in buggy if r.status != "PASS"}

    _, g_first = simlog.triage(logs, root=ROOT, mode="first")
    _, g_set = simlog.triage(logs, root=ROOT, mode="set")

    groups = run["groups"]
    in_ctx = sum(builds[g["build"]]["bug"]["line"] in g["context_lines"] for g in groups)
    ctx_sizes = [len(g["context_lines"]) for g in groups]
    base_ok = sum(g["baseline_line"] == builds[g["build"]]["bug"]["line"] for g in groups)
    asked = [g for g in groups if g["explanation"] is not None]
    parsed = [g for g in asked if not g["explanation"]["error"]]
    model_ok = sum(g["explanation"]["suspect_line"] == builds[g["build"]]["bug"]["line"] for g in parsed)

    def by_kind(pred):
        out = {}
        for g in groups:
            k = "compile error" if g["status"] == "COMPILE_ERROR" else "functional"
            out.setdefault(k, [0, 0])
            out[k][1] += 1
            out[k][0] += pred(g)
        return out

    base_kind = by_kind(lambda g: g["baseline_line"] == builds[g["build"]]["bug"]["line"])
    model_kind = by_kind(lambda g: bool(g["explanation"]) and not g["explanation"]["error"]
                         and g["explanation"]["suspect_line"] == builds[g["build"]]["bug"]["line"])

    lines = [
        "# Simulation-log triage — evaluation", "",
        f"- Benchmark: {len(bug_builds)} builds with one seeded bug + {len(builds) - len(bug_builds)} clean builds, "
        f"{len(truth['seeds'])} seeds each = {len(runs)} runs",
        "",
        "## 1. Regression (testbench quality, not this tool)",
        f"- Clean runs reported as failing: **{pct(false_fail, len(clean))}**",
        f"- Buggy runs caught: {pct(caught, len(buggy))} · bugs caught: {pct(len(detected_builds), len(bug_builds))}",
        "",
        "## 2. Grouping",
        f"- {caught} failing runs -> **{len(g_first)} groups** by first symptom "
        f"(vs {len(g_set)} if grouped by the full set of mismatching signals)",
        f"- Builds split into more than one group: {sum(1 for b in detected_builds if sum(g.build == b for g in g_first) > 1)} "
        f"(first symptom) vs {sum(1 for b in detected_builds if sum(g.build == b for g in g_set) > 1)} (full set)",
        "",
        "## 3. Candidate RTL lines (retrieval)",
        f"- True bug line among the candidates: **{pct(in_ctx, len(groups))}** · "
        f"candidates per group: {min(ctx_sizes)}–{max(ctx_sizes)} (mean {sum(ctx_sizes) / len(ctx_sizes):.1f})",
        "",
        "## 4. Localisation (top-1 line == seeded bug line)",
        f"- Baseline without a model: **{pct(base_ok, len(groups))}** — "
        + " · ".join(f"{k} {v[0]}/{v[1]}" for k, v in base_kind.items()),
    ]
    if asked:
        lines.append(f"- GLM: **{pct(model_ok, len(groups))}** — "
                     + " · ".join(f"{k} {v[0]}/{v[1]}" for k, v in model_kind.items())
                     + f" (valid JSON {len(parsed)}/{len(asked)})")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", default=os.path.join(ROOT, "work/sim/sim_truth.json"))
    ap.add_argument("--run", default=os.path.join(ROOT, "out/sim_report.json"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    text = score(a.truth, a.run)
    print(text)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)


if __name__ == "__main__":
    main()
