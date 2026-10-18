#!/usr/bin/python3
"""Seeded-bug regression for the simulation-log benchmark.

    /usr/bin/python3 tools/mutate_rtl.py [--seeds 6]
      -> work/sim/logs/<build>__<design>__seed<k>.log  +  work/sim/sim_truth.json

Each "build" is the clean RTL with exactly one known bug (mutation-testing style), plus one clean build per
design as a control. Every build is compiled with Icarus Verilog and its self-checking testbench is run with
several seeds. The ground truth records which file and line the bug is on.
"""
import argparse
import json
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RTL = os.path.join(ROOT, "bench_rtl")
WORK = os.path.join(ROOT, "work", "sim")

# id, design, bug type, exact text to replace (must occur once), replacement, what the bug is
MUTANTS = [
    ("c_rst_val",      "counter", "wrong reset value",   "count <= 4'd0;",                      "count <= 4'd1;",                      "reset loads 1 instead of 0"),
    ("c_wrap_off1",    "counter", "off-by-one",          "(count == 4'd15)",                    "(count == 4'd14)",                    "wrap flag fires one count early"),
    ("c_en_ignored",   "counter", "missing condition",   "else if (en)",                        "else",                                "counter ignores enable"),
    ("c_syntax",       "counter", "syntax error",        "count <= count + 4'd1;",              "count <= count + 4'd1",               "missing semicolon"),
    ("f_full_off1",    "fifo",    "off-by-one",          "(cnt == 3'd4)",                       "(cnt == 3'd3)",                       "full asserted at 3 entries"),
    ("f_rptr_stuck",   "fifo",    "missing update",      "rptr <= rptr + 2'd1;",                "rptr <= rptr;",                       "read pointer never advances"),
    ("f_cnt_dec",      "fifo",    "missing update",      "2'b01: cnt <= cnt - 3'd1;",           "2'b01: cnt <= cnt;",                  "count not decremented on read"),
    ("f_wr_when_full", "fifo",    "missing condition",   "if (wr_en && !full) begin",           "if (wr_en) begin",                    "write accepted when full"),
    ("s_wrong_trans",  "seqdet",  "wrong FSM transition", "S101:    next = din ? S1011 : S10;", "S101:    next = din ? S1011 : S0;",   "S101 on 0 goes to S0, losing the overlap"),
    ("s_no_overlap",   "seqdet",  "wrong FSM transition", "S1011:   next = din ? S1    : S10;", "S1011:   next = din ? S0    : S10;", "S1011 on 1 goes to S0"),
    ("s_hit_state",    "seqdet",  "wrong output decode", "assign hit = (state == S1011);",      "assign hit = (state == S101);",       "hit decoded from the wrong state"),
    ("a_sub_add",      "alu",     "wrong operator",      "3'd1: {carry, y} = {1'b0, a} - {1'b0, b};", "3'd1: {carry, y} = {1'b0, a} + {1'b0, b};", "SUB performs ADD"),
    ("a_and_or",       "alu",     "wrong operator",      "3'd2: y = a & b;",                    "3'd2: y = a | b;",                    "AND performs OR"),
    ("a_carry_lost",   "alu",     "width truncation",    "3'd0: {carry, y} = {1'b0, a} + {1'b0, b};", "3'd0: y = a + b;",              "ADD drops the carry"),
    ("a_syntax",       "alu",     "syntax error",        "assign zero = (y == 8'd0);",          "assign zero = (y == 8'd0)",           "missing semicolon"),
]
DESIGNS = ["counter", "fifo", "seqdet", "alu"]


def apply(src, find, repl):
    assert src.count(find) == 1, f"mutation anchor not unique: {find!r}"
    i = src.index(find)
    line = src[:i].count("\n") + 1
    return src.replace(find, repl), line


def run_build(build, design, rtl_text, seeds, logs_dir):
    bdir = os.path.join(WORK, "builds", build)
    os.makedirs(bdir, exist_ok=True)
    rtl_path = os.path.join(bdir, f"{design}.v")
    with open(rtl_path, "w") as f:
        f.write(rtl_text)
    tb = os.path.join(RTL, f"tb_{design}.v")
    vvp = os.path.join(bdir, f"{design}.vvp")
    comp = subprocess.run(["iverilog", "-g2005", "-o", vvp, rtl_path, tb], capture_output=True, text=True)
    out = []
    for k in seeds:
        log = os.path.join(logs_dir, f"{build}__{design}__seed{k}.log")
        with open(log, "w") as f:
            f.write(f"# build={build} design={design} seed={k}\n")
            f.write(f"# rtl={os.path.relpath(rtl_path, ROOT)}\n")
            if comp.returncode != 0:
                f.write(comp.stdout + comp.stderr)
                f.write("COMPILE FAILED\n")
            else:
                r = subprocess.run(["vvp", "-n", vvp, f"+seed={k}"], capture_output=True, text=True, timeout=60)
                f.write(r.stdout + r.stderr)
        out.append(os.path.relpath(log, ROOT))
    return out, os.path.relpath(rtl_path, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=6)
    args = ap.parse_args()
    seeds = list(range(1, args.seeds + 1))
    logs_dir = os.path.join(WORK, "logs")
    shutil.rmtree(os.path.join(WORK, "builds"), ignore_errors=True)
    shutil.rmtree(logs_dir, ignore_errors=True)
    os.makedirs(logs_dir)

    truth = {"seeds": seeds, "builds": []}
    for d in DESIGNS:   # clean controls
        src = open(os.path.join(RTL, f"{d}.v")).read()
        logs, rtl = run_build(f"clean_{d}", d, src, seeds, logs_dir)
        truth["builds"].append({"build": f"clean_{d}", "design": d, "bug": None, "rtl": rtl, "logs": logs})
    for mid, d, kind, find, repl, desc in MUTANTS:
        src = open(os.path.join(RTL, f"{d}.v")).read()
        mutated, line = apply(src, find, repl)
        logs, rtl = run_build(mid, d, mutated, seeds, logs_dir)
        truth["builds"].append({"build": mid, "design": d, "rtl": rtl, "logs": logs,
                                "bug": {"type": kind, "line": line, "description": desc, "after": repl}})
    with open(os.path.join(WORK, "sim_truth.json"), "w") as f:
        json.dump(truth, f, indent=1)
    n = sum(len(b["logs"]) for b in truth["builds"])
    print(f"{len(truth['builds'])} builds ({len(MUTANTS)} with one seeded bug), {n} logs -> work/sim/")


if __name__ == "__main__":
    main()
