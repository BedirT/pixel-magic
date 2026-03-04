"""Deterministic QA checks — fast, free, run on every frame."""

from __future__ import annotations

import numpy as np
from PIL import Image

from pixel_magic.models.metadata import QACheck, QACheckName, QAReport
from pixel_magic.models.palette import Palette
from pixel_magic.pipeline.consistency import detect_jitter
from pixel_magic.models.asset import AnimationClip


def check_palette_compliance(
    image: Image.Image,
    palette: Palette,
    tolerance: int = 2,
) -> QACheck:
    """Check that all opaque pixels are within tolerance of palette colors."""
    arr = np.array(image)
    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3]

    opaque_mask = alpha > 128
    if not opaque_mask.any():
        return QACheck(QACheckName.PALETTE_COMPLIANCE, True, 1.0, "No opaque pixels")

    opaque_pixels = rgb[opaque_mask].astype(np.int16)
    pal_arr = np.array([c[:3] for c in palette.colors], dtype=np.int16)

    # For each pixel, find minimum distance to any palette color
    compliant = 0
    total = len(opaque_pixels)

    # Batch: compute distance matrix
    dists = np.min(
        np.linalg.norm(opaque_pixels[:, None, :] - pal_arr[None, :, :], axis=2),
        axis=1,
    )
    compliant = int(np.sum(dists <= tolerance))

    score = compliant / total if total > 0 else 1.0
    passed = score >= 0.99  # Allow 1% tolerance

    return QACheck(
        QACheckName.PALETTE_COMPLIANCE,
        passed,
        score,
        f"{compliant}/{total} pixels within palette (tolerance={tolerance})",
    )


def check_alpha_compliance(
    image: Image.Image,
    policy: str = "binary",
) -> QACheck:
    """Check that alpha values conform to the policy."""
    arr = np.array(image)
    alpha = arr[:, :, 3].flatten()

    if policy == "keep8bit":
        return QACheck(QACheckName.ALPHA_COMPLIANCE, True, 1.0, "keep8bit: all values allowed")

    # Binary: only 0 or 255
    binary_compliant = np.sum((alpha == 0) | (alpha == 255))
    total = len(alpha)
    score = binary_compliant / total if total > 0 else 1.0

    return QACheck(
        QACheckName.ALPHA_COMPLIANCE,
        score >= 0.99,
        score,
        f"{binary_compliant}/{total} pixels have binary alpha",
    )


def check_grid_compliance(
    image: Image.Image,
    macro_size: int,
) -> QACheck:
    """Check that all macro-cells are uniform (intra-cell variance = 0)."""
    if macro_size <= 1:
        return QACheck(QACheckName.GRID_COMPLIANCE, True, 1.0, "Grid size 1: trivially compliant")

    arr = np.array(image).astype(np.float32)
    h, w = arr.shape[:2]

    cells_h = h // macro_size
    cells_w = w // macro_size
    if cells_h < 1 or cells_w < 1:
        return QACheck(QACheckName.GRID_COMPLIANCE, True, 1.0, "Image smaller than grid")

    region = arr[:cells_h * macro_size, :cells_w * macro_size]
    cells = region.reshape(cells_h, macro_size, cells_w, macro_size, 4)
    cells = cells.transpose(0, 2, 1, 3, 4)
    cells = cells.reshape(cells_h * cells_w, macro_size * macro_size, 4)

    # Intra-cell variance
    variance = np.var(cells, axis=1).mean()
    passed = variance < 0.5  # Near-zero variance
    score = max(0.0, 1.0 - variance / 100.0)

    return QACheck(
        QACheckName.GRID_COMPLIANCE,
        passed,
        score,
        f"Mean intra-cell variance: {variance:.2f}",
    )


def check_island_noise(
    image: Image.Image,
    min_size: int = 2,
) -> QACheck:
    """Check for small disconnected islands that suggest noise."""
    try:
        from skimage import measure
    except ImportError:
        return QACheck(QACheckName.ISLAND_NOISE, True, 1.0, "skimage not available")

    arr = np.array(image)
    alpha = arr[:, :, 3]
    binary = (alpha > 128).astype(np.uint8)

    labels = measure.label(binary, connectivity=1)
    regions = measure.regionprops(labels)

    small_islands = [r for r in regions if r.area < min_size]
    total_regions = len(regions)

    if total_regions == 0:
        return QACheck(QACheckName.ISLAND_NOISE, True, 1.0, "No opaque regions")

    score = 1.0 - len(small_islands) / max(total_regions, 1)

    return QACheck(
        QACheckName.ISLAND_NOISE,
        len(small_islands) == 0,
        score,
        f"{len(small_islands)} islands below {min_size}px (of {total_regions} total)",
    )


def check_frame_count(actual: int, expected: int) -> QACheck:
    """Check extracted frame count matches expected."""
    passed = actual == expected
    score = 1.0 if passed else 0.0
    return QACheck(
        QACheckName.FRAME_COUNT_MATCH,
        passed,
        score,
        f"Expected {expected}, got {actual}",
    )


def check_frame_size_consistency(frames: list[Image.Image]) -> QACheck:
    """Check all frames have identical dimensions."""
    if len(frames) <= 1:
        return QACheck(QACheckName.FRAME_SIZE_CONSISTENCY, True, 1.0, "0-1 frames")

    sizes = [(f.width, f.height) for f in frames]
    unique_sizes = set(sizes)
    passed = len(unique_sizes) == 1
    score = 1.0 / len(unique_sizes)

    return QACheck(
        QACheckName.FRAME_SIZE_CONSISTENCY,
        passed,
        score,
        f"{'Consistent' if passed else 'Inconsistent'}: {unique_sizes}",
    )


def check_palette_delta(
    frames: list[Image.Image],
    max_delta_e: float = 5.0,
) -> QACheck:
    """Check palette consistency across frames using color histogram comparison."""
    if len(frames) <= 1:
        return QACheck(QACheckName.PALETTE_DELTA, True, 1.0, "0-1 frames")

    from pixel_magic.pipeline.palette import rgb_to_oklab

    # Collect unique colors per frame in OKLab
    frame_colors = []
    for f in frames:
        arr = np.array(f)
        alpha = arr[:, :, 3]
        rgb = arr[:, :, :3]
        opaque = rgb[alpha > 128]
        if len(opaque) > 0:
            unique = np.unique(opaque.reshape(-1, 3), axis=0)
            lab = rgb_to_oklab(unique)
            frame_colors.append(lab)

    if len(frame_colors) < 2:
        return QACheck(QACheckName.PALETTE_DELTA, True, 1.0, "Insufficient color data")

    # Compare first frame palette to each subsequent frame
    ref = frame_colors[0]
    max_drift = 0.0

    for fc in frame_colors[1:]:
        # For each color in fc, find nearest in ref
        for color in fc:
            dists = np.linalg.norm(ref - color, axis=1)
            min_dist = float(np.min(dists))
            max_drift = max(max_drift, min_dist)

    passed = max_drift < max_delta_e / 100  # OKLab distances are typically 0-1
    score = max(0.0, 1.0 - max_drift * 100 / max_delta_e)

    return QACheck(
        QACheckName.PALETTE_DELTA,
        passed,
        score,
        f"Max palette drift: {max_drift:.4f} OKLab",
    )


def check_anim_flicker(clip: AnimationClip, threshold: float = 2.0) -> QACheck:
    """Check for animation flicker/jitter."""
    report = detect_jitter(clip, threshold)
    passed = not report["jitter_detected"]
    max_cd = report["max_centroid_drift"]
    score = max(0.0, 1.0 - max_cd / (threshold * 3))

    return QACheck(
        QACheckName.ANIM_FLICKER,
        passed,
        score,
        f"Max centroid drift: {max_cd:.1f}px, bbox drift: {report['max_bbox_drift']:.1f}px",
    )


def run_deterministic_qa(
    frames: list[Image.Image],
    palette: Palette | None = None,
    alpha_policy: str = "binary",
    macro_size: int = 1,
    expected_frame_count: int | None = None,
    min_island_size: int = 2,
    clip: AnimationClip | None = None,
) -> QAReport:
    """Run all applicable deterministic QA checks and return a report."""
    report = QAReport()

    # Per-frame checks on first frame (representative)
    if frames:
        sample = frames[0]

        if palette:
            report.checks.append(check_palette_compliance(sample, palette))

        report.checks.append(check_alpha_compliance(sample, alpha_policy))

        if macro_size > 1:
            report.checks.append(check_grid_compliance(sample, macro_size))

        report.checks.append(check_island_noise(sample, min_island_size))

    # Multi-frame checks
    if expected_frame_count is not None:
        report.checks.append(check_frame_count(len(frames), expected_frame_count))

    if len(frames) > 1:
        report.checks.append(check_frame_size_consistency(frames))

        if palette:
            report.checks.append(check_palette_delta(frames))

    if clip:
        report.checks.append(check_anim_flicker(clip))

    return report
