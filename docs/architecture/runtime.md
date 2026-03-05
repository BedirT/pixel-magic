---
title: Runtime Architecture
---

## Stage Machine

The executor uses a fixed, deterministic transition sequence:

1. `input_validate`
2. `route`
3. `plan`
4. `generate`
5. `extract`
6. `postprocess`
7. `deterministic_gate`
8. `final_validator_agent`
9. `export`
10. `finalize`

No stage skipping is allowed in production flow.

## Gate Semantics

### Deterministic Gate

- Mandatory hard gate.
- Uses deterministic QA checks over generated frames.
- Terminal failure when unrecoverable.

### Final Validator Agent

- Mandatory hard gate.
- Structured output: `pass | retry | fail`.
- Retry budget: one correction attempt maximum.
- Correction planner emits patch instructions; executor reruns affected generation flow.

## Orchestration Model

- Agents decide (route, plan, correction, final validation).
- Deterministic tools execute mutations.
- Executor owns transitions, retry budget, timeout, and terminal semantics.

## External Reference Support

For extension workflows:

- input stage validates `reference_image_path` / `external_reference_paths`
- loaded images are passed to generation calls with internal references
- extension mode plans only requested animation prompts (no base idle generation)

## Output Contract

Successful jobs return:

- artifact manifest (raw paths, frame paths, atlas, metadata)
- full stage trace
- deterministic gate report
- final validator decision
- metrics (`generation_calls`, `retry_count`, duration)
