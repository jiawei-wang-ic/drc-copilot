"""Triage of RTL simulation regression logs (Icarus Verilog / self-checking testbenches).

Deterministic part: classify each run, normalise failure messages into signatures, group runs by
build + signature, and pull the RTL lines that drive the failing signals (the "retrieval" step).
"""
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

HEADER = re.compile(r"^# (\w+)=(.*)$")
MISMATCH = re.compile(r"ERROR: \[(\w+)\] (\w+) mismatch at (\d+) ns(?: \(([^)]*)\))?: expected (\S+) got (\S+)")
COMPILE = re.compile(r"^(.*?):(\d+): (?:error: )?(.*)$")


@dataclass
class Run:
    path: str
    build: str
    design: str
    seed: str
    rtl: str
    status: str                       # PASS / FAIL / COMPILE_ERROR / TIMEOUT / UNKNOWN
    signals: Tuple[str, ...] = ()     # mismatching outputs, e.g. ('carry', 'y')
    tags: Tuple[str, ...] = ()        # extra context from messages, e.g. ('op=1',)
    first_error: str = ""
    first_time_ns: Optional[int] = None
    compile_line: Optional[int] = None
    compile_msg: str = ""
    errors: int = 0
    first_signal: str = ""
    first_tag: str = ""
    evidence: List[str] = field(default_factory=list)   # first few raw error lines


def parse(path: str) -> Run:
    meta, lines = {}, []
    with open(path, errors="replace") as f:
        for raw in f:
            m = HEADER.match(raw.strip())
            if m and m.group(1) in ("build", "design", "seed", "rtl"):
                for kv in raw[2:].split():
                    k, _, v = kv.partition("=")
                    meta[k] = v
                continue
            lines.append(raw.rstrip("\n"))
    run = Run(path=path, build=meta.get("build", "?"), design=meta.get("design", "?"),
              seed=meta.get("seed", "?"), rtl=meta.get("rtl", ""), status="UNKNOWN")
    text = "\n".join(lines)
    if "COMPILE FAILED" in text:
        run.status = "COMPILE_ERROR"
        rtl_name = os.path.basename(run.rtl)
        for ln in lines:                       # the first error in the design file is the real one;
            m = COMPILE.match(ln)              # testbench errors after it are usually knock-on effects
            if m and os.path.basename(m.group(1)) == rtl_name:
                run.compile_line, run.compile_msg = int(m.group(2)), m.group(3).strip()
                break
        if run.compile_line is None:
            m = next((COMPILE.match(ln) for ln in lines if COMPILE.match(ln)), None)
            if m:
                run.compile_line, run.compile_msg = int(m.group(2)), m.group(3).strip()
        run.first_error = f"{os.path.basename(run.rtl)}:{run.compile_line}: {run.compile_msg}"
        run.evidence = [os.path.basename(l.split(":", 1)[0]) + ":" + l.split(":", 1)[1] for l in lines
                        if COMPILE.match(l)][:4]
        return run
    mism = [MISMATCH.search(ln) for ln in lines]
    mism = [m for m in mism if m]
    if mism:
        run.status = "FAIL"
        run.errors = len(mism)
        run.signals = tuple(sorted({m.group(2) for m in mism}))
        run.tags = tuple(sorted({m.group(4) for m in mism if m.group(4)}))
        first = mism[0]
        run.first_time_ns = int(first.group(3))
        run.first_error = first.group(0)
        run.first_signal = first.group(2)
        run.first_tag = first.group(4) or ""
        run.evidence = [ln.strip() for ln in lines if MISMATCH.search(ln)][:4]
    elif any("FATAL" in ln and "timeout" in ln for ln in lines):
        run.status = "TIMEOUT"
        run.first_error = next(ln for ln in lines if "FATAL" in ln)
    elif any("TEST PASSED" in ln for ln in lines):
        run.status = "PASS"
    return run


def signature(r: Run, mode: str = "first") -> str:
    """Seed-independent description of how a run failed.

    mode="first": the first failing signal (and its tag) — what an engineer triages on.
    mode="set":   every signal that mismatched — varies with the seed, so it fragments groups.
    """
    if r.status == "COMPILE_ERROR":
        return f"compile error: {r.compile_msg} (line {r.compile_line})"
    if r.status == "FAIL":
        if mode == "set":
            s = "mismatch on " + ", ".join(r.signals)
            return s + (f" [{', '.join(r.tags)}]" if r.tags else "")
        return f"first mismatch on {r.first_signal}" + (f" [{r.first_tag}]" if r.first_tag else "")
    return r.status.lower()


@dataclass
class SimGroup:
    build: str
    design: str
    status: str
    signature: str
    runs: List[Run] = field(default_factory=list)
    context: List[Tuple[int, str]] = field(default_factory=list)   # (line number, RTL line)

    @property
    def count(self):
        return len(self.runs)


IDENT = re.compile(r"\b([A-Za-z_]\w*)\b")
KEYWORDS = {"assign", "begin", "end", "if", "else", "case", "endcase", "default", "always", "posedge", "negedge",
            "reg", "wire", "input", "output", "module", "endmodule", "localparam", "or", "and"}


def _drivers(src, sig):
    out = []
    for i, line in enumerate(src, 1):
        code = line.split("//")[0]
        if re.search(rf"(assign\s+{sig}\b|\b{sig}\s*(\[[^\]]*\])?\s*<=|\b{sig}\s*=[^=]|\{{[^}}]*\b{sig}\b[^}}]*\}}\s*=)", code):
            out.append(i)
    return out


def _guard(src, i):
    """The if / else-if / case-item line that controls line i, if any (looks up to 3 lines back)."""
    for j in range(i - 1, max(0, i - 4), -1):
        code = src[j - 1].split("//")[0]
        if re.search(r"\b(if|else)\b", code):
            return j
    return None


def driver_lines(rtl_path: str, signals, around: Optional[int] = None, radius: int = 2,
                 tag: str = "") -> List[Tuple[int, str]]:
    """RTL lines worth reading for this failure: drivers of the failing signals, their guarding
    conditions, one level of fan-in, and next-state logic for FSM outputs. For compile errors,
    the lines around the reported line (compilers often report the line after the real mistake)."""
    if not rtl_path or not os.path.exists(rtl_path):
        return []
    src = open(rtl_path).read().splitlines()
    if around:
        lo, hi = max(1, around - radius), min(len(src), around + radius)
        return [(i, src[i - 1]) for i in range(lo, hi + 1)]
    picked = set()
    for s in signals:
        for i in _drivers(src, s):
            picked.add(i)
    # a tag such as op=1 selects the matching case item
    m = re.match(r"(\w+)=(\d+)", tag or "")
    if m:
        label = re.compile(rf"'d{m.group(2)}\s*:")
        items = {i for i, line in enumerate(src, 1) if label.search(line.split("//")[0])}
        hit = {i for i in picked if i in items}
        # keep the matching case item even if it no longer assigns the signal (the bug may be a missing assignment)
        picked = (hit | items) if items else picked
    for i in list(picked):
        g = _guard(src, i)
        if g:
            picked.add(g)
    # one level of fan-in: who drives the signals read on those lines
    seen = set(signals)
    for i in list(picked):
        rhs = re.split(r"<=|=", src[i - 1].split("//")[0], maxsplit=1)[-1]
        for name in IDENT.findall(rhs):
            if name in seen or name in KEYWORDS or name.isupper() or re.match(r"^S\d", name):
                continue
            seen.add(name)
            for j in _drivers(src, name):
                picked.add(j)
                g = _guard(src, j)
                if g:
                    picked.add(g)
    if any("state" in src[i - 1] for i in picked):
        for i, line in enumerate(src, 1):
            if re.search(r"\bnext\s*=", line.split("//")[0]):
                picked.add(i)
    return [(i, src[i - 1]) for i in sorted(picked)]


def triage(log_paths: List[str], root: str = ".", mode: str = "first") -> Tuple[List[Run], List[SimGroup]]:
    runs = [parse(p) for p in log_paths]
    buckets: Dict[tuple, SimGroup] = {}
    for r in runs:
        if r.status == "PASS":
            continue
        key = (r.build, r.design, r.status, signature(r, mode))
        g = buckets.get(key)
        if g is None:
            g = buckets[key] = SimGroup(build=r.build, design=r.design, status=r.status, signature=key[3])
        g.runs.append(r)
    groups = list(buckets.values())
    for g in groups:
        r0 = g.runs[0]
        rtl = os.path.join(root, r0.rtl)
        sigs = (r0.first_signal,) if mode == "first" and r0.first_signal else r0.signals
        g.context = driver_lines(rtl, sigs, around=r0.compile_line if g.status == "COMPILE_ERROR" else None,
                                 tag=r0.first_tag)
    groups.sort(key=lambda g: (g.build, -g.count))
    return runs, groups


def summary(runs: List[Run]) -> Dict[str, int]:
    return dict(Counter(r.status for r in runs))
