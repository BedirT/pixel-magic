#!/usr/bin/env python3
"""Render the Ember Depths isometric scene as an animated GIF.

Replicates the same scene as index.html but in Python/Pillow,
producing a compact GIF suitable for README embedding.

Usage:
    uv run python showcase/render_gif.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

SHOWCASE = Path(__file__).parent
ASSETS = SHOWCASE / "assets"
TILE_DIR = ASSETS / "tiles" / "tiles" / "custom"
OBJ_DIR = ASSETS / "objects" / "objects" / "custom"
CHAR_DIR = ASSETS / "characters"
FX_DIR = ASSETS / "effects" / "effects"

# ─── Map / layout config ─────────────────────────────────────────────
TILE_W, TILE_H = 64, 36
MAP_COLS, MAP_ROWS = 10, 10
GIF_FRAMES = 24       # total frames in the GIF loop
FRAME_DELAY_MS = 125  # 8 FPS

TILES = [
    "grass", "moss_stone", "cracked_path", "flowers",
    "dark_stone", "crystal_floor", "glowing_moss", "gravel",
    "basalt", "lava", "cracked_obsidian", "cooled_lava",
    "water_puddle", "underground_water", "magma_vein", "ash",
]

MAP = [
    [0, 0, 3, 0, 0, 3, 0, 0, 0, 3],
    [0, 3, 0, 0, 2, 2, 0, 3, 0, 0],
    [0, 0, 2, 2, 1, 1, 2, 0, 0, 0],
    [1, 2, 1, 12, 2, 2, 12, 1, 2, 0],
    [4, 4, 7, 4, 5, 5, 4, 7, 4, 4],
    [4, 6, 4, 5, 4, 13, 5, 4, 6, 4],
    [7, 4, 5, 4, 7, 4, 4, 5, 4, 7],
    [8, 8, 11, 8, 8, 10, 8, 8, 11, 8],
    [8, 10, 9, 8, 14, 8, 9, 10, 8, 15],
    [15, 8, 9, 9, 8, 15, 9, 9, 8, 8],
]

OBJECTS = [
    {"row": 0, "col": 6, "img": "mushroom", "scale": 0.55, "oy": -42},
    {"row": 1, "col": 7, "img": "overgrown_statue", "scale": 0.42, "oy": -50},
    {"row": 2, "col": 0, "img": "broken_pillar", "scale": 0.5, "oy": -38},
    {"row": 3, "col": 8, "img": "vine_archway", "scale": 0.45, "oy": -45},
    {"row": 5, "col": 1, "img": "crystal_cluster", "scale": 0.6, "oy": -32},
    {"row": 6, "col": 7, "img": "cave_torch", "scale": 0.65, "oy": -32},
    {"row": 4, "col": 7, "img": "stalactite", "scale": 0.55, "oy": -38},
    {"row": 7, "col": 5, "img": "obsidian_spike", "scale": 0.45, "oy": -42},
    {"row": 8, "col": 1, "img": "fire_brazier", "scale": 0.48, "oy": -40},
    {"row": 9, "col": 6, "img": "magma_crystal", "scale": 0.5, "oy": -38},
    {"row": 9, "col": 3, "img": "dragon_egg", "scale": 0.5, "oy": -28},
    {"row": 3, "col": 3, "img": "ancient_chest", "scale": 0.55, "oy": -30},
]

CHARACTERS = [
    {"row": 1, "col": 2, "name": "forest-goblin", "scale": 0.14, "oy": -52},
    {"row": 5, "col": 5, "name": "cave-bat", "scale": 0.12, "oy": -48},
    {"row": 8, "col": 7, "name": "fire-imp", "scale": 0.12, "oy": -48},
]

KNIGHT_PATH = [
    (1, 4), (2, 4), (3, 4), (4, 4), (5, 4), (6, 4), (7, 4), (8, 4),
    (8, 3), (7, 3), (6, 3), (5, 3), (4, 3), (3, 3), (2, 3), (1, 3),
]

EFFECTS = [
    {"row": 9, "col": 1, "name": "lava-bubble", "frames": 5, "scale": 0.35, "oy": -18},
    {"row": 8, "col": 5, "name": "fire-explosion", "frames": 6, "scale": 0.4, "oy": -25},
    {"row": 6, "col": 2, "name": "healing-glow", "frames": 6, "scale": 0.35, "oy": -20},
]


def iso_to_screen(row: int, col: int) -> tuple[int, int]:
    return (col - row) * (TILE_W // 2), (col + row) * (TILE_H // 2)


def load_and_scale(path: Path, scale: float) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    w, h = int(img.width * scale), int(img.height * scale)
    return img.resize((w, h), Image.NEAREST)


def paste_centered(canvas: Image.Image, sprite: Image.Image, row: int, col: int,
                    ox: int, oy_offset: int, oy: int) -> None:
    sx, sy = iso_to_screen(row, col)
    x = sx + ox + (TILE_W - sprite.width) // 2
    y = sy + oy_offset + oy
    canvas.paste(sprite, (x, y), sprite)


def main() -> None:
    # Compute canvas bounds
    corners = [iso_to_screen(r, c) for r, c in [(0, 0), (0, 9), (9, 0), (9, 9)]]
    min_x = min(c[0] for c in corners)
    max_x = max(c[0] for c in corners) + TILE_W
    min_y = min(c[1] for c in corners)
    max_y = max(c[1] for c in corners) + TILE_H

    PAD_TOP, PAD_BOTTOM, PAD_SIDE = 120, 60, 30
    canvas_w = (max_x - min_x) + PAD_SIDE * 2
    canvas_h = (max_y - min_y) + PAD_TOP + PAD_BOTTOM
    ox = -min_x + PAD_SIDE
    oy = -min_y + PAD_TOP

    # Pre-load all images
    print("Loading assets...")
    tile_imgs = {}
    for name in TILES:
        p = TILE_DIR / f"{name}.png"
        if p.exists():
            tile_imgs[name] = Image.open(p).convert("RGBA")

    obj_imgs = {}
    for o in OBJECTS:
        p = OBJ_DIR / f"{o['img']}.png"
        if p.exists():
            obj_imgs[o["img"]] = load_and_scale(p, o["scale"])

    char_imgs = {}
    for c in CHARACTERS:
        p = CHAR_DIR / c["name"] / "views" / "front_left.png"
        if p.exists():
            char_imgs[c["name"]] = load_and_scale(p, c["scale"])

    knight_walk = []
    for i in range(1, 7):
        p = CHAR_DIR / "ember-knight" / "animations" / "walk" / f"frame_0{i}.png"
        if p.exists():
            knight_walk.append(load_and_scale(p, 0.15))
    knight_scale = 0.15

    fx_frames: dict[str, list[Image.Image]] = {}
    for e in EFFECTS:
        frames = []
        for i in range(1, e["frames"] + 1):
            p = FX_DIR / e["name"] / f"frame_0{i}.png"
            if p.exists():
                frames.append(load_and_scale(p, e["scale"]))
        fx_frames[e["name"]] = frames

    # Background: dark gradient
    bg = Image.new("RGBA", (canvas_w, canvas_h), (26, 26, 46, 255))
    # Simple vertical gradient
    for y_px in range(canvas_h):
        t = y_px / canvas_h
        r = int(26 + (46 - 26) * t)
        g = int(42 - 16 * t)
        b = int(26 + (20) * t)
        for x_px in range(canvas_w):
            bg.putpixel((x_px, y_px), (r, g, b, 255))

    print(f"Rendering {GIF_FRAMES} frames at {canvas_w}x{canvas_h}...")

    gif_frames: list[Image.Image] = []
    knight_path_idx = 0.0
    knight_step = len(KNIGHT_PATH) / GIF_FRAMES  # complete one full loop

    for frame_num in range(GIF_FRAMES):
        canvas = bg.copy()

        # Collect drawables: (depth, draw_fn)
        drawables: list[tuple[float, callable]] = []

        # Tiles
        for row in range(MAP_ROWS):
            for col in range(MAP_COLS):
                tile_name = TILES[MAP[row][col]]
                tile_img = tile_imgs.get(tile_name)
                if tile_img:
                    sx, sy = iso_to_screen(row, col)

                    def draw_tile(img=tile_img, x=sx + ox, y=sy + oy):
                        canvas.paste(img, (x, y), img)

                    drawables.append((row + col, draw_tile))

        # Objects
        for o in OBJECTS:
            img = obj_imgs.get(o["img"])
            if img:
                def draw_obj(img=img, r=o["row"], c=o["col"], oy_off=o["oy"]):
                    paste_centered(canvas, img, r, c, ox, oy, oy_off)
                drawables.append((o["row"] + o["col"] + 0.5, draw_obj))

        # Characters
        for c in CHARACTERS:
            img = char_imgs.get(c["name"])
            if img:
                def draw_char(img=img, r=c["row"], c_=c["col"], oy_off=c["oy"]):
                    paste_centered(canvas, img, r, c_, ox, oy, oy_off)
                drawables.append((c["row"] + c["col"] + 0.6, draw_char))

        # Knight
        if knight_walk:
            walk_idx = frame_num % len(knight_walk)
            path_pos = knight_path_idx
            p_idx = int(path_pos) % len(KNIGHT_PATH)
            p_next = (p_idx + 1) % len(KNIGHT_PATH)
            t = path_pos - int(path_pos)
            r1, c1 = KNIGHT_PATH[p_idx]
            r2, c2 = KNIGHT_PATH[p_next]
            kr = r1 + (r2 - r1) * t
            kc = c1 + (c2 - c1) * t
            sx, sy = iso_to_screen(0, 0)
            ksx = (kc - kr) * (TILE_W // 2)
            ksy = (kc + kr) * (TILE_H // 2)
            kimg = knight_walk[walk_idx]
            depth = kr + kc + 0.7

            def draw_knight(img=kimg, ksx_=ksx, ksy_=ksy):
                x = int(ksx_) + ox + (TILE_W - img.width) // 2
                y = int(ksy_) + oy - 55
                canvas.paste(img, (x, y), img)

            drawables.append((depth, draw_knight))
            knight_path_idx += knight_step

        # Effects
        for e in EFFECTS:
            frames = fx_frames.get(e["name"], [])
            if frames:
                fx_idx = frame_num % len(frames)
                fx_img = frames[fx_idx]

                def draw_fx(img=fx_img, r=e["row"], c=e["col"], oy_off=e["oy"]):
                    paste_centered(canvas, img, r, c, ox, oy, oy_off)

                drawables.append((e["row"] + e["col"] + 0.8, draw_fx))

        # Sort by depth, draw
        drawables.sort(key=lambda d: d[0])
        for _, draw_fn in drawables:
            draw_fn()

        # Convert to P mode for GIF (with transparency)
        rgb = canvas.convert("RGB")
        gif_frames.append(rgb)
        print(f"  Frame {frame_num + 1}/{GIF_FRAMES}")

    # Save GIF
    out_path = SHOWCASE / "ember_depths.gif"
    print(f"Saving GIF to {out_path}...")
    gif_frames[0].save(
        out_path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=FRAME_DELAY_MS,
        loop=0,
        optimize=True,
    )
    size_kb = out_path.stat().st_size / 1024
    print(f"Done! {out_path.name} — {size_kb:.0f} KB, {GIF_FRAMES} frames @ {1000//FRAME_DELAY_MS} FPS")


if __name__ == "__main__":
    main()
