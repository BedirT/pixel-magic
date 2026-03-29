# Grid Canvas + Frame Numbers Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the horizontal strip canvas with a 16:9-ish grid layout, add pixel-art frame numbers to empty slots, and auto-scale characters based on tile count so the canvas stays compact.

**Architecture:** Frames are arranged in a cols×rows grid that best approximates 16:9 given slot dimensions. Each empty slot gets a 3×5 pixel digit (scaled up) in its top-left corner so Gemini knows the sequence order. The platform removal pass also strips frame numbers. Character scale decreases for larger tile grids, keeping slot width bounded.

**Tech Stack:** Pillow (ImageDraw for grid layout + digit rendering), existing Gemini pipeline.

---

## Current State

- `build_canvas()` creates a **horizontal strip** — all frames in a single row
- `extract_frames()` divides strip width by frame count
- `composite_on_platform()` uses fixed `char_scale=0.8` regardless of tile count
- Canvas dimensions grow linearly with frame count (6×345px = ~2070px wide)
- No frame numbers — Gemini relies on left-to-right ordering

## Key Constraints

- **Gemini input/output:** Roughly preserves input dimensions. Natural 16:9 images work better than extreme aspect ratios.
- **Pixel art style:** Frame numbers must be pixel-art styled (hard edges, no anti-aliasing).
- **Loop mode:** First and last slots always show the reference frame (identical anchors).
- **Backwards compat:** `assemble_sprite_sheet()` output remains a horizontal strip for GIF/game engine consumption. The grid is only for the Gemini canvas.

## Design Decisions

### Grid layout algorithm

Given N frames with slot dimensions (w, h), find (cols, rows) where:
- `cols × rows >= N` (enough cells)
- `(cols × w) / (rows × h)` is closest to 16/9

```
4 frames:  2×2          6 frames:  3×2          8 frames:  4×2
 [1][2]     [1][2][3]    [1][2][3][4]
 [3][4]     [4][5][6]    [5][6][7][8]

9 frames:  3×3
 [1][2][3]
 [4][5][6]
 [7][8][9]
```

If grid has more cells than frames (e.g. 5 frames in 3×2 = 6 cells), the extra cell stays chromakey-filled with no number.

### Auto char_scale per tile grid

Larger tile grids → smaller character → slot width stays bounded:

```
grid_size=1 (1 tile):   char_scale = 0.80  →  205px  (for 256px base)
grid_size=2 (4 tiles):  char_scale = 0.55  →  141px
grid_size=3 (9 tiles):  char_scale = 0.40  →  102px
```

Canvas width estimates (256px base, 6 frames in 3×2 grid):

| Tiles | char_scale | Slot width | Canvas (3×2) |
|-------|-----------|-----------|-------------|
| 1     | 0.80      | ~235px    | ~705×800    |
| 4     | 0.55      | ~325px    | ~975×800    |
| 9     | 0.40      | ~353px    | ~1059×800   |

All well within Gemini's comfort zone.

### Pixel digit rendering

Hardcoded 3×5 pixel bitmaps for digits 0-9. Each pixel scaled up by a factor proportional to slot width (`max(2, slot_width // 60)`). Drawn in white with a 1px black outline shadow. Positioned in the top-left corner of each slot with a small margin.

For two-digit numbers (10+), digits rendered side-by-side with 1px gap.

Numbers are drawn on ALL slots, then reference frames are pasted on top (hiding the numbers underneath the character). Result: numbers visible only on empty slots.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/pixel_magic/animate.py` | Modify | Grid layout calc, pixel digits, rewrite `build_canvas()` + `extract_frames()` |
| `src/pixel_magic/platform.py` | Modify | Auto char_scale in `composite_on_platform()` |
| `src/pixel_magic/prompts.py` | Modify | Grid layout description in prompts, number removal in cleaning prompt |

No new files. No CLI changes needed (`--tiles` and `--frames` already exist).

---

### Task 1: Pixel digit renderer in animate.py

**Files:**
- Modify: `src/pixel_magic/animate.py`

Add the hardcoded 3×5 pixel bitmaps and a function to draw a frame number onto an image.

- [ ] **Step 1: Add digit bitmap constants**

Add after the imports in `animate.py`:

```python
import math

# 3×5 pixel bitmaps for digits 0-9 (each row is a 3-bit mask, MSB = left)
_DIGIT_BITMAPS: dict[int, list[int]] = {
    0: [0b111, 0b101, 0b101, 0b101, 0b111],
    1: [0b010, 0b110, 0b010, 0b010, 0b111],
    2: [0b111, 0b001, 0b111, 0b100, 0b111],
    3: [0b111, 0b001, 0b111, 0b001, 0b111],
    4: [0b101, 0b101, 0b111, 0b001, 0b001],
    5: [0b111, 0b100, 0b111, 0b001, 0b111],
    6: [0b111, 0b100, 0b111, 0b101, 0b111],
    7: [0b111, 0b001, 0b001, 0b010, 0b010],
    8: [0b111, 0b101, 0b111, 0b101, 0b111],
    9: [0b111, 0b101, 0b111, 0b001, 0b111],
}
```

- [ ] **Step 2: Add `_draw_frame_number()` function**

```python
def _draw_frame_number(
    canvas: Image.Image,
    number: int,
    slot_x: int,
    slot_y: int,
    slot_width: int,
) -> None:
    """Draw a pixel-art frame number in the top-left corner of a slot."""
    scale = max(2, slot_width // 60)
    margin = scale * 2
    digit_w = 3 * scale
    digit_h = 5 * scale
    gap = scale  # gap between multi-digit numbers

    digits = [int(d) for d in str(number)]

    # Starting position (top-left corner of slot + margin)
    x0 = slot_x + margin
    y0 = slot_y + margin

    for digit in digits:
        bitmap = _DIGIT_BITMAPS[digit]
        for row_idx, row_bits in enumerate(bitmap):
            for col_idx in range(3):
                if row_bits & (1 << (2 - col_idx)):
                    # Draw scaled pixel block
                    px = x0 + col_idx * scale
                    py = y0 + row_idx * scale
                    # Black outline (1px border around each block)
                    for dx in range(-1, scale + 1):
                        for dy in range(-1, scale + 1):
                            cx, cy = px + dx, py + dy
                            if 0 <= cx < canvas.width and 0 <= cy < canvas.height:
                                canvas.putpixel((cx, cy), (0, 0, 0, 255))
                    # White fill
                    for dx in range(scale):
                        for dy in range(scale):
                            canvas.putpixel((px + dx, py + dy), (255, 255, 255, 255))
        x0 += digit_w + gap
```

- [ ] **Step 3: Verify visually**

```bash
uv run python -c "
from PIL import Image
from pixel_magic.animate import _draw_frame_number
img = Image.new('RGBA', (400, 400), (0, 255, 0, 255))
for i in range(1, 10):
    _draw_frame_number(img, i, ((i-1) % 3) * 130, ((i-1) // 3) * 130, 130)
img.save('/tmp/test_digits.png')
print('saved /tmp/test_digits.png')
"
```

Open `/tmp/test_digits.png` and verify: 9 white pixel-art digits on green, each with black outline, properly positioned.

- [ ] **Step 4: Commit**

```bash
git add src/pixel_magic/animate.py
git commit -m "feat: add pixel-art digit renderer for frame numbers"
```

---

### Task 2: Grid layout calculator in animate.py

**Files:**
- Modify: `src/pixel_magic/animate.py`

- [ ] **Step 1: Add `_grid_layout()` function**

Add after the digit constants:

```python
def _grid_layout(n_frames: int, slot_w: int, slot_h: int) -> tuple[int, int]:
    """Find (cols, rows) grid closest to 16:9 aspect ratio.

    Returns (cols, rows) where cols * rows >= n_frames.
    """
    target = 16 / 9
    best = (n_frames, 1)
    best_diff = float("inf")

    for cols in range(1, n_frames + 1):
        rows = math.ceil(n_frames / cols)
        ratio = (cols * slot_w) / (rows * slot_h)
        diff = abs(ratio - target)
        if diff < best_diff:
            best_diff = diff
            best = (cols, rows)

    return best
```

- [ ] **Step 2: Verify grid calculations**

```bash
uv run python -c "
from pixel_magic.animate import _grid_layout
# Square-ish slots (~325x400)
for n in [4, 5, 6, 8, 9]:
    cols, rows = _grid_layout(n, 325, 400)
    ratio = (cols * 325) / (rows * 400)
    print(f'{n} frames: {cols}x{rows} grid, ratio={ratio:.2f} (target=1.78)')
"
```

Expected: grids approximate 16:9 (e.g. 6→3×2, 4→2×2, 9→4×3 or 3×3 depending on slot shape).

- [ ] **Step 3: Commit**

```bash
git add src/pixel_magic/animate.py
git commit -m "feat: add grid layout calculator targeting 16:9 aspect ratio"
```

---

### Task 3: Rewrite `build_canvas()` for grid layout + frame numbers

**Files:**
- Modify: `src/pixel_magic/animate.py`

The function now returns `(canvas, cols)` so `extract_frames` can use the same grid dimensions.

- [ ] **Step 1: Rewrite `build_canvas()`**

Replace the entire `build_canvas` function:

```python
def build_canvas(
    reference_frame: Image.Image,
    total_frames: int,
    chromakey_color: str = "green",
    slot_bg: Image.Image | None = None,
    loop: bool = False,
) -> tuple[Image.Image, int]:
    """Build a sprite sheet canvas with frames arranged in a grid.

    Frames are laid out in a cols×rows grid approximating 16:9 aspect ratio.
    Empty slots get a pixel-art frame number in the top-left corner.

    If loop=True, the reference is placed in both slot 1 and the last slot.
    If slot_bg is provided, it's placed in every slot (behind reference).

    Returns (canvas, cols) — cols needed by extract_frames().
    """
    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (0, 255, 0))

    w, h = reference_frame.size
    cols, rows = _grid_layout(total_frames, w, h)

    canvas = Image.new("RGBA", (w * cols, h * rows), (*fill, 255))

    # Place slot backgrounds and frame numbers on all slots
    for idx in range(total_frames):
        col = idx % cols
        row = idx // cols
        x, y = col * w, row * h

        if slot_bg is not None:
            canvas.paste(slot_bg, (x, y), slot_bg if slot_bg.mode == "RGBA" else None)

        _draw_frame_number(canvas, idx + 1, x, y, w)

    # Place reference in slot 1 (covers frame number underneath)
    canvas.paste(
        reference_frame, (0, 0),
        reference_frame if reference_frame.mode == "RGBA" else None,
    )

    # Loop: also place reference in last slot
    if loop:
        last_idx = total_frames - 1
        lx = (last_idx % cols) * w
        ly = (last_idx // cols) * h
        canvas.paste(
            reference_frame, (lx, ly),
            reference_frame if reference_frame.mode == "RGBA" else None,
        )

    return canvas, cols
```

- [ ] **Step 2: Update `generate_animation()` to use new return type**

In `generate_animation()`, change the canvas build line from:

```python
canvas = build_canvas(ref_composite, total_frames, chromakey_color, slot_bg=slot_bg, loop=loop)
```

to:

```python
canvas, grid_cols = build_canvas(ref_composite, total_frames, chromakey_color, slot_bg=slot_bg, loop=loop)
```

And update the `extract_frames` call from:

```python
frames = extract_frames(result.image, total_frames)
```

to:

```python
frames = extract_frames(result.image, total_frames, cols=grid_cols)
```

Also update the print line to show grid dimensions:

```python
grid_rows = math.ceil(total_frames / grid_cols)
print(f"  Canvas: {canvas.width}x{canvas.height} ({grid_cols}×{grid_rows} grid, {total_frames} frames)")
```

- [ ] **Step 3: Commit**

```bash
git add src/pixel_magic/animate.py
git commit -m "feat: build_canvas uses grid layout with frame numbers"
```

---

### Task 4: Rewrite `extract_frames()` for grid extraction

**Files:**
- Modify: `src/pixel_magic/animate.py`

- [ ] **Step 1: Update `extract_frames()` to accept `cols` parameter**

Replace the entire function:

```python
def extract_frames(
    sheet: Image.Image,
    total_frames: int,
    cols: int | None = None,
) -> list[Image.Image]:
    """Extract frames from a grid-layout sprite sheet.

    If cols is None, falls back to horizontal strip (legacy).
    """
    if cols is None:
        cols = total_frames
    rows = math.ceil(total_frames / cols)
    slot_w = sheet.width // cols
    slot_h = sheet.height // rows

    frames = []
    for idx in range(total_frames):
        col = idx % cols
        row = idx // cols
        frame = sheet.crop((col * slot_w, row * slot_h, (col + 1) * slot_w, (row + 1) * slot_h))
        frames.append(frame)
    return frames
```

- [ ] **Step 2: Verify round-trip**

```bash
uv run python -c "
from PIL import Image
from pixel_magic.animate import build_canvas, extract_frames

# Create a test reference frame
ref = Image.new('RGBA', (200, 250), (255, 0, 0, 255))  # red square
canvas, cols = build_canvas(ref, 6, 'green')
print(f'Canvas: {canvas.size}, cols={cols}')

# Extract back
frames = extract_frames(canvas, 6, cols=cols)
print(f'Extracted {len(frames)} frames, each {frames[0].size}')

# Slot 1 should be red (reference)
px = frames[0].getpixel((100, 125))
print(f'Frame 1 center pixel: {px} (expect red)')

# Slot 2 should be green (empty)
px2 = frames[1].getpixel((100, 125))
print(f'Frame 2 center pixel: {px2} (expect green)')

canvas.save('/tmp/test_grid_canvas.png')
print('Saved /tmp/test_grid_canvas.png')
"
```

- [ ] **Step 3: Commit**

```bash
git add src/pixel_magic/animate.py
git commit -m "feat: extract_frames supports grid layout extraction"
```

---

### Task 5: Auto char_scale in `composite_on_platform()`

**Files:**
- Modify: `src/pixel_magic/platform.py`

Scale character down more for larger tile grids so slot width stays bounded.

- [ ] **Step 1: Add grid scale factors and auto-adjust char_scale**

At the top of `composite_on_platform()`, after the docstring, add the auto-scaling logic. Replace this section:

```python
    char_w, char_h = character.size

    # Scale character down to make room
    new_w = int(char_w * char_scale)
    new_h = int(char_h * char_scale)
```

With:

```python
    char_w, char_h = character.size

    # Auto-scale character based on tile grid — larger grids → smaller character
    # so slot width stays bounded while giving more floor space
    grid_size = {1: 1, 4: 2, 9: 3}.get(tiles, 1)
    _grid_scale = {1: 1.0, 2: 0.68, 3: 0.50}
    char_scale = char_scale * _grid_scale.get(grid_size, 1.0)

    # Scale character down to make room
    new_w = int(char_w * char_scale)
    new_h = int(char_h * char_scale)
```

Note: move the `grid_size` computation up (it's currently further down in the function). Remove the duplicate line:

```python
    grid_size = {1: 1, 4: 2, 9: 3}.get(tiles, 1)
```

that currently appears on line 121 — it's now at the top of the function.

Scale factors:
- grid 1: `0.8 × 1.0 = 0.80` → 205px for 256px base
- grid 2: `0.8 × 0.68 = 0.54` → 139px for 256px base
- grid 3: `0.8 × 0.50 = 0.40` → 102px for 256px base

- [ ] **Step 2: Verify slot dimensions**

```bash
uv run python -c "
from PIL import Image
from pixel_magic.platform import composite_on_platform

ref = Image.new('RGBA', (256, 256), (255, 0, 0, 255))
for t in [1, 4, 9]:
    comp, plat, crop = composite_on_platform(ref, tiles=t)
    print(f'tiles={t}: slot={comp.size}, platform={plat.size}')
"
```

Verify slot widths stay in a reasonable range (~230-360px) and don't balloon.

- [ ] **Step 3: Commit**

```bash
git add src/pixel_magic/platform.py
git commit -m "feat: auto-scale character based on tile grid size"
```

---

### Task 6: Update prompts for grid layout + number removal

**Files:**
- Modify: `src/pixel_magic/prompts.py`

Two changes: (1) `build_canvas_prompt()` describes the grid layout and numbered slots, (2) `build_platform_removal_prompt()` also removes frame numbers.

- [ ] **Step 1: Add `grid_cols` and `grid_rows` params to `build_canvas_prompt()`**

Change the signature from:

```python
def build_canvas_prompt(
    animation_type: str,
    total_frames: int,
    character_description: str = "",
    style: str = "16-bit SNES RPG style",
    chromakey_color: str = "green",
    platform: bool = False,
    loop: bool = False,
    tiles: int = 1,
) -> str:
```

to:

```python
def build_canvas_prompt(
    animation_type: str,
    total_frames: int,
    character_description: str = "",
    style: str = "16-bit SNES RPG style",
    chromakey_color: str = "green",
    platform: bool = False,
    loop: bool = False,
    tiles: int = 1,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
```

- [ ] **Step 2: Update the canvas description to reference the grid**

Replace the opening layout description. In the platform branch, change:

```python
This image is a sprite sheet with {total_frames} frame slots in a horizontal row, on a {chromakey_color} ({hex_color}) background. {slot_desc}
```

to:

```python
This image is a sprite sheet with {total_frames} numbered frame slots arranged in a {grid_cols}×{grid_rows} grid (read left-to-right, top-to-bottom), on a {chromakey_color} ({hex_color}) background. {slot_desc}
```

And in the non-platform branch, do the same replacement:

```python
This image is a sprite sheet with {total_frames} frame slots in a horizontal row.
```

becomes:

```python
This image is a sprite sheet with {total_frames} numbered frame slots arranged in a {grid_cols}×{grid_rows} grid (read left-to-right, top-to-bottom).
```

Also add a rule in both branches about the frame numbers:

```
- Each empty slot has a small white number in the top-left corner showing its frame position — use these numbers to maintain correct animation sequence order
```

- [ ] **Step 3: Pass grid dimensions from `generate_animation()` to `build_canvas_prompt()`**

In `animate.py`, update the prompt call:

```python
prompt = build_canvas_prompt(
    animation_type=animation_type,
    total_frames=total_frames,
    character_description=character_description,
    style=style,
    chromakey_color=chromakey_color,
    platform=platform,
    loop=loop,
    tiles=tiles,
    grid_cols=grid_cols,
    grid_rows=math.ceil(total_frames / grid_cols),
)
```

- [ ] **Step 4: Update `build_platform_removal_prompt()` to also remove frame numbers**

Change the current function to also mention frame numbers. Replace:

```python
def build_platform_removal_prompt(
    total_frames: int,
    chromakey_color: str = "green",
) -> str:
    """Prompt for a second Gemini pass that removes platforms from the sheet."""
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    return f"""\
This is a pixel art sprite sheet with {total_frames} character frames on stone platforms.

Remove the stone platforms from EVERY frame. Replace all platform pixels with {chromakey_color} ({hex_color}) background.

RULES:
- Keep the characters EXACTLY as they are — same proportions, colors, poses, pixel art style
- Do NOT modify any character pixels — only remove the stone platform
- Fill where the platform was with solid {chromakey_color} ({hex_color})
- The output must be the same dimensions as the input
- Maintain the same frame layout (horizontal row of {total_frames} frames)"""
```

With:

```python
def build_platform_removal_prompt(
    total_frames: int,
    chromakey_color: str = "green",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for a second Gemini pass that removes platforms and frame numbers."""
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}×{grid_rows} grid"
    else:
        layout_desc = f"in a horizontal row"
    return f"""\
This is a pixel art sprite sheet with {total_frames} character frames {layout_desc} on stone platforms. Some frames have small white numbers in the corner.

Remove the stone platforms AND the frame numbers from EVERY frame. Replace all platform and number pixels with {chromakey_color} ({hex_color}) background.

RULES:
- Keep the characters EXACTLY as they are — same proportions, colors, poses, pixel art style
- Do NOT modify any character pixels — only remove the stone platforms and corner numbers
- Fill where the platforms and numbers were with solid {chromakey_color} ({hex_color})
- The output must be the same dimensions as the input
- Maintain the same {layout_desc} frame layout"""
```

- [ ] **Step 5: Pass grid dims to removal prompt in `generate_animation()`**

In `animate.py`, update the removal prompt call:

```python
removal_prompt = build_platform_removal_prompt(
    total_frames, chromakey_color,
    grid_cols=grid_cols,
    grid_rows=math.ceil(total_frames / grid_cols),
)
```

- [ ] **Step 6: Commit**

```bash
git add src/pixel_magic/prompts.py src/pixel_magic/animate.py
git commit -m "feat: prompts describe grid layout and frame numbers"
```

---

### Task 7: Visual verification of full pipeline

**Files:** none (testing only)

- [ ] **Step 1: Test canvas generation with platform + numbers**

```bash
uv run python -c "
from PIL import Image
from pixel_magic.platform import composite_on_platform
from pixel_magic.animate import build_canvas

ref = Image.open('output/samurai/views/front_right.png').convert('RGBA')
for t in [1, 4, 9]:
    comp, plat, crop = composite_on_platform(ref, tiles=t)
    canvas, cols = build_canvas(comp, 6, 'green', slot_bg=plat, loop=True)
    canvas.save(f'/tmp/grid_canvas_tiles_{t}.png')
    print(f'tiles={t}: slot={comp.size}, canvas={canvas.size}, cols={cols}')
"
```

Open the 3 images and verify:
- Grid layout (not horizontal strip)
- Frame numbers visible on empty slots (white digits, black outline, top-left corner)
- Numbers hidden under reference frames (slot 1 and slot 6 for loop)
- Platform tiles present in all slots
- Character properly centered and scaled down for larger tile counts

- [ ] **Step 2: Test frame extraction round-trip**

```bash
uv run python -c "
from PIL import Image
from pixel_magic.platform import composite_on_platform
from pixel_magic.animate import build_canvas, extract_frames, assemble_sprite_sheet

ref = Image.open('output/samurai/views/front_right.png').convert('RGBA')
comp, plat, crop = composite_on_platform(ref, tiles=4)
canvas, cols = build_canvas(comp, 6, 'green', slot_bg=plat, loop=True)

# Simulate: extract from canvas (as if Gemini returned it)
frames = extract_frames(canvas, 6, cols=cols)
print(f'Extracted {len(frames)} frames, each {frames[0].size}')

# Assemble back to horizontal sheet
sheet = assemble_sprite_sheet(frames)
sheet.save('/tmp/grid_roundtrip_sheet.png')
print(f'Sheet: {sheet.size}')
"
```

Verify: 6 frames extracted correctly, sheet is horizontal strip.

- [ ] **Step 3: Test non-platform mode**

```bash
uv run python -c "
from PIL import Image
from pixel_magic.animate import build_canvas

ref = Image.new('RGBA', (200, 250), (255, 0, 0, 255))
canvas, cols = build_canvas(ref, 6, 'green')
canvas.save('/tmp/grid_no_platform.png')
print(f'No-platform canvas: {canvas.size}, cols={cols}')
"
```

Verify: grid layout works without platforms too, numbers visible on green slots.

---

## Non-platform mode note

The grid layout and frame numbers apply to ALL animations, not just platform mode. This improves Gemini's understanding of frame order regardless of whether a platform is used. The only difference is: without platform, numbers appear directly on chromakey background. With platform, numbers appear over the platform tile.
