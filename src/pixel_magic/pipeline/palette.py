"""Palette quantization and dithering — fixed, adaptive, and shared modes."""

from __future__ import annotations

import numpy as np
from PIL import Image

from pixel_magic.models.palette import DitherConfig, DitherType, Palette, PaletteMode


# ── OKLab conversion helpers (for perceptual distance) ────────────────

def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    """Convert sRGB [0,1] to linear RGB."""
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    """Convert linear RGB to sRGB [0,1]."""
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)


def rgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    """Convert RGB [0,255] uint8 array (..., 3) to OKLab (..., 3)."""
    rgb_f = rgb.astype(np.float64) / 255.0
    linear = _srgb_to_linear(rgb_f)

    l = 0.4122214708 * linear[..., 0] + 0.5363325363 * linear[..., 1] + 0.0514459929 * linear[..., 2]
    m = 0.2119034982 * linear[..., 0] + 0.6806995451 * linear[..., 1] + 0.1073969566 * linear[..., 2]
    s = 0.0883024619 * linear[..., 0] + 0.2817188376 * linear[..., 1] + 0.6299787005 * linear[..., 2]

    l_ = np.cbrt(l)
    m_ = np.cbrt(m)
    s_ = np.cbrt(s)

    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

    return np.stack([L, a, b], axis=-1)


def oklab_distance(c1: np.ndarray, c2: np.ndarray) -> np.ndarray:
    """Euclidean distance in OKLab space."""
    diff = c1 - c2
    return np.sqrt(np.sum(diff ** 2, axis=-1))


# ── Palette extraction ────────────────────────────────────────────────

def extract_adaptive_palette(
    images: list[Image.Image],
    max_colors: int = 16,
) -> Palette:
    """Extract an adaptive palette from one or more images using k-means in OKLab.

    For multi-frame (shared palette mode), pass all frames.
    """
    # Collect all opaque pixels
    all_pixels = []
    for img in images:
        arr = np.array(img)
        alpha = arr[:, :, 3]
        opaque_mask = alpha > 128
        rgb = arr[:, :, :3][opaque_mask]
        if rgb.size > 0:
            all_pixels.append(rgb)

    if not all_pixels:
        # Fallback: just black
        return Palette(name="adaptive", colors=[(0, 0, 0, 255)])

    pixels = np.concatenate(all_pixels, axis=0)

    # Subsample for performance if too many pixels
    if len(pixels) > 50000:
        rng = np.random.default_rng(42)
        indices = rng.choice(len(pixels), 50000, replace=False)
        pixels = pixels[indices]

    # K-means in OKLab space
    lab_pixels = rgb_to_oklab(pixels)
    centers = _kmeans_oklab(lab_pixels, max_colors, max_iters=20)

    # Convert centers back to sRGB
    colors = _oklab_centers_to_rgb(centers)

    return Palette(
        name="adaptive",
        colors=[(int(r), int(g), int(b), 255) for r, g, b in colors],
    )


def _kmeans_oklab(pixels: np.ndarray, k: int, max_iters: int = 20) -> np.ndarray:
    """Simple k-means clustering in OKLab space."""
    n = len(pixels)
    if n <= k:
        return pixels.copy()

    # Initialize with k-means++ style
    rng = np.random.default_rng(42)
    centers = np.zeros((k, 3), dtype=np.float64)
    centers[0] = pixels[rng.integers(n)]

    for i in range(1, k):
        dists = np.min([oklab_distance(pixels, centers[j]) for j in range(i)], axis=0)
        total = dists.sum()
        if total < 1e-10:
            # All remaining points are identical to existing centers
            centers[i] = pixels[rng.integers(n)]
        else:
            probs = dists / total
            centers[i] = pixels[rng.choice(n, p=probs)]

    for _ in range(max_iters):
        # Assign each pixel to nearest center
        dists = np.stack([oklab_distance(pixels, c) for c in centers], axis=-1)
        labels = np.argmin(dists, axis=-1)

        # Update centers
        new_centers = np.zeros_like(centers)
        for j in range(k):
            mask = labels == j
            if mask.any():
                new_centers[j] = pixels[mask].mean(axis=0)
            else:
                new_centers[j] = centers[j]

        if np.allclose(new_centers, centers, atol=1e-5):
            break
        centers = new_centers

    return centers


def _oklab_centers_to_rgb(centers: np.ndarray) -> np.ndarray:
    """Convert OKLab centers back to sRGB [0,255]."""
    L, a, b = centers[:, 0], centers[:, 1], centers[:, 2]

    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3

    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b_out = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    linear = np.stack([r, g, b_out], axis=-1)
    srgb = _linear_to_srgb(np.clip(linear, 0, 1))
    return np.clip(srgb * 255, 0, 255).astype(np.uint8)


# ── Quantization ──────────────────────────────────────────────────────

def quantize_image(
    image: Image.Image,
    palette: Palette,
    dither: DitherConfig | None = None,
) -> Image.Image:
    """Map every pixel to the nearest palette color. Optionally apply dithering."""
    arr = np.array(image)
    alpha = arr[:, :, 3].copy()
    rgb = arr[:, :, :3]

    # Build palette array in OKLab
    pal_rgb = np.array([c[:3] for c in palette.colors], dtype=np.uint8)
    pal_lab = rgb_to_oklab(pal_rgb)

    if dither is None or dither.type == DitherType.NONE:
        result_rgb = _nearest_palette(rgb, pal_rgb, pal_lab)
    elif dither.type == DitherType.ORDERED:
        result_rgb = _ordered_dither(rgb, pal_rgb, pal_lab, dither)
    else:
        result_rgb = _error_diffusion(rgb, pal_rgb, pal_lab, dither)

    out = np.zeros_like(arr)
    out[:, :, :3] = result_rgb
    out[:, :, 3] = alpha

    return Image.fromarray(out, "RGBA")


def _nearest_palette(rgb: np.ndarray, pal_rgb: np.ndarray, pal_lab: np.ndarray) -> np.ndarray:
    """Map each pixel to nearest palette color in OKLab space."""
    h, w = rgb.shape[:2]
    flat = rgb.reshape(-1, 3)
    flat_lab = rgb_to_oklab(flat)

    # Distance to each palette color
    dists = np.stack(
        [oklab_distance(flat_lab, pal_lab[i]) for i in range(len(pal_lab))],
        axis=-1,
    )
    indices = np.argmin(dists, axis=-1)

    result = pal_rgb[indices].reshape(h, w, 3)
    return result


def _ordered_dither(
    rgb: np.ndarray, pal_rgb: np.ndarray, pal_lab: np.ndarray, dither: DitherConfig
) -> np.ndarray:
    """Ordered (Bayer) dithering into a palette."""
    bayer = _bayer_matrix(dither.bayer_size.value)
    h, w = rgb.shape[:2]

    # Tile the bayer matrix across the image
    bh, bw = bayer.shape
    tiled = np.tile(bayer, (h // bh + 1, w // bw + 1))[:h, :w]

    # Scale bayer to [-strength, +strength] range in [0,255]
    strength = dither.strength * 32  # approximate spread in RGB units
    noise = (tiled - 0.5) * 2 * strength

    # Add noise to RGB
    rgb_f = rgb.astype(np.float32)
    rgb_f[:, :, 0] += noise
    rgb_f[:, :, 1] += noise
    rgb_f[:, :, 2] += noise
    rgb_noisy = np.clip(rgb_f, 0, 255).astype(np.uint8)

    return _nearest_palette(rgb_noisy, pal_rgb, pal_lab)


def _error_diffusion(
    rgb: np.ndarray, pal_rgb: np.ndarray, pal_lab: np.ndarray, dither: DitherConfig
) -> np.ndarray:
    """Floyd-Steinberg error diffusion into a palette."""
    h, w = rgb.shape[:2]
    img = rgb.astype(np.float32).copy()
    result = np.zeros_like(rgb)
    strength = dither.strength

    for y in range(h):
        for x in range(w):
            old_pixel = img[y, x].copy()
            old_lab = rgb_to_oklab(old_pixel.reshape(1, 3).astype(np.uint8))

            # Find nearest palette color
            dists = np.array([oklab_distance(old_lab, pal_lab[i : i + 1]) for i in range(len(pal_lab))])
            idx = int(np.argmin(dists))
            new_pixel = pal_rgb[idx].astype(np.float32)
            result[y, x] = pal_rgb[idx]

            error = (old_pixel - new_pixel) * strength

            # Distribute error (Floyd-Steinberg coefficients)
            if x + 1 < w:
                img[y, x + 1] += error * 7 / 16
            if y + 1 < h:
                if x - 1 >= 0:
                    img[y + 1, x - 1] += error * 3 / 16
                img[y + 1, x] += error * 5 / 16
                if x + 1 < w:
                    img[y + 1, x + 1] += error * 1 / 16

    return result


def _bayer_matrix(size: int) -> np.ndarray:
    """Generate a Bayer dithering matrix of given size, normalized to [0,1]."""
    if size == 2:
        return np.array([[0, 2], [3, 1]], dtype=np.float32) / 4
    if size == 4:
        b2 = _bayer_matrix(2) * 4
        return np.block([
            [b2, b2 + 2],
            [b2 + 3, b2 + 1],
        ]) / 16
    # size == 8
    b4 = _bayer_matrix(4) * 4
    return np.block([
        [b4, b4 + 2],
        [b4 + 3, b4 + 1],
    ]) / 64
