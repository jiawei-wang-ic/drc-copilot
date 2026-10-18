# Simulation-log triage — evaluation

- Benchmark: 15 builds with one seeded bug + 4 clean builds, 6 seeds each = 114 runs

## 1. Regression (testbench quality, not this tool)
- Clean runs reported as failing: **0/24 (0.0%)**
- Buggy runs caught: 90/90 (100.0%) · bugs caught: 15/15 (100.0%)

## 2. Grouping
- 90 failing runs -> **16 groups** by first symptom (vs 21 if grouped by the full set of mismatching signals)
- Builds split into more than one group: 1 (first symptom) vs 4 (full set)

## 3. Candidate RTL lines (retrieval)
- True bug line among the candidates: **16/16 (100.0%)** · candidates per group: 1–9 (mean 5.4)

## 4. Localisation (top-1 line == seeded bug line)
- Baseline without a model: **7/16 (43.8%)** — functional 7/14 · compile error 0/2
- GLM: **15/16 (93.8%)** — functional 13/14 · compile error 2/2 (valid JSON 15/16)
