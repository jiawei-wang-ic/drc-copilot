#!/usr/bin/python3
"""Score a DRC Copilot run against the injected ground truth.

    /usr/bin/python3 tools/evaluate.py --lyrdb work/bench.lyrdb --truth work/bench_truth.json \
        --run out/bench_glm.json --out out/eval.md

Reports, each with its own denominator:
  1. detection   — violating sites flagged by the official deck; controls (at-limit, legal) flagged
  2. triage      — markers -> rule groups
  3. retrieval   — does the retrieved manual rule equal the site's ground-truth rule?
                   compared with a naive baseline (id lookup only, no type-consistency check)
  4. explanation — model answer parsed; quotes the limit; quotes the worst measured value; self-reported grounded
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from drc_copilot import lyrdb, rules  # noqa: E402

NUM = re.compile(r"-?\d+(?:\.\d+)?")


def marker_points(values):
    pts = []
    for v in values:
        nums = [float(x) for x in NUM.findall(v.split(":", 1)[-1])]
        pts += list(zip(nums[0::2], nums[1::2]))
    return pts


def inside(p, bb, eps=0.02):
    return bb[0] - eps <= p[0] <= bb[2] + eps and bb[1] - eps <= p[1] <= bb[3] + eps


def naive_retrieve(index, rule_id):
    for cand in rules.candidates(rule_id):
        hits = index.exact(cand)
        if hits:
            return hits[0].rule_id
    return None


def mentions(text, value):
    if value is None:
        return None
    forms = {f"{value:g}", f"{value:.2f}", f"{value:.3f}", f"{value:.4f}".rstrip("0").rstrip(".")}
    return any(f in (text or "") for f in forms)


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.1f}%)" if b else f"{a}/0"


RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data/sky130_periphery_rules.csv")


def score(lyrdb_path, truth_path, run_path, rules_path=RULES):
    """Returns (metrics dict, markdown text)."""
    rep = lyrdb.parse(lyrdb_path)
    truth = json.load(open(truth_path))
    sites = truth["sites"]
    run = json.load(open(run_path))
    index = rules.RuleIndex(rules.load(rules_path))

    # 1. detection: match every marker to the site whose box contains it (same cell)
    hits_by_site = defaultdict(list)
    unmatched = 0
    by_cell = defaultdict(list)
    for s in sites:
        by_cell[s["cell"]].append(s)
    for v in rep.violations:
        pts = marker_points(v.values)
        site = next((s for s in by_cell.get(v.cell, []) if pts and any(inside(p, s["bbox_um"]) for p in pts)), None)
        if site is None:
            unmatched += 1
        else:
            hits_by_site[site["id"]].append(v.rule)
    violating = [s for s in sites if not s["control"]]
    controls = [s for s in sites if s["control"]]
    detected = sum(1 for s in violating if hits_by_site.get(s["id"]))
    false_pos = sum(1 for s in controls if hits_by_site.get(s["id"]))

    # 3. retrieval: ground-truth rule per deck rule = majority expected rule of the sites it flagged
    truth_of_rule = defaultdict(Counter)
    for s in violating:
        for r in hits_by_site.get(s["id"], []):
            truth_of_rule[r][s["expected_rule"]] += 1
    groups = run["groups"]
    ret_ok = ret_naive_ok = 0
    ret_rows = []
    for g in groups:
        expected = truth_of_rule[g["rule"]].most_common(1)[0][0] if truth_of_rule[g["rule"]] else None
        got = g["retrieved"][0] if g["retrieved"] else None
        naive = naive_retrieve(index, g["rule"])
        ret_ok += got == expected
        ret_naive_ok += naive == expected
        ret_rows.append((g["rule"], expected, got, g["retrieval"], naive))

    # 4. explanation checks (only groups the model was asked about)
    asked = [g for g in groups if g["explanation"] is not None]
    parsed = [g for g in asked if not g["explanation"]["error"]]
    with_limit = [g for g in parsed if g["limit"] is not None]
    lim_ok = sum(1 for g in with_limit if mentions(g["explanation"]["what"], g["limit"]))
    worst_ok = sum(1 for g in with_limit if mentions(g["explanation"]["what"], g["worst"]))
    grounded = sum(1 for g in parsed if g["explanation"]["grounded"] is True)

    lines = [
        "# DRC Copilot — evaluation",
        "",
        f"- Benchmark: `{os.path.basename(truth_path)}` (seed {truth.get('seed')}), "
        f"run: `{os.path.basename(run_path)}` ({run.get('seconds')} s)",
        "",
        "## 1. Detection (official SKY130 KLayout deck)",
        f"- Violating sites flagged: **{pct(detected, len(violating))}**",
        f"- At-limit legal controls flagged (false positives): **{pct(false_pos, len(controls))}**",
        f"- Markers not matched to any injected site: {unmatched}",
        "",
        "## 2. Triage",
        f"- {len(rep.violations)} markers -> **{len(groups)} rule groups**",
        "",
        "## 3. Rule-text retrieval (top-1 manual rule == ground truth)",
        f"- DRC Copilot (id normalization + type-consistency check): **{pct(ret_ok, len(groups))}**",
        f"- Naive baseline (id lookup only): {pct(ret_naive_ok, len(groups))}",
        "",
        "| Deck rule | Ground truth | Retrieved | How | Naive |",
        "|---|---|---|---|---|",
    ] + [f"| `{a}` | `{b}` | `{c}` | {d} | `{e}` |" for a, b, c, d, e in ret_rows] + [
        "",
        "## 4. Model explanations",
        f"- Groups sent to the model: {len(asked)}; valid JSON answers: **{pct(len(parsed), len(asked))}**",
        f"- Quote the correct limit: **{pct(lim_ok, len(with_limit))}** · quote the worst measured value: "
        f"**{pct(worst_ok, len(with_limit))}** (groups with a numeric limit)",
        f"- Self-reported grounded in the retrieved text: {pct(grounded, len(parsed))}",
    ]
    text = "\n".join(lines) + "\n"
    metrics = {
        "markers": len(rep.violations), "groups": len(groups), "seconds": run.get("seconds"),
        "sites": len(violating), "detected": detected, "controls": len(controls), "false_pos": false_pos,
        "retrieval_ok": ret_ok, "retrieval_naive_ok": ret_naive_ok,
        "asked": len(asked), "parsed": len(parsed), "with_limit": len(with_limit),
        "limit_ok": lim_ok, "worst_ok": worst_ok, "grounded": grounded,
        "expected_rule": {a: b for a, b, c, d, e in ret_rows},
    }
    return metrics, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lyrdb", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--run", required=True, help="JSON written by run.py")
    ap.add_argument("--rules", default=RULES)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    _, text = score(args.lyrdb, args.truth, args.run, args.rules)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
