"""Root-cause hints for a simulation failure group: a deterministic baseline and a GLM explanation."""
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from . import glm
from .simlog import SimGroup, _drivers

SYSTEM = (
    "You are a digital verification engineer triaging a failing RTL regression. "
    "Use only the evidence and RTL lines you are given. Pick the single RTL line most likely to contain the bug. "
    "Compilers often report a syntax error on the line AFTER the real mistake. Answer with JSON only."
)

TEMPLATE = """Design: {design}   (RTL file: {rtl})
Failure signature: {signature}
Failing runs in this group: {count} (different random seeds)
First error lines from the logs:
{evidence}

Candidate RTL lines (line number: code):
{context}

Return JSON with exactly these keys:
{{"suspect_line": <one of the candidate line numbers>,
  "hypothesis": "one or two sentences: what is wrong and why it produces this failure",
  "fix": "the corrected line of code",
  "next_step": "one concrete debug step to confirm it (signal to probe, waveform to check)"
}}"""


@dataclass
class SimExplanation:
    suspect_line: Optional[int] = None
    hypothesis: str = ""
    fix: str = ""
    next_step: str = ""
    error: str = ""


def baseline_line(g: SimGroup, root: str = ".") -> Optional[int]:
    """No model: compile errors -> the reported line; mismatches -> first line that drives the first failing signal."""
    r0 = g.runs[0]
    if g.status == "COMPILE_ERROR":
        return r0.compile_line
    rtl = os.path.join(root, r0.rtl)
    if r0.first_signal and os.path.exists(rtl):
        src = open(rtl).read().splitlines()
        d = [i for i in _drivers(src, r0.first_signal) if any(i == n for n, _ in g.context)]
        if d:
            return d[0]
    return g.context[0][0] if g.context else None


def _parse(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def explain(g: SimGroup) -> SimExplanation:
    r0 = g.runs[0]
    prompt = TEMPLATE.format(
        design=g.design, rtl=os.path.basename(r0.rtl), signature=g.signature, count=g.count,
        evidence="\n".join(r0.evidence) or r0.first_error,
        context="\n".join(f"{n}: {line}" for n, line in g.context) or "(none)")
    try:
        d = _parse(glm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]))
        line = d.get("suspect_line")
        return SimExplanation(suspect_line=int(line) if str(line).strip().isdigit() else None,
                              hypothesis=str(d.get("hypothesis", "")), fix=str(d.get("fix", "")),
                              next_step=str(d.get("next_step", "")))
    except glm.GLMUnavailable as e:
        return SimExplanation(error=str(e))
    except (ValueError, json.JSONDecodeError, TypeError):
        return SimExplanation(error="model answer was not valid JSON")
