"""Vision QA — AI-based quality evaluation with self-correction loop."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PIL import Image

from pixel_magic.models.metadata import QACheck, QACheckName, QAReport
from pixel_magic.providers.base import ImageProvider

logger = logging.getLogger(__name__)


@dataclass
class VisionScores:
    """Structured scores from AI vision evaluation."""

    grid_alignment: float = 0.0
    style_adherence: float = 0.0
    silhouette_clarity: float = 0.0
    overall: float = 0.0
    feedback: str = ""


SINGLE_FRAME_EVAL_PROMPT = """Evaluate this pixel art sprite image on the following criteria.
Score each from 1 (worst) to 10 (best).

1. **grid_alignment**: Are pixels on a clean, consistent grid? No anti-aliasing, blurring, or subpixel artifacts?
2. **style_adherence**: Does it look like authentic pixel art ({style})? Clean color ramps, intentional shading?
3. **silhouette_clarity**: Is the sprite silhouette clear and readable at its target size? Good contrast with transparent background?

Return JSON only:
{{"grid_alignment": N, "style_adherence": N, "silhouette_clarity": N, "overall": N, "feedback": "brief text"}}"""


CROSS_FRAME_EVAL_PROMPT = """Compare these sprite frames for consistency.
They should be from the same character/object. Score 1-10 on:

1. **identity_match**: Do they look like the same character? Consistent proportions, features, colors?
2. **palette_consistency**: Are the same colors used across all frames? No unexpected color drift?
3. **scale_consistency**: Are all sprites the same size/scale?

Return JSON only:
{{"identity_match": N, "palette_consistency": N, "scale_consistency": N, "overall": N, "feedback": "brief text"}}"""


async def evaluate_single_frame(
    provider: ImageProvider,
    image: Image.Image,
    style: str = "16-bit pixel art",
) -> VisionScores:
    """Evaluate a single sprite frame using AI vision."""
    prompt = SINGLE_FRAME_EVAL_PROMPT.format(style=style)
    result = await provider.evaluate_image(image, prompt)

    scores = VisionScores()
    if isinstance(result, dict):
        scores.grid_alignment = float(result.get("grid_alignment", 0)) / 10
        scores.style_adherence = float(result.get("style_adherence", 0)) / 10
        scores.silhouette_clarity = float(result.get("silhouette_clarity", 0)) / 10
        scores.overall = float(result.get("overall", 0)) / 10
        scores.feedback = str(result.get("feedback", ""))

    return scores


async def evaluate_cross_frame(
    provider: ImageProvider,
    frames: list[Image.Image],
    max_frames: int = 6,
) -> dict:
    """Evaluate cross-frame consistency by compositing frames into a strip."""
    if not frames:
        return {"identity_match": 1.0, "palette_consistency": 1.0, "scale_consistency": 1.0}

    # Create a composite strip for evaluation
    sample = frames[:max_frames]
    max_h = max(f.height for f in sample)
    total_w = sum(f.width for f in sample) + (len(sample) - 1) * 4
    composite = Image.new("RGBA", (total_w, max_h), (0, 0, 0, 0))

    x = 0
    for f in sample:
        composite.paste(f, (x, max_h - f.height))
        x += f.width + 4

    result = await provider.evaluate_image(composite, CROSS_FRAME_EVAL_PROMPT)

    if isinstance(result, dict):
        return {
            "identity_match": float(result.get("identity_match", 0)) / 10,
            "palette_consistency": float(result.get("palette_consistency", 0)) / 10,
            "scale_consistency": float(result.get("scale_consistency", 0)) / 10,
            "overall": float(result.get("overall", 0)) / 10,
            "feedback": str(result.get("feedback", "")),
        }

    return {"identity_match": 0.5, "palette_consistency": 0.5, "scale_consistency": 0.5}


def vision_checks_to_qa(
    scores: VisionScores,
    min_score: float = 0.7,
) -> list[QACheck]:
    """Convert vision scores into QACheck entries."""
    checks = []

    checks.append(QACheck(
        QACheckName.VISION_GRID_ALIGNMENT,
        scores.grid_alignment >= min_score,
        scores.grid_alignment,
        f"Grid alignment: {scores.grid_alignment:.2f}",
    ))

    checks.append(QACheck(
        QACheckName.VISION_STYLE_ADHERENCE,
        scores.style_adherence >= min_score,
        scores.style_adherence,
        f"Style adherence: {scores.style_adherence:.2f}",
    ))

    checks.append(QACheck(
        QACheckName.VISION_SILHOUETTE_CLARITY,
        scores.silhouette_clarity >= min_score,
        scores.silhouette_clarity,
        f"Silhouette clarity: {scores.silhouette_clarity:.2f}",
    ))

    return checks


async def run_vision_qa(
    provider: ImageProvider,
    frames: list[Image.Image],
    style: str = "16-bit pixel art",
    min_score: float = 0.7,
) -> QAReport:
    """Run all vision-based QA checks."""
    report = QAReport()

    if not frames:
        return report

    # Single-frame evaluation on first frame
    scores = await evaluate_single_frame(provider, frames[0], style)
    report.checks.extend(vision_checks_to_qa(scores, min_score))

    # Cross-frame consistency if multiple frames
    if len(frames) > 1:
        cross = await evaluate_cross_frame(provider, frames)
        overall = cross.get("overall", 0.5)
        report.checks.append(QACheck(
            QACheckName.VISION_CROSS_FRAME_CONSISTENCY,
            overall >= min_score,
            overall,
            cross.get("feedback", ""),
        ))

    return report


def build_correction_prompt(
    qa_report: QAReport,
    original_prompt: str,
) -> str | None:
    """Build a correction prompt from failed QA checks.

    Returns None if no correction is needed (all checks passed).
    """
    if qa_report.passed:
        return None

    failed = qa_report.failed_checks
    issues = []

    for check in failed:
        if check.name == QACheckName.VISION_GRID_ALIGNMENT:
            issues.append("The pixel grid is not clean — there is anti-aliasing or blurring. "
                         "Make sure every pixel is on a crisp, uniform grid with no subpixel artifacts.")
        elif check.name == QACheckName.VISION_STYLE_ADHERENCE:
            issues.append("The style doesn't match authentic pixel art. "
                         "Use clean color ramps, intentional dithering, and avoid gradients or soft shading.")
        elif check.name == QACheckName.VISION_SILHOUETTE_CLARITY:
            issues.append("The sprite silhouette is not clear enough. "
                         "Improve contrast, make the outline more distinct, ensure readability at target size.")
        elif check.name == QACheckName.VISION_CROSS_FRAME_CONSISTENCY:
            issues.append("The frames are inconsistent — character proportions, colors, or scale differ "
                         "between frames. Make all frames look like the same character.")
        elif check.name == QACheckName.FRAME_COUNT_MATCH:
            issues.append(f"Frame count mismatch: {check.details}. "
                         "Generate exactly the requested number of frames.")
        elif check.name == QACheckName.PALETTE_COMPLIANCE:
            issues.append("Off-palette colors detected. Use only the specified palette colors.")

    if not issues:
        return None

    correction = (
        "The previous generation had quality issues. Please regenerate with these corrections:\n\n"
        + "\n".join(f"- {issue}" for issue in issues)
        + "\n\nOriginal request: " + original_prompt
    )

    return correction
