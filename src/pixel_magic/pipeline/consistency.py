"""Multi-frame consistency — palette lock, pivot alignment, jitter detection."""

from __future__ import annotations

import numpy as np
from PIL import Image

from pixel_magic.models.asset import AnimationClip, SpriteAsset
from pixel_magic.models.palette import Palette
from pixel_magic.pipeline.palette import quantize_image


def lock_palette_across_clips(
    clips: list[AnimationClip],
    palette: Palette,
) -> list[AnimationClip]:
    """Re-quantize all frames in all clips to the same shared palette.

    This ensures palette index stability across directions and animations.
    """
    for clip in clips:
        for i, frame in enumerate(clip.frames):
            quantized = quantize_image(frame.image, palette)
            clip.frames[i] = SpriteAsset(
                image=quantized,
                direction=frame.direction,
                animation_name=frame.animation_name,
                frame_index=frame.frame_index,
            )
    return clips


def compute_pivot(
    image: Image.Image,
    policy: str = "feet",
) -> tuple[float, float]:
    """Compute a normalized pivot point (0-1) for a sprite.

    Policies:
    - "feet": bottom-center of the opaque bounding box.
    - "center": center of the opaque bounding box.
    """
    arr = np.array(image)
    alpha = arr[:, :, 3]
    opaque = alpha > 128

    if not opaque.any():
        return 0.5, 0.5

    rows = np.any(opaque, axis=1)
    cols = np.any(opaque, axis=0)
    top = int(np.argmax(rows))
    bottom = int(len(rows) - np.argmax(rows[::-1]))
    left = int(np.argmax(cols))
    right = int(len(cols) - np.argmax(cols[::-1]))

    h, w = image.height, image.width

    if policy == "center":
        cx = (left + right) / 2 / w
        cy = (top + bottom) / 2 / h
        return cx, cy

    # "feet": bottom-center
    cx = (left + right) / 2 / w
    cy = bottom / h
    return cx, cy


def align_pivots(
    clip: AnimationClip,
    target_pivot: tuple[float, float] | None = None,
) -> AnimationClip:
    """Align all frames so their pivot points match.

    If target_pivot is None, use the pivot of the first frame.
    """
    if not clip.frames:
        return clip

    pivots = [compute_pivot(f.image) for f in clip.frames]

    if target_pivot is None:
        target_pivot = pivots[0]

    tx, ty = target_pivot

    for i, frame in enumerate(clip.frames):
        px, py = pivots[i]
        dx = int((tx - px) * frame.width)
        dy = int((ty - py) * frame.height)

        if dx == 0 and dy == 0:
            continue

        # Shift the image content
        shifted = _shift_image(frame.image, dx, dy)
        clip.frames[i] = SpriteAsset(
            image=shifted,
            direction=frame.direction,
            animation_name=frame.animation_name,
            frame_index=frame.frame_index,
        )

    return clip


def _shift_image(image: Image.Image, dx: int, dy: int) -> Image.Image:
    """Shift image content by (dx, dy) pixels, filling new space with transparency."""
    arr = np.array(image)
    h, w = arr.shape[:2]
    result = np.zeros_like(arr)

    # Compute source and destination slices
    src_y_start = max(0, -dy)
    src_y_end = min(h, h - dy)
    src_x_start = max(0, -dx)
    src_x_end = min(w, w - dx)

    dst_y_start = max(0, dy)
    dst_y_end = min(h, h + dy)
    dst_x_start = max(0, dx)
    dst_x_end = min(w, w + dx)

    if src_y_end > src_y_start and src_x_end > src_x_start:
        result[dst_y_start:dst_y_end, dst_x_start:dst_x_end] = \
            arr[src_y_start:src_y_end, src_x_start:src_x_end]

    return Image.fromarray(result, "RGBA")


def detect_jitter(clip: AnimationClip, threshold: float = 2.0) -> dict:
    """Detect excessive frame-to-frame jitter in an animation clip.

    Returns a report dict with jitter metrics.
    """
    if len(clip.frames) < 2:
        return {"jitter_detected": False, "max_centroid_drift": 0.0, "max_bbox_drift": 0.0}

    centroids = []
    bboxes = []

    for frame in clip.frames:
        arr = np.array(frame.image)
        alpha = arr[:, :, 3]
        opaque = alpha > 128

        if not opaque.any():
            centroids.append((0.0, 0.0))
            bboxes.append((0, 0, 0, 0))
            continue

        ys, xs = np.where(opaque)
        cx, cy = float(xs.mean()), float(ys.mean())
        centroids.append((cx, cy))
        bboxes.append((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))

    # Compute drifts between consecutive frames
    centroid_drifts = []
    bbox_drifts = []
    for i in range(1, len(centroids)):
        cx1, cy1 = centroids[i - 1]
        cx2, cy2 = centroids[i]
        centroid_drifts.append(((cx2 - cx1) ** 2 + (cy2 - cy1) ** 2) ** 0.5)

        bx1 = bboxes[i - 1]
        bx2 = bboxes[i]
        bbox_drift = max(abs(bx2[j] - bx1[j]) for j in range(4))
        bbox_drifts.append(bbox_drift)

    max_cd = max(centroid_drifts) if centroid_drifts else 0.0
    max_bbox = max(bbox_drifts) if bbox_drifts else 0.0

    return {
        "jitter_detected": max_cd > threshold or max_bbox > threshold * 2,
        "max_centroid_drift": max_cd,
        "max_bbox_drift": float(max_bbox),
        "centroid_drifts": centroid_drifts,
    }
