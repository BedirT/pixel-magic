"""Diagnose which pipeline stage corrupts sprite transparency."""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pixel_magic.config import Settings
from pixel_magic.generation.extractor import extract_frames
from pixel_magic.models.asset import CompositeLayout
from pixel_magic.pipeline.cleanup import cleanup_sprite
from pixel_magic.pipeline.palette import extract_adaptive_palette, quantize_image
from pixel_magic.workflow.executor import _normalize_frame_to_resolution


def count_opaque(img: Image.Image) -> int:
    arr = np.array(img)
    return int((arr[:, :, 3] > 0).sum())


def count_semitransparent(img: Image.Image) -> int:
    arr = np.array(img)
    a = arr[:, :, 3]
    return int(((a > 0) & (a < 255)).sum())


def save_alpha_vis(img: Image.Image, path: str):
    """Save alpha channel visualization (white=opaque, black=transparent, gray=semi)."""
    arr = np.array(img)
    alpha = arr[:, :, 3]
    vis = np.stack([alpha, alpha, alpha], axis=-1)
    Image.fromarray(vis, "RGB").save(path)


def main():
    settings = Settings()
    diag_dir = Path("output/_diagnostics")
    diag_dir.mkdir(parents=True, exist_ok=True)

    # Use whichever raw image exists
    for name in ["backpack_kid", "fire_mage"]:
        raw_path = Path(f"output/{name}/raw/character_sheet.png")
        if not raw_path.exists():
            print(f"Skipping {name} — no raw image found")
            continue

        print(f"\n{'='*60}")
        print(f"Diagnosing: {name}")
        print(f"{'='*60}")

        raw = Image.open(raw_path).convert("RGBA")
        prefix = diag_dir / name

        # Stage 0: Raw
        print(f"\n[RAW] size={raw.size}, opaque={count_opaque(raw)}, semi={count_semitransparent(raw)}")
        save_alpha_vis(raw, f"{prefix}_0_raw_alpha.png")

        # Stage 1: Extract frames
        frames = extract_frames(
            raw,
            CompositeLayout.REFERENCE_SHEET,
            expected_count=2,
            provider="openai",
            chromakey_color="green",
        )
        for i, f in enumerate(frames):
            print(f"\n[EXTRACT frame {i}] size={f.size}, opaque={count_opaque(f)}, semi={count_semitransparent(f)}")
            f.save(f"{prefix}_1_extract_{i}.png")
            save_alpha_vis(f, f"{prefix}_1_extract_{i}_alpha.png")

        # Stage 2: Normalize (LANCZOS downscale + binary alpha)
        target_size = (64, 64)
        normalized = []
        for i, f in enumerate(frames):
            norm, detail = _normalize_frame_to_resolution(f, target_size=target_size, settings=settings)
            normalized.append(norm)
            print(f"\n[NORMALIZE frame {i}] size={norm.size}, opaque={count_opaque(norm)}, semi={count_semitransparent(norm)}, method={detail['method']}")
            norm.save(f"{prefix}_2_normalize_{i}.png")
            save_alpha_vis(norm, f"{prefix}_2_normalize_{i}_alpha.png")

        # Stage 3: Quantize
        palette = extract_adaptive_palette(normalized, 16)
        if settings.enforce_outline:
            outline_color = (0, 0, 0, 255)
            if outline_color not in palette.colors:
                palette.colors.append(outline_color)
        quantized = []
        for i, f in enumerate(normalized):
            q = quantize_image(f, palette)
            quantized.append(q)
            print(f"\n[QUANTIZE frame {i}] size={q.size}, opaque={count_opaque(q)}, semi={count_semitransparent(q)}")
            q.save(f"{prefix}_3_quantize_{i}.png")
            save_alpha_vis(q, f"{prefix}_3_quantize_{i}_alpha.png")

        # Stage 4: Cleanup
        for i, f in enumerate(quantized):
            cleaned = cleanup_sprite(
                f,
                palette.colors,
                settings.min_island_size,
                settings.max_hole_size,
                settings.enforce_outline,
            )
            print(f"\n[CLEANUP frame {i}] size={cleaned.size}, opaque={count_opaque(cleaned)}, semi={count_semitransparent(cleaned)}")
            cleaned.save(f"{prefix}_4_cleanup_{i}.png")
            save_alpha_vis(cleaned, f"{prefix}_4_cleanup_{i}_alpha.png")

        # Also test: LANCZOS downscale with lower alpha threshold
        print(f"\n--- Alternative: alpha threshold=64 ---")
        for i, f in enumerate(frames):
            from PIL import Image as PILImage
            scale = min(64 / f.width, 64 / f.height)
            resized_size = (max(1, round(f.width * scale)), max(1, round(f.height * scale)))
            resized = f.resize(resized_size, Image.LANCZOS)
            r, g, b, a = resized.split()
            # Lower threshold
            a_low = a.point(lambda v: 255 if v >= 64 else 0)
            result_low = Image.merge("RGBA", (r, g, b, a_low))
            # Center on canvas
            canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            px = (64 - result_low.width) // 2
            py = (64 - result_low.height) // 2
            canvas.paste(result_low, (px, py))
            print(f"[ALT threshold=64 frame {i}] opaque={count_opaque(canvas)}")
            canvas.save(f"{prefix}_alt_thresh64_{i}.png")

        # Also test: NEAREST downscale (no alpha issue)
        print(f"\n--- Alternative: NEAREST downscale ---")
        for i, f in enumerate(frames):
            resized = f.resize((64, 64), Image.NEAREST)
            print(f"[ALT NEAREST frame {i}] opaque={count_opaque(resized)}, semi={count_semitransparent(resized)}")
            resized.save(f"{prefix}_alt_nearest_{i}.png")

    print(f"\nDiagnostics saved to {diag_dir}/")


if __name__ == "__main__":
    main()
