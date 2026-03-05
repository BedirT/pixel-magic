---
title: Evaluation and Testing
---

## Production vs Offline Evaluation

- Production quality gates:
  - deterministic QA gate (hard)
  - final validator agent gate (hard)
- Offline quality tracking:
  - LLM-as-a-Judge evaluation suite
  - trend and regression analysis across variants/providers

LLM-as-a-Judge is not an extra runtime pass/fail gate in production flow.

## MCP Evaluation Tools

- `run_evaluation` runs standard cases and persists results.
- `compare_evaluations` compares result sets and generates reports.
- `list_eval_cases` lists canonical cases.

## Test Strategy

Runtime and tools should include:

- planner/correction/validator behavior tests
- extraction/postprocess/export correctness tests
- state transition and retry semantics tests
- extension reference-image path tests
- MCP registry surface tests
- docs coverage checks for tool reference completeness

## Typical Regression Workflow

1. Run baseline:

```bash
uv run python -m pixel_magic.evaluation.cli run --variant baseline
```

2. Run candidate:

```bash
uv run python -m pixel_magic.evaluation.cli run --variant candidate
```

3. Compare:

```bash
uv run python -m pixel_magic.evaluation.cli compare \
  output/eval/baseline/results.json \
  output/eval/candidate/results.json
```
