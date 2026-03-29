# Multi-Tile Platform Grid Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the platform grid configurable (1, 4, or 9 tiles) so animation slots can be wider for attack/cast animations where the character needs room to swing.

**Architecture:** Replace the single `create_platform()` tile with a `create_platform_grid(tiles)` that arranges 1x1, 2x2, or 3x3 isometric tiles into a diamond floor. The character is centered on the grid. Larger grids = wider slots = more room for dramatic poses. Canvas and prompt are updated to reflect the grid size.

**Tech Stack:** Pillow (ImageDraw polygons), existing Gemini pipeline.

---

## Current State

- `create_platform(width, depth)` draws one isometric diamond tile
- `composite_on_platform(character)` scales char to 80%, places on single tile
- Canvas slots are character-width (~345px for samurai)
- Gemini preserves input dimensions (~1:1 ratio between input/output)
- Current 6-frame canvas: ~2070x498 — Gemini handles this fine

## Key Constraints

- **Gemini output size:** Gemini roughly preserves input dimensions. A 2070x498 canvas returns ~2062x496. Very wide canvases (5000+px) are untested and may degrade.
- **Frame count tradeoff:** More tiles = wider slots = wider canvas. With 9 tiles and 6 frames the canvas hits ~5700px wide. We should recommend fewer frames (4) for large grids, or accept wider output.
- **Isometric tile layout:** In a 2x2 isometric grid, tiles interlock in a diamond pattern (not a square grid). Each row is offset by half a tile width.

## Design Decisions

### Tile grid layout (isometric diamond arrangement)

```
1 tile (1x1):       4 tiles (2x2):         9 tiles (3x3):
                         ◇                      ◇
    ◇                  ◇   ◇                  ◇   ◇
                         ◇                    ◇   ◇   ◇
                                               ◇   ◇
                                                 ◇
```

A `grid_size` of N means an NxN isometric diamond. The tiles are arranged in standard isometric layout — each row offset by half a tile. The total footprint:
- 1x1: 1 tile wide, 1 tile tall
- 2x2: 2 tiles wide, 2 tiles tall (diamond shape)
- 3x3: 3 tiles wide, 3 tiles tall (larger diamond)

### Slot sizing

The slot width/height must accommodate the full tile grid + the scaled character. The character is centered on the grid. For attack animations, the extra grid area gives the character room to extend limbs/weapons into neighboring tile space.

### CLI interface

`--tiles 1|4|9` (default: 1 for walk/idle, could auto-pick based on animation type later).

No auto-picking in this plan — keep it explicit. User chooses.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/pixel_magic/platform.py` | Modify | Add `create_platform_grid()`, update `composite_on_platform()` to accept `tiles` param |
| `src/pixel_magic/animate.py` | Modify | Pass `tiles` through to `composite_on_platform()` |
| `src/pixel_magic/prompts.py` | Modify | Describe the tile grid in platform prompts |
| `src/pixel_magic/__main__.py` | Modify | Add `--tiles` CLI arg |

---

### Task 1: `create_platform_grid()` in platform.py

**Files:**
- Modify: `src/pixel_magic/platform.py`

The core function. Takes the existing single-tile `create_platform()` and arranges N tiles in an isometric diamond pattern.

- [ ] **Step 1: Add `create_platform_grid()` function**

```python
def create_platform_grid(
    tile_width: int,
    tile_depth: int = 8,
    grid_size: int = 1,
) -> Image.Image:
    """Arrange tiles in an isometric diamond grid.

    grid_size=1: single tile (same as create_platform)
    grid_size=2: 2x2 diamond (4 tiles)
    grid_size=3: 3x3 diamond (9 tiles)

    Returns RGBA image with transparent background.
    """
    if grid_size == 1:
        return create_platform(tile_width, tile_depth)

    tile = create_platform(tile_width, tile_depth)
    tw, th = tile.size
    diamond_h = tile_width // 2

    # Isometric grid: each tile offset by (tw/2, diamond_h/2)
    # Grid spans grid_size columns and grid_size rows
    # Total width: grid_size * tw
    # Total height: grid_size * diamond_h + tile_depth
    grid_w = grid_size * tw
    grid_h = grid_size * diamond_h + tile_depth

    grid_img = Image.new("RGBA", (grid_w, grid_h), (0, 0, 0, 0))

    # Place tiles in isometric order (back to front for correct overlap)
    for row in range(grid_size):
        for col in range(grid_size):
            # Isometric position: each step right = (+tw/2, +diamond_h/2)
            #                     each step down  = (-tw/2, +diamond_h/2)
            x = (col - row) * (tw // 2) + (grid_size - 1) * (tw // 2)
            y = (col + row) * (diamond_h // 2)
            grid_img.paste(tile, (x, y), tile)

    return grid_img
```

The isometric placement formula:
- Moving "right" in grid space = move right and down on screen
- Moving "down" in grid space = move left and down on screen
- Base offset centers the grid horizontally

- [ ] **Step 2: Test visually**

```bash
uv run python -c "
from pixel_magic.platform import create_platform_grid
for n in [1, 2, 3]:
    g = create_platform_grid(160, 16, grid_size=n)
    g.save(f'/tmp/grid_{n}x{n}.png')
    print(f'{n}x{n}: {g.size}')
"
```

Verify the grids look like proper isometric diamond arrangements.

- [ ] **Step 3: Commit**

```bash
git add src/pixel_magic/platform.py
git commit -m "feat: add create_platform_grid() for multi-tile isometric floors"
```

---

### Task 2: Update `composite_on_platform()` to use grid

**Files:**
- Modify: `src/pixel_magic/platform.py`

- [ ] **Step 1: Add `tiles` parameter to `composite_on_platform()`**

Change signature:
```python
def composite_on_platform(
    character: Image.Image,
    char_scale: float = 0.8,
    platform_ratio: float = 1.15,
    platform_depth: int = 32,
    tiles: int = 1,
) -> tuple[Image.Image, Image.Image, int]:
```

Replace `create_platform(plat_w, platform_depth)` call with:
```python
grid_size = {1: 1, 4: 2, 9: 3}[tiles]
platform = create_platform_grid(plat_w, platform_depth, grid_size=grid_size)
```

Update `comp_w` to accommodate wider grid:
```python
comp_w = max(char_w, platform.width)
```

The `diamond_h` calculation for overlap needs to use the SINGLE tile's diamond_h (not the full grid), since the character stands on the center tile:
```python
single_diamond_h = plat_w // 2
overlap = int(single_diamond_h * 0.7)
```

- [ ] **Step 2: Test with samurai reference**

```bash
uv run python -c "
from pixel_magic.platform import composite_on_platform
from pixel_magic.animate import build_canvas
from PIL import Image
ref = Image.open('output/samurai/views/front_right.png').convert('RGBA')
for t in [1, 4, 9]:
    comp, plat, crop = composite_on_platform(ref, tiles=t)
    canvas = build_canvas(comp, 4, 'green', slot_bg=plat, loop=True)
    canvas.save(f'output/test_tiles_{t}.png')
    print(f'tiles={t}: slot={comp.size}, canvas={canvas.size}')
"
```

Check that:
- tiles=1 looks like current behavior
- tiles=4 has wider slots with 2x2 diamond floor
- tiles=9 has even wider slots with 3x3 diamond floor
- Character is centered on the grid in all cases

- [ ] **Step 3: Commit**

```bash
git add src/pixel_magic/platform.py
git commit -m "feat: composite_on_platform supports tiles param (1/4/9)"
```

---

### Task 3: Pass `tiles` through animate.py

**Files:**
- Modify: `src/pixel_magic/animate.py`

- [ ] **Step 1: Add `tiles` param to `generate_animation()`**

Add `tiles: int = 1` to the function signature.

Pass it through to `composite_on_platform`:
```python
ref_composite, slot_bg, crop_h = composite_on_platform(reference_frame, tiles=tiles)
```

- [ ] **Step 2: Commit**

```bash
git add src/pixel_magic/animate.py
git commit -m "feat: generate_animation passes tiles to platform compositor"
```

---

### Task 4: Update prompts for multi-tile context

**Files:**
- Modify: `src/pixel_magic/prompts.py`

- [ ] **Step 1: Add `tiles` param to `build_canvas_prompt()`**

Add `tiles: int = 1` to signature.

In the platform branch, adjust the slot description based on tile count:
```python
if tiles == 1:
    floor_desc = "an isometric stone platform"
elif tiles == 4:
    floor_desc = "a 2x2 isometric stone tile floor (4 tiles in a diamond)"
else:
    floor_desc = "a 3x3 isometric stone tile floor (9 tiles in a diamond)"
```

Use `floor_desc` in place of "an isometric stone platform" in the prompt text. Also add a rule for multi-tile:
```python
if tiles > 1:
    space_rule = "- The character has extra floor space — use it for the full range of motion (extended limbs, weapon swings, lunges)"
else:
    space_rule = ""
```

- [ ] **Step 2: Pass `tiles` from `generate_animation()` to `build_canvas_prompt()`**

In `animate.py`, update the prompt call:
```python
prompt = build_canvas_prompt(
    ...,
    tiles=tiles,
)
```

- [ ] **Step 3: Commit**

```bash
git add src/pixel_magic/prompts.py src/pixel_magic/animate.py
git commit -m "feat: prompts describe tile grid size for multi-tile floors"
```

---

### Task 5: Add `--tiles` CLI argument

**Files:**
- Modify: `src/pixel_magic/__main__.py`

- [ ] **Step 1: Add argument to animate subparser**

After the `--platform` arguments:
```python
anim.add_argument(
    "--tiles", type=int, default=1, choices=[1, 4, 9],
    help="Platform tile count: 1 (default), 4 (2x2 grid), 9 (3x3 grid). More tiles = more room for action poses.",
)
```

- [ ] **Step 2: Pass to `generate_animation()`**

In `_animate()`:
```python
anim_frames = await generate_animation(
    ...,
    platform=args.platform,
    tiles=args.tiles,
)
```

Note: `--tiles` implies `--platform`. If tiles > 1 and platform is False, auto-enable platform:
```python
if args.tiles > 1:
    args.platform = True
```

Add this right before the `generate_animation` call in `_animate()`.

- [ ] **Step 3: Test the full pipeline**

```bash
# Walk with 1 tile (current behavior)
uv run pixel-magic animate --name samurai --animation walk --frames 6 --platform --tiles 1

# Attack with 4 tiles (more room)
uv run pixel-magic animate --name samurai --animation attack --frames 6 --platform --tiles 4 --no-loop

# Attack with 9 tiles (maximum room)
uv run pixel-magic animate --name samurai --animation attack --frames 4 --platform --tiles 9 --no-loop
```

- [ ] **Step 4: Commit**

```bash
git add src/pixel_magic/__main__.py
git commit -m "feat: --tiles CLI arg for multi-tile platform grids"
```

---

## Output Size Notes

Canvas widths for reference (samurai, 345px base):

| Tiles | Frames | Canvas width | Status |
|-------|--------|-------------|--------|
| 1     | 6      | ~2070px     | Tested, works |
| 4     | 6      | ~3800px     | Should work |
| 4     | 4      | ~2500px     | Safe |
| 9     | 6      | ~5700px     | May be too wide — recommend 4 frames |
| 9     | 4      | ~3800px     | Should work |

If 9-tile + 6-frame proves too wide for Gemini, we can add a warning or auto-cap frames. Not in this plan — handle if it becomes an issue.
