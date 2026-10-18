"""Build a self-contained HTML report (index.html + img/) from a DRC Copilot run.

    /usr/bin/python3 -m drc_copilot.site --gds work/bench.gds --lyrdb work/bench.lyrdb \
        --run out/bench_glm.json [--truth work/bench_truth.json] --out out/site
"""
import argparse
import json
import os
import re
import sys

from . import group, lyrdb, measure, rules
from .snapshot import Snapshotter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(HERE, "site_template.html")


def safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def build(gds, lyrdb_path, run_path, out_dir, truth_path=None, top="TOP"):
    rep = lyrdb.parse(lyrdb_path)
    groups = {g.rule: g for g in group.group(rep)}
    run = json.load(open(run_path))
    index = rules.RuleIndex(rules.load(os.path.join(ROOT, "data/sky130_periphery_rules.csv")))
    img_dir = os.path.join(out_dir, "img")
    os.makedirs(img_dir, exist_ok=True)

    snap = Snapshotter(gds, top)
    snap.overview(os.path.join(img_dir, "overview.png"))

    metrics = None
    if truth_path and os.path.exists(truth_path):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from evaluate import score  # noqa: E402
        metrics, _ = score(lyrdb_path, truth_path, run_path)

    items = []
    for rg in run["groups"]:
        g = groups.get(rg["rule"])
        hits, how = index.retrieve(rg["rule"], rg["description"])
        img = None
        cands = [v for v in rep.violations if v.rule == rg["rule"] and v.values]
        if cands:
            # show the worst marker, so the picture matches the "worst measured" number
            def size(v):
                m = measure.measure(v.values[0])
                return m[1] if m else float("inf")
            s = min(cands, key=size)
            img = snap.render(s.cell, s.values[0], os.path.join(img_dir, safe(rg["rule"]) + ".png"))
        expected = (metrics or {}).get("expected_rule", {}).get(rg["rule"])
        items.append({
            **rg,
            "rule_text": [r.as_context() for r in hits],
            "snapshot": f"img/{os.path.basename(img)}" if img else None,
            "expected": expected,
            "retrieval_ok": (expected == rg["retrieved"][0]) if expected and rg["retrieved"] else None,
        })

    data = {
        "source": os.path.basename(lyrdb_path),
        "violations": run["violations"],
        "seconds": run.get("seconds"),
        "model": os.environ.get("GLM_MODEL", "glm-5.3-flash"),
        "metrics": metrics,
        "seed": json.load(open(truth_path)).get("seed") if truth_path and os.path.exists(truth_path) else None,
        "groups": items,
    }
    page = open(TEMPLATE, encoding="utf-8").read()
    page = page.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    return os.path.join(out_dir, "index.html")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gds", required=True)
    ap.add_argument("--lyrdb", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--truth", default=None)
    ap.add_argument("--out", default=os.path.join(ROOT, "out/site"))
    a = ap.parse_args()
    print(build(a.gds, a.lyrdb, a.run, a.out, a.truth))


if __name__ == "__main__":
    main()
