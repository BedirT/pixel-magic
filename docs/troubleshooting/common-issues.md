---
title: Common Issues
---

## `INVALID_INPUT` at `input_validate`

Typical cause:

- missing or unreadable `reference_image_path` in `extend_character_animation`

Fix:

- provide an existing local file path
- confirm process permissions on that path

## `QA_FAILED` at `deterministic_gate`

Typical causes:

- alpha not compliant with selected alpha policy
- frame count mismatch
- palette drift across frames

Fix:

- reduce prompt complexity
- tighten animation description
- use a named palette for consistency

## `VALIDATOR_FAILED` at `final_validator_agent`

Typical causes:

- validator returns `fail`
- validator returns `retry` after retry budget is already spent

Fix:

- improve style/objective specificity
- lower asset complexity per call

## Provider Errors

Typical causes:

- missing API key
- provider quota/rate limits
- transient upstream errors

Fix:

- verify environment keys
- retry later for transient failures
- switch provider with `set_provider`

## Docs Coverage Gate Failures

If `scripts/check_mcp_docs_coverage.py` fails:

- add missing tool heading(s) to `docs/mcp/tool-reference.md`
- heading format must be:

```md
### `tool_name`
```
