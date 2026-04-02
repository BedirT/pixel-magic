"""Effect animation — loop closure for subjectless VFX sprites."""

from __future__ import annotations

from PIL import Image


def enforce_loop_closure(
    frames: list[Image.Image],
    loop: bool,
) -> list[Image.Image]:
    """Make the last frame an exact copy of the first for looping effects."""
    if not loop or len(frames) < 2:
        return frames

    closed = list(frames)
    closed[-1] = closed[0].copy()
    return closed
