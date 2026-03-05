"""Optional LLM validation step — checks if generated output matches instructions.

When enabled, each generation is followed by a fast LLM vision check.
If the check fails the image is regenerated (up to *max_retries* times).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PIL import Image

from pixel_magic.providers.base import ImageProvider

logger = logging.getLogger(__name__)


_VALIDATION_PROMPT = """\
You are a strict QA validator for pixel art sprite sheets.
Look at this image and answer these questions.

**Instructions given to the artist:**
{instructions_summary}

**Check the following:**
1. sprite_count — Does the image contain exactly {expected_count} distinct \
sprites/frames? Count carefully.
2. layout — Are the sprites arranged in a single horizontal row (not stacked \
vertically, not in a grid)?
3. subject_match — Does the subject matter match what was requested?

Score each dimension 1 (fail) or 10 (pass).
Return ONLY valid JSON:
{{"sprite_count": N, "layout": N, "subject_match": N, \
"feedback": "one-sentence reason if anything failed"}}\
"""


@dataclass
class ValidationResult:
    """Outcome of a single validation check."""

    passed: bool
    sprite_count_ok: bool
    layout_ok: bool
    subject_ok: bool
    feedback: str = ""
    raw: dict | None = None

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "sprite_count_ok": self.sprite_count_ok,
            "layout_ok": self.layout_ok,
            "subject_ok": self.subject_ok,
            "feedback": self.feedback,
        }


async def validate_generation(
    provider: ImageProvider,
    image: Image.Image,
    instructions_summary: str,
    expected_count: int,
    *,
    pass_threshold: int = 7,
) -> ValidationResult:
    """Run a quick LLM check on a generated image.

    Args:
        provider: The AI provider (needs ``evaluate_image``).
        image: The generated composite image.
        instructions_summary: Human-readable summary of what was requested.
        expected_count: How many sprites/frames should be in the image.
        pass_threshold: Minimum score (1-10) to consider a dimension passed.

    Returns:
        A :class:`ValidationResult` with per-dimension pass/fail.
    """
    prompt = _VALIDATION_PROMPT.format(
        instructions_summary=instructions_summary,
        expected_count=expected_count,
    )

    try:
        raw = await provider.evaluate_image(image, prompt)
    except Exception as exc:
        logger.warning("Validation LLM call failed: %s — treating as passed", exc)
        # If the validation call itself errors, don't block generation
        return ValidationResult(
            passed=True,
            sprite_count_ok=True,
            layout_ok=True,
            subject_ok=True,
            feedback=f"Validation skipped (error: {exc})",
        )

    sprite_count_score = int(raw.get("sprite_count", 10))
    layout_score = int(raw.get("layout", 10))
    subject_score = int(raw.get("subject_match", 10))
    feedback = str(raw.get("feedback", ""))

    sprite_ok = sprite_count_score >= pass_threshold
    layout_ok = layout_score >= pass_threshold
    subject_ok = subject_score >= pass_threshold
    passed = sprite_ok and layout_ok and subject_ok

    return ValidationResult(
        passed=passed,
        sprite_count_ok=sprite_ok,
        layout_ok=layout_ok,
        subject_ok=subject_ok,
        feedback=feedback,
        raw=raw,
    )


def build_retry_hint(result: ValidationResult) -> str:
    """Build a short correction hint from a failed validation."""
    issues: list[str] = []
    if not result.sprite_count_ok:
        issues.append(
            "WRONG SPRITE COUNT — you must produce EXACTLY the requested number "
            "of sprites in a SINGLE HORIZONTAL ROW."
        )
    if not result.layout_ok:
        issues.append(
            "WRONG LAYOUT — arrange ALL sprites in ONE horizontal row, "
            "NOT stacked vertically and NOT in a grid."
        )
    if not result.subject_ok:
        issues.append(
            "SUBJECT MISMATCH — the generated sprites do not match the "
            "requested description. Please re-read the instructions."
        )
    if result.feedback:
        issues.append(f"Judge feedback: {result.feedback}")
    return "\n".join(issues)
