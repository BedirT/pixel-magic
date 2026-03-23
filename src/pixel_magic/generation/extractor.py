"""Frame extraction from composite AI-generated images."""

from __future__ import annotations

import logging
import math

import cv2
import numpy as np
from PIL import Image

from pixel_magic.models.asset import CompositeLayout

logger = logging.getLogger(__name__)

# Maximum acceptable aspect ratio for a single extracted frame.
# Sprites are typically close to square; anything beyond 2:1 is suspect.
_MAX_FRAME_ASPECT = 2.0

# Magenta separator detection parameters
_MAGENTA_RGB = np.array([255, 0, 255], dtype=np.float64)
_MAGENTA_COLOR_DIST = 30  # max Euclidean distance in RGB space
_MAGENTA_MIN_COVERAGE = 0.80  # fraction of column height that must be magenta


def extract_frames(
    composite: Image.Image,
    layout: CompositeLayout,
    expected_count: int,
    grid_cols: int | None = None,
    provider: str = "openai",
    chromakey_color: str = "green",
) -> list[Image.Image]:
    """Extract individual sprite frames from a composite image.

    Args:
        composite: The composite image containing multiple sprites.
        layout: How the sprites are arranged.
        expected_count: How many frames we expect to find.
        grid_cols: For GRID layout, how many columns.
        provider: Image provider name — ``"gemini"`` uses chromakey removal,
            others use corner-sampling background removal.
        chromakey_color: Chromakey preset for Gemini (``"green"`` or ``"blue"``).

    Returns:
        List of extracted PIL Images (RGBA).
    """
    composite = composite.convert("RGBA")

    if layout == CompositeLayout.REFERENCE_SHEET:
        return _extract_reference_sheet(composite, expected_count, provider=provider, chromakey_color=chromakey_color)
    elif layout == CompositeLayout.AUTO_DETECT:
        return _extract_auto(composite, expected_count, provider=provider, chromakey_color=chromakey_color)
    elif layout == CompositeLayout.HORIZONTAL_STRIP:
        return _extract_smart_strip(composite, expected_count, provider=provider, chromakey_color=chromakey_color)
    elif layout == CompositeLayout.VERTICAL_STRIP:
        return _extract_strip(composite, expected_count, horizontal=False)
    elif layout == CompositeLayout.GRID:
        cols = grid_cols or expected_count
        rows = max(1, (expected_count + cols - 1) // cols)
        return _extract_grid(composite, rows, cols, expected_count)
    else:
        return _extract_smart_strip(composite, expected_count, provider=provider, chromakey_color=chromakey_color)


def _frame_aspect_ok(w: int, h: int) -> bool:
    """Check if a frame has a reasonable aspect ratio for a sprite."""
    if w == 0 or h == 0:
        return False
    ratio = max(w, h) / min(w, h)
    return ratio <= _MAX_FRAME_ASPECT


def _remove_solid_background(image: Image.Image, tolerance: int = 30) -> Image.Image:
    """If the image has a solid-color background, make it transparent.

    Detects the dominant corner color and replaces near-matching pixels with alpha=0.
    """
    arr = np.array(image)
    alpha = arr[:, :, 3]

    # Only process if image is mostly opaque (solid background)
    opaque_ratio = np.sum(alpha > 240) / alpha.size
    if opaque_ratio < 0.5:
        return image  # already has transparency

    # Sample corner pixels to detect background color
    h, w = arr.shape[:2]
    corners = [
        arr[0, 0, :3], arr[0, w - 1, :3],
        arr[h - 1, 0, :3], arr[h - 1, w - 1, :3],
        arr[0, w // 2, :3], arr[h - 1, w // 2, :3],
    ]
    bg_color = np.median(corners, axis=0).astype(np.float64)

    # Create mask of pixels close to background color
    rgb = arr[:, :, :3].astype(np.float64)
    dist = np.sqrt(np.sum((rgb - bg_color) ** 2, axis=2))
    bg_mask = dist < tolerance

    # Set background pixels to transparent
    result = arr.copy()
    result[bg_mask, 3] = 0

    return Image.fromarray(result, "RGBA")


def _trim_transparent_padding(image: Image.Image) -> Image.Image:
    """Crop to the bounding box of non-transparent content."""
    bbox = image.getbbox()
    if bbox is None:
        return image
    x0 = max(0, bbox[0] - 2)
    y0 = max(0, bbox[1] - 2)
    x1 = min(image.width, bbox[2] + 2)
    y1 = min(image.height, bbox[3] + 2)
    cropped = image.crop((x0, y0, x1, y1))
    if cropped.width < 10 or cropped.height < 10:
        return image
    return cropped


def _prepare_composite(
    image: Image.Image,
    provider: str = "openai",
    chromakey_color: str = "green",
) -> Image.Image:
    """Prepare a composite image for extraction: remove background, trim padding.

    For Gemini provider, uses HSV-based chromakey removal.
    For other providers, uses corner-sampling solid background removal.
    """
    if provider == "gemini":
        from pixel_magic.pipeline.chromakey import remove_chromakey
        image = remove_chromakey(image, color=chromakey_color)
    else:
        image = _remove_solid_background(image)
    return _trim_transparent_padding(image)


def _extract_reference_sheet(
    composite: Image.Image,
    expected_count: int,
    provider: str = "openai",
    chromakey_color: str = "green",
) -> list[Image.Image]:
    """Extract sprites from a multi-view reference sheet.

    JSON-structured character prompts produce multi-view sheets with transparent
    backgrounds. Uses connected-component detection to find individual views.
    """
    cleaned = _prepare_composite(composite, provider=provider, chromakey_color=chromakey_color)

    # Use connected-component detection
    frames = _run_component_detection(cleaned, expected_count)

    if len(frames) == expected_count:
        logger.debug(
            "Reference sheet: extracted %d views via component detection",
            expected_count,
        )
        return frames

    # Fallback: try grid/strip layouts on the cleaned image
    grid_frames = _try_grid_layouts(cleaned, expected_count)
    if grid_frames:
        return grid_frames

    # Last resort: horizontal strip
    logger.warning(
        "Reference sheet: component detection found %d but expected %d, "
        "falling back to horizontal strip.",
        len(frames), expected_count,
    )
    return _extract_strip(cleaned, expected_count, horizontal=True)


def _detect_separator_lines(arr: np.ndarray) -> list[int]:
    """Find columns that are magenta separator lines.

    Args:
        arr: RGBA numpy array of the image.

    Returns:
        Sorted list of column indices that are magenta separators.
    """
    h, w = arr.shape[:2]
    if h == 0 or w == 0:
        return []

    rgb = arr[:, :, :3].astype(np.float64)
    alpha = arr[:, :, 3]

    # Per-column: count pixels that are both opaque and magenta
    dist = np.sqrt(np.sum((rgb - _MAGENTA_RGB) ** 2, axis=2))
    is_magenta = (dist <= _MAGENTA_COLOR_DIST) & (alpha >= 128)

    col_coverage = np.sum(is_magenta, axis=0) / h
    return sorted(int(c) for c in np.where(col_coverage >= _MAGENTA_MIN_COVERAGE)[0])


def _group_separator_columns(cols: list[int]) -> list[tuple[int, int]]:
    """Group consecutive magenta columns into (start, end) spans."""
    if not cols:
        return []
    groups: list[tuple[int, int]] = []
    start = cols[0]
    prev = cols[0]
    for c in cols[1:]:
        if c == prev + 1:
            prev = c
        else:
            groups.append((start, prev))
            start = c
            prev = c
    groups.append((start, prev))
    return groups


def _remove_magenta_bleed(frame: Image.Image, margin: int = 4) -> Image.Image:
    """Zero out residual magenta at the frame edges."""
    arr = np.array(frame)
    h, w = arr.shape[:2]
    if w == 0 or h == 0:
        return frame

    rgb = arr[:, :, :3].astype(np.float64)
    dist = np.sqrt(np.sum((rgb - _MAGENTA_RGB) ** 2, axis=2))
    is_magenta = dist <= _MAGENTA_COLOR_DIST

    edge = min(margin, w)
    # Left edge
    mask_left = is_magenta[:, :edge]
    arr[:, :edge, 3][mask_left] = 0
    # Right edge
    mask_right = is_magenta[:, w - edge:]
    arr[:, w - edge:, 3][mask_right] = 0

    edge_y = min(margin, h)
    # Top edge
    mask_top = is_magenta[:edge_y, :]
    arr[:edge_y, :, 3][mask_top] = 0
    # Bottom edge
    mask_bottom = is_magenta[h - edge_y:, :]
    arr[h - edge_y:, :, 3][mask_bottom] = 0

    return Image.fromarray(arr, "RGBA")


def _extract_by_separators(
    composite: Image.Image, expected_count: int
) -> list[Image.Image] | None:
    """Try to extract frames using magenta separator lines.

    Looks for vertical magenta (#FF00FF) divider lines between sprites.
    Expects exactly (expected_count - 1) separator groups.

    Returns:
        List of extracted frames if separators match, else None.
    """
    if expected_count <= 1:
        return None

    arr = np.array(composite.convert("RGBA"))
    cols = _detect_separator_lines(arr)
    if not cols:
        return None

    groups = _group_separator_columns(cols)
    if len(groups) != expected_count - 1:
        logger.debug(
            "Separator detection found %d dividers but expected %d",
            len(groups), expected_count - 1,
        )
        return None

    w = composite.width
    h = composite.height
    frames: list[Image.Image] = []

    # Extract cells between separator groups
    left = 0
    for start, end in groups:
        cell = composite.crop((left, 0, start, h))
        cell = _remove_magenta_bleed(cell)
        frames.append(cell)
        left = end + 1

    # Last cell after final separator
    if left < w:
        cell = composite.crop((left, 0, w, h))
        cell = _remove_magenta_bleed(cell)
        frames.append(cell)

    if len(frames) != expected_count:
        return None

    # Validate: reject tiny or extremely skewed cells
    for f in frames:
        if f.width < 4 or f.height < 4:
            return None

    logger.debug(
        "Separator detection extracted %d frames from %d dividers",
        len(frames), len(groups),
    )
    return frames


def _extract_smart_strip(
    composite: Image.Image,
    expected_count: int,
    provider: str = "openai",
    chromakey_color: str = "green",
) -> list[Image.Image]:
    """Smart extraction: separator detection, then auto-detect, then horizontal strip, then grid."""
    # Try separator detection on the RAW image first (before bg removal)
    # because _prepare_composite may destroy the magenta lines.
    sep_frames = _extract_by_separators(composite, expected_count)
    if sep_frames is not None:
        # Separator-extracted frames still have the original background.
        # For providers that use chromakey, remove it from each frame.
        if provider == "gemini":
            from pixel_magic.pipeline.chromakey import remove_chromakey
            sep_frames = [remove_chromakey(f, color=chromakey_color) for f in sep_frames]
        return sep_frames

    # Remove solid backgrounds and trim padding — AI generators often add these
    composite = _prepare_composite(composite, provider=provider, chromakey_color=chromakey_color)
    w, h = composite.size

    # For a single frame, just return the whole image
    if expected_count <= 1:
        return [composite]

    # Try horizontal strip first — works well when image is obviously wide enough
    frame_w = w // expected_count
    if _frame_aspect_ok(frame_w, h):
        logger.debug("Using horizontal strip: %dx%d per frame", frame_w, h)
        return _extract_strip(composite, expected_count, horizontal=True)

    # For non-trivial layouts, try auto-detect (progressive dilation)
    auto_frames = _extract_auto_silent(composite, expected_count)
    if auto_frames is not None:
        return auto_frames

    # Try grid layouts (AI generators commonly produce 2×3, 3×2, 2×2, etc.)
    frames = _try_grid_layouts(composite, expected_count)
    if frames:
        return frames

    # Try vertical strip
    frame_h = h // expected_count
    if _frame_aspect_ok(w, frame_h):
        logger.debug("Using vertical strip: %dx%d per frame", w, frame_h)
        return _extract_strip(composite, expected_count, horizontal=False)

    # Last resort: auto-detect with grid/strip fallbacks
    logger.info(
        "All extraction methods gave poor results for %dx%d with %d frames. "
        "Using auto-detect with fallbacks.",
        w, h, expected_count,
    )
    return _extract_auto(composite, expected_count)


def _try_grid_layouts(
    composite: Image.Image, expected_count: int
) -> list[Image.Image] | None:
    """Try plausible grid layouts, preferring the one that produces the squarest cells."""
    w, h = composite.size

    # Generate candidate (cols, rows) pairs — include 1-row (Nx1) and 1-col (1xN) strips
    valid = []
    for cols in range(1, expected_count + 1):
        rows = math.ceil(expected_count / cols)
        if cols * rows < expected_count:
            continue
        for c, r in [(cols, rows), (rows, cols)]:
            if c < 1 or r < 1 or c * r < expected_count:
                continue
            cell_w = w // c
            cell_h = h // r
            if cell_w < 1 or cell_h < 1:
                continue
            if _frame_aspect_ok(cell_w, cell_h):
                # Score: prefer exact fit (cols*rows == expected), then squarer cells
                waste = c * r - expected_count
                aspect = max(cell_w, cell_h) / max(min(cell_w, cell_h), 1)
                valid.append((waste, aspect, c, r, cell_w, cell_h))

    if not valid:
        return None

    # Pick the layout with least waste, then squarest cells
    valid.sort(key=lambda x: (x[0], x[1]))
    _, _, cols, rows, cell_w, cell_h = valid[0]
    logger.debug("Using grid layout: %d cols × %d rows → %dx%d per cell", cols, rows, cell_w, cell_h)
    return _extract_grid(composite, rows, cols, expected_count)


def _extract_strip(
    composite: Image.Image, expected_count: int, horizontal: bool
) -> list[Image.Image]:
    """Extract frames from an evenly-divided strip."""
    w, h = composite.size
    frames = []

    if horizontal:
        frame_w = w // expected_count
        for i in range(expected_count):
            x = i * frame_w
            frame = composite.crop((x, 0, x + frame_w, h))
            frames.append(frame)
    else:
        frame_h = h // expected_count
        for i in range(expected_count):
            y = i * frame_h
            frame = composite.crop((0, y, w, y + frame_h))
            frames.append(frame)

    return frames


def _extract_grid(
    composite: Image.Image, rows: int, cols: int, expected_count: int
) -> list[Image.Image]:
    """Extract frames from a grid layout."""
    w, h = composite.size
    cell_w = w // cols
    cell_h = h // rows
    frames = []

    for r in range(rows):
        for c in range(cols):
            if len(frames) >= expected_count:
                break
            x = c * cell_w
            y = r * cell_h
            frame = composite.crop((x, y, x + cell_w, y + cell_h))
            frames.append(frame)

    return frames


def _extract_auto_silent(
    composite: Image.Image,
    expected_count: int,
    provider: str = "openai",
    chromakey_color: str = "green",
) -> list[Image.Image] | None:
    """Try auto-detect; return None if it can't find the expected number of regions.

    Also validates that detected regions are reasonable — rejects results where
    any single component covers too much of the image or sizes vary wildly.
    """
    frames = _run_component_detection(composite, expected_count)
    if len(frames) != expected_count:
        return None

    # Validate: reject if any frame covers >50% of the composite area
    composite_area = composite.width * composite.height
    for f in frames:
        if f.width * f.height > composite_area * 0.5:
            logger.debug(
                "Auto-detect rejected: frame %dx%d covers >50%% of %dx%d",
                f.width, f.height, composite.width, composite.height,
            )
            return None

    # Validate: reject if largest frame is >10x the smallest (sizes should be similar)
    areas = [f.width * f.height for f in frames]
    if max(areas) > 10 * min(areas):
        logger.debug(
            "Auto-detect rejected: size ratio %d/%d > 10x",
            max(areas), min(areas),
        )
        return None

    return frames


def _run_component_detection(
    composite: Image.Image, expected_count: int
) -> list[Image.Image]:
    """Core connected-component detection with progressive dilation."""
    arr = np.array(composite)
    alpha = arr[:, :, 3]

    _, binary = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)

    # Try multiple dilation levels — start light, increase if too many fragments
    dilation_configs = [
        (3, 1),  # light
        (3, 2),  # moderate
        (5, 2),  # medium
        (5, 3),  # heavy
    ]

    best_bboxes = None
    best_diff = float("inf")

    for k_size, iters in dilation_configs:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
        dilated = cv2.dilate(binary, kernel, iterations=iters)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            dilated, connectivity=8
        )

        bboxes = []
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < 100:
                continue
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]
            bboxes.append((x, y, w, h, area))

        diff = abs(len(bboxes) - expected_count)
        if diff < best_diff:
            best_diff = diff
            best_bboxes = bboxes
        if len(bboxes) == expected_count:
            break

    bboxes = best_bboxes or []

    # Sort by y position (top to bottom), then x (left to right)
    avg_h = composite.height // max(1, expected_count)
    row_bucket = max(avg_h // 3, 20)
    bboxes.sort(key=lambda b: (b[1] // row_bucket, b[0]))

    # If more regions than expected, keep the largest
    if len(bboxes) > expected_count:
        bboxes.sort(key=lambda b: b[4], reverse=True)
        bboxes = bboxes[:expected_count]
        bboxes.sort(key=lambda b: (b[1] // row_bucket, b[0]))

    frames = []
    for x, y, w, h, _area in bboxes:
        frame = composite.crop((x, y, x + w, y + h))
        frames.append(frame)

    return frames


def _extract_auto(
    composite: Image.Image,
    expected_count: int,
    provider: str = "openai",
    chromakey_color: str = "green",
) -> list[Image.Image]:
    """Auto-detect with fallbacks to grid/strip extraction."""
    # Try separator detection on raw image first
    sep_frames = _extract_by_separators(composite, expected_count)
    if sep_frames is not None:
        if provider == "gemini":
            from pixel_magic.pipeline.chromakey import remove_chromakey
            sep_frames = [remove_chromakey(f, color=chromakey_color) for f in sep_frames]
        return sep_frames

    composite = _prepare_composite(composite, provider=provider, chromakey_color=chromakey_color)
    frames = _run_component_detection(composite, expected_count)

    if len(frames) == expected_count:
        return frames

    logger.warning(
        "Auto-detect found %d regions but expected %d. Trying grid/strip fallbacks.",
        len(frames), expected_count,
    )

    grid_frames = _try_grid_layouts(composite, expected_count)
    if grid_frames:
        return grid_frames

    w, h = composite.size
    if h > w:
        return _extract_strip(composite, expected_count, horizontal=False)
    return _extract_strip(composite, expected_count, horizontal=True)


def normalize_frame_sizes(frames: list[Image.Image]) -> list[Image.Image]:
    """Ensure all frames have the same dimensions (use the max size with centering)."""
    if not frames:
        return frames

    max_w = max(f.width for f in frames)
    max_h = max(f.height for f in frames)

    # If already uniform, return as-is
    if all(f.width == max_w and f.height == max_h for f in frames):
        return frames

    normalized = []
    for frame in frames:
        if frame.width == max_w and frame.height == max_h:
            normalized.append(frame)
        else:
            # Center the frame on a larger canvas
            canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
            offset_x = (max_w - frame.width) // 2
            offset_y = (max_h - frame.height) // 2
            canvas.paste(frame, (offset_x, offset_y))
            normalized.append(canvas)

    return normalized
