# Platform-Based Character Generation + OpenAI Retirement Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use the grid canvas + platform system for character sprite generation (not just animation), and retire the OpenAI provider since Gemini is now the sole backend for both generation and animation.

**Architecture:** Build a platform template canvas (grid of empty platforms), send it to Gemini with a character description prompt, get back characters-on-platforms, remove platforms, extract individual views. Same grid/ratio/padding system as animation. Retire OpenAI: remove provider, simplify config, drop `--provider` flag.

**Tech Stack:** Pillow, Google Gemini (multimodal), existing platform/canvas/extraction pipeline.

---

## Current State

- `_generate()` sends a text-only JSON prompt → model generates a horizontal strip of character views on chromakey background
- OpenAI and Gemini both supported via `--provider`
- Gemini output gets chromakey removal (rembg + despill), OpenAI has native transparency
- `extract_sprites()` uses connected-component analysis to find individual views
- Animation already uses grid canvas + platforms + Gemini multimodal + frame numbers

## Key Changes

1. **Generation uses platform canvas** — build a grid of empty platforms, send as image + prompt to Gemini
2. **Grid layout for views** — 4-dir: 2 views (2×1 or 1×2), 8-dir: 5 views (3 top, 2 centered bottom)
3. **`--tiles` on generate** — character footprint (1×1, 2×2, 3×3)
4. **View labels on platforms** — pixel-art text showing facing direction (like frame numbers for animation)
5. **Retire OpenAI** — remove provider, config fields, CLI flag
6. **Platform removal pass** — second Gemini call strips platforms after generation

## Grid Layout for Views

```
4-dir (2 views):        8-dir (5 views):
                         [back] [back_right] [right]
[front_left] [back_right]    [front_right] [front]
                         (bottom row centered)
```

For 8-dir, bottom row of 2 is centered horizontally — each offset by half a cell width from the edges.

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/pixel_magic/__main__.py` | Modify | Add `--tiles` to generate, remove `--provider`/OpenAI, rewrite `_generate()` to use canvas pipeline |
| `src/pixel_magic/prompts.py` | Modify | Add `build_generation_canvas_prompt()`, add `build_generation_cleanup_prompt()` |
| `src/pixel_magic/animate.py` | Modify | Extract shared canvas utilities (grid layout, frame numbers, snap ratio) — or reuse directly |
| `src/pixel_magic/platform.py` | No change | Already has `composite_on_platform()` and `create_platform_grid()` |
| `src/pixel_magic/config.py` | Modify | Remove OpenAI settings, change default provider to "gemini" |
| `src/pixel_magic/providers/openai.py` | Delete | No longer needed |
| `src/pixel_magic/providers/base.py` | No change | Keep `GenerationConfig`/`GenerationResult` |

---

### Task 1: Retire OpenAI provider

**Files:**
- Delete: `src/pixel_magic/providers/openai.py`
- Modify: `src/pixel_magic/config.py`
- Modify: `src/pixel_magic/__main__.py`

- [ ] **Step 1: Remove OpenAI from config.py**

In `config.py`, remove these fields from `Settings`:
```python
    # Remove these lines:
    provider: Literal["openai", "gemini"] = "openai"
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = "gpt-image-1.5"
    openai_quality: Literal["low", "medium", "high"] = "medium"
```

The remaining config should be:
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PIXEL_MAGIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")

    # Gemini
    gemini_image_model: str = "gemini-3.1-flash-image-preview"

    # Generation defaults
    direction_mode: int = 4
    image_size: str = "1024x1024"
    default_resolution: str = "64x64"
    max_colors: int = 16
    chromakey_color: Literal["green", "blue"] = "green"

    # Output
    output_dir: Path = Path("output")
```

- [ ] **Step 2: Remove `--provider` from CLI**

In `__main__.py`, remove this line from the generate subparser:
```python
    gen.add_argument("--provider", choices=["openai", "gemini"], help="Override provider (default: from .env)")
```

- [ ] **Step 3: Simplify `_generate()` to Gemini-only**

In `_generate()`, remove the provider switching. Replace:
```python
    provider_name = args.provider or settings.provider
    ...
    if provider_name == "openai":
        from pixel_magic.providers.openai import OpenAIProvider
        provider = OpenAIProvider(...)
    else:
        from pixel_magic.providers.gemini import GeminiProvider
        provider = GeminiProvider(...)
```

With:
```python
    from pixel_magic.providers.gemini import GeminiProvider
    provider = GeminiProvider(
        api_key=settings.google_api_key,
        model=settings.gemini_image_model,
    )
```

Also remove the `if provider_name == "gemini"` conditional around background removal — it always runs now. And remove `provider=provider_name` from the `build_character_sheet_prompt()` call (provider param no longer needed).

- [ ] **Step 4: Delete `src/pixel_magic/providers/openai.py`**

```bash
rm src/pixel_magic/providers/openai.py
```

- [ ] **Step 5: Clean up prompts.py**

Remove the `provider` parameter from `build_character_sheet_prompt()` and the provider-conditional background logic. Background is always chromakey now. Remove `_background_instruction()` and `_background_rule()` OpenAI branches — they always return the Gemini variant.

- [ ] **Step 6: Verify**

```bash
uv run python -c "from pixel_magic.__main__ import main; print('ok')"
uv run pixel-magic generate --help  # should NOT show --provider
```

- [ ] **Step 7: Commit**

```bash
git rm src/pixel_magic/providers/openai.py
git add src/pixel_magic/config.py src/pixel_magic/__main__.py src/pixel_magic/prompts.py
git commit -m "refactor: retire OpenAI provider, Gemini-only pipeline"
```

---

### Task 2: Add `build_generation_canvas_prompt()` to prompts.py

**Files:**
- Modify: `src/pixel_magic/prompts.py`

The prompt for canvas-based generation. Tells Gemini: "This image has N platforms in a grid. Draw the same character on each platform, facing the labeled direction."

- [ ] **Step 1: Add view label constants**

Add after the existing `_VIEWS_8DIR`:

```python
_VIEW_LABELS_4DIR: list[str] = ["front_left", "back_right"]
_VIEW_LABELS_8DIR: list[str] = ["back", "back_right", "right", "front_right", "front"]
```

- [ ] **Step 2: Add `build_generation_canvas_prompt()`**

```python
def build_generation_canvas_prompt(
    character_description: str,
    direction_mode: int = 4,
    style: str = "16-bit SNES RPG style",
    max_colors: int = 16,
    chromakey_color: str = "green",
    tiles: int = 1,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Build a prompt for canvas-based character generation.

    The caller creates a canvas with labeled platforms in a grid.
    The model draws the same character on each platform facing the labeled direction.
    """
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    views = _VIEWS_4DIR if direction_mode == 4 else _VIEWS_8DIR

    if tiles == 1:
        floor_desc = "an isometric stone platform"
    elif tiles == 4:
        floor_desc = "a 2x2 isometric stone tile floor"
    else:
        floor_desc = "a 3x3 isometric stone tile floor"

    view_list = "\n".join(
        f"  - Platform labeled \"{v['facing'].split('(')[0].strip()}\": "
        f"draw the character {v['description'].lower()}"
        for v in views
    )

    layout_desc = ""
    if grid_cols and grid_rows:
        layout_desc = f" arranged in a {grid_cols}x{grid_rows} grid"

    return f"""\
This image shows {len(views)} labeled platforms{layout_desc} on a {chromakey_color} ({hex_color}) background. Each platform has a direction label in the corner.

Draw the SAME pixel art character on every platform, facing the labeled direction:
{view_list}

The character is: {character_description}

RULES:
- The character must be IDENTICAL across all platforms — same proportions, colors, outfit, pixel art style
- Only the facing direction changes between platforms
- The character's feet must rest on the platform surface
- Maintain the isometric 3/4 top-down perspective — the platform establishes the ground plane
- Style: {style}
- Pixel art: hard pixel edges, no anti-aliasing, no smoothing
- 1-pixel black outline on all character elements
- Maximum {max_colors} colors in the character palette
- Simple 2-3 tone stepped shading per color area
- {chromakey_color} ({hex_color}) background must remain around the character and platform
- Do NOT modify the platforms or labels — draw the character standing ON TOP of them"""
```

- [ ] **Step 3: Add `build_generation_cleanup_prompt()`**

```python
def build_generation_cleanup_prompt(
    view_count: int,
    chromakey_color: str = "green",
    grid_cols: int | None = None,
    grid_rows: int | None = None,
) -> str:
    """Prompt for removing platforms and labels from generated character sheet."""
    hex_color = _CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    if grid_cols and grid_rows:
        layout_desc = f"arranged in a {grid_cols}x{grid_rows} grid"
    else:
        layout_desc = "in a row"
    return f"""\
This is a pixel art character sheet with {view_count} character views {layout_desc} on stone platforms. Each platform has a direction label in the corner.

Remove the stone platforms AND the direction labels from EVERY view. Replace all platform and label pixels with {chromakey_color} ({hex_color}) background.

RULES:
- Keep the characters EXACTLY as they are — same proportions, colors, poses, pixel art style
- Do NOT modify any character pixels — only remove the stone platforms and corner labels
- Fill where the platforms and labels were with solid {chromakey_color} ({hex_color})
- The output must be the same dimensions as the input
- Maintain the same {layout_desc} layout"""
```

- [ ] **Step 4: Verify**

```bash
uv run python -c "
from pixel_magic.prompts import build_generation_canvas_prompt, build_generation_cleanup_prompt
p = build_generation_canvas_prompt('a samurai with a katana', direction_mode=4, tiles=4, grid_cols=2, grid_rows=1)
assert 'front' in p.lower()
assert 'back' in p.lower()
assert '2x2' in p
print('canvas prompt ok')
c = build_generation_cleanup_prompt(2, grid_cols=2, grid_rows=1)
assert 'direction labels' in c.lower()
print('cleanup prompt ok')
"
```

- [ ] **Step 5: Commit**

```bash
git add src/pixel_magic/prompts.py
git commit -m "feat: add generation canvas prompt with platform + direction labels"
```

---

### Task 3: Build generation canvas with labeled platforms

**Files:**
- Modify: `src/pixel_magic/animate.py`

Reuse the existing canvas infrastructure but with direction labels instead of frame numbers, and a centered-bottom-row layout for 5 views.

- [ ] **Step 1: Add `_draw_label()` function**

Similar to `_draw_frame_number()` but renders a short text string. Reuse the `_DIGIT_BITMAPS` for any digits in the label, and add uppercase letter bitmaps (3×5) for common direction labels.

Actually, simpler approach: the direction labels can just be short abbreviations drawn as pixel text. We need these letters at minimum: B, A, C, K, R, I, G, H, T, F, O, N, L, E (for "BACK", "RIGHT", "FRONT", "LEFT").

Add a `_LETTER_BITMAPS` dict with 3×5 bitmaps for uppercase letters A-Z (or just the needed ones). Then a `_draw_label()` function that renders a string character by character.

```python
_LETTER_BITMAPS: dict[str, list[int]] = {
    "A": [0b010, 0b101, 0b111, 0b101, 0b101],
    "B": [0b110, 0b101, 0b110, 0b101, 0b110],
    "C": [0b011, 0b100, 0b100, 0b100, 0b011],
    "E": [0b111, 0b100, 0b110, 0b100, 0b111],
    "F": [0b111, 0b100, 0b110, 0b100, 0b100],
    "G": [0b011, 0b100, 0b101, 0b101, 0b011],
    "H": [0b101, 0b101, 0b111, 0b101, 0b101],
    "I": [0b111, 0b010, 0b010, 0b010, 0b111],
    "K": [0b101, 0b110, 0b100, 0b110, 0b101],
    "L": [0b100, 0b100, 0b100, 0b100, 0b111],
    "N": [0b101, 0b111, 0b111, 0b101, 0b101],
    "O": [0b010, 0b101, 0b101, 0b101, 0b010],
    "R": [0b110, 0b101, 0b110, 0b101, 0b101],
    "T": [0b111, 0b010, 0b010, 0b010, 0b010],
    " ": [0b000, 0b000, 0b000, 0b000, 0b000],
}
```

Then generalize the existing `_draw_frame_number` into a `_draw_pixel_text(canvas, text, x, y, slot_width)` function that handles both numbers and letters. The existing `_draw_frame_number` becomes a thin wrapper: `_draw_pixel_text(canvas, str(number), ...)`.

- [ ] **Step 2: Add `_generation_grid_layout()` for view grids**

For generation, the layout is different from animation:
- 2 views: 2×1 (side by side)
- 5 views: 3×2 with bottom row centered

```python
def _generation_grid_layout(
    n_views: int,
) -> tuple[int, int, bool]:
    """Grid layout for character generation views.

    Returns (cols, rows, center_bottom).
    center_bottom=True means the last row has fewer items and should be centered.
    """
    if n_views <= 3:
        return n_views, 1, False
    if n_views <= 4:
        return 2, 2, False
    if n_views <= 6:
        top_cols = (n_views + 1) // 2
        return top_cols, 2, n_views % top_cols != 0
    # Fallback
    cols = math.ceil(math.sqrt(n_views))
    rows = math.ceil(n_views / cols)
    return cols, rows, n_views % cols != 0
```

For 2 views: (2, 1, False) — 2 side by side
For 5 views: (3, 2, True) — 3 top, 2 bottom centered

- [ ] **Step 3: Add `build_generation_canvas()`**

```python
def build_generation_canvas(
    view_labels: list[str],
    tile_width: int = 160,
    tile_depth: int = 16,
    tiles: int = 1,
    chromakey_color: str = "green",
) -> tuple[Image.Image, int, tuple[int, int], str, str, bool]:
    """Build a canvas with labeled platforms for character generation.

    Each platform gets a direction label in the top-left corner.
    For 5 views, the bottom row of 2 is centered.

    Returns (canvas, cols, slot_size, aspect_ratio, image_size, center_bottom).
    """
    from pixel_magic.platform import composite_on_platform, create_platform_grid

    chromakey_rgb = {"green": (0, 255, 0), "blue": (0, 0, 255)}
    fill = chromakey_rgb.get(chromakey_color, (0, 255, 0))

    n_views = len(view_labels)
    cols, rows, center_bottom = _generation_grid_layout(n_views)

    # Create a dummy character-sized reference to get platform composite dimensions
    # Use tile_width as the base for sizing
    grid_size = {1: 1, 4: 2, 9: 3}.get(tiles, 1)
    platform = create_platform_grid(tile_width, tile_depth, grid_size=grid_size)

    # Slot = platform with headroom above for the character
    slot_w = platform.width + 20  # small margin
    slot_h = int(platform.height * 2.5)  # room for character above platform

    # Platform positioning within slot
    plat_x = (slot_w - platform.width) // 2
    plat_y = slot_h - platform.height - 10  # near bottom of slot

    # Snap to Gemini ratio
    raw_w = cols * slot_w
    raw_h = rows * slot_h
    aspect_ratio, canvas_w, canvas_h = _snap_gemini_ratio(raw_w, raw_h)
    image_size = _pick_image_size(max(canvas_w, canvas_h))

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*fill, 255))

    cell_w = canvas_w // cols
    cell_h = canvas_h // rows

    for idx in range(n_views):
        row = idx // cols if not center_bottom or idx < cols else 1
        col = idx % cols if not center_bottom or idx < cols else idx - cols

        cell_x = col * cell_w
        cell_y = row * cell_h

        # Center bottom row if needed
        if center_bottom and row == 1:
            bottom_count = n_views - cols
            total_bottom_w = bottom_count * cell_w
            offset = (canvas_w - total_bottom_w) // 2
            cell_x = offset + (idx - cols) * cell_w

        # Center slot within cell
        ox = cell_x + (cell_w - slot_w) // 2
        oy = cell_y + (cell_h - slot_h) // 2

        # Paste platform
        canvas.paste(platform, (ox + plat_x, oy + plat_y), platform)

        # Draw direction label
        label = view_labels[idx].upper().replace("_", " ")
        _draw_pixel_text(canvas, label, cell_x, cell_y, cell_w)

    return canvas, cols, (slot_w, slot_h), aspect_ratio, image_size, center_bottom
```

- [ ] **Step 4: Verify visually**

```bash
uv run python -c "
from pixel_magic.animate import build_generation_canvas
canvas, cols, slot_size, ratio, img_size, centered = build_generation_canvas(
    ['front_left', 'back_right'], tile_width=160, tiles=1,
)
canvas.save('/tmp/gen_canvas_4dir.png')
print(f'4-dir: {canvas.size}, {cols} cols, {ratio} {img_size}')

canvas5, cols5, _, ratio5, _, centered5 = build_generation_canvas(
    ['back', 'back_right', 'right', 'front_right', 'front'], tile_width=160, tiles=4,
)
canvas5.save('/tmp/gen_canvas_8dir.png')
print(f'8-dir: {canvas5.size}, {cols5} cols, {ratio5}, centered={centered5}')
"
```

Open images and verify: platforms visible, labels readable, 8-dir has centered bottom row.

- [ ] **Step 5: Commit**

```bash
git add src/pixel_magic/animate.py
git commit -m "feat: generation canvas with labeled platforms and centered layout"
```

---

### Task 4: Rewrite `_generate()` to use canvas pipeline

**Files:**
- Modify: `src/pixel_magic/__main__.py`

- [ ] **Step 1: Add `--tiles` to generate subparser**

After the `--chromakey` argument:
```python
    gen.add_argument(
        "--tiles", type=int, default=1, choices=[1, 4, 9],
        help="Character tile footprint: 1 (default), 4 (2x2 — larger creature), 9 (3x3 — boss/mount).",
    )
```

- [ ] **Step 2: Rewrite `_generate()` to use canvas pipeline**

Replace the entire `_generate()` function. The new flow:
1. Build generation canvas (platforms + labels)
2. Build generation prompt
3. Send canvas + prompt to Gemini (multimodal)
4. Second pass: remove platforms
5. Background removal (rembg + despill)
6. Extract sprites
7. Optional resize

```python
async def _generate(args: argparse.Namespace) -> None:
    from pixel_magic.animate import build_generation_canvas, extract_frames
    from pixel_magic.config import Settings
    from pixel_magic.prompts import (
        build_generation_canvas_prompt,
        build_generation_cleanup_prompt,
    )
    from pixel_magic.providers.gemini import GeminiProvider

    settings = Settings()
    chromakey_color = args.chromakey or settings.chromakey_color

    provider = GeminiProvider(
        api_key=settings.google_api_key,
        model=settings.gemini_image_model,
    )

    view_labels = _view_labels(args.directions)
    view_count = len(view_labels)

    # Build canvas with labeled platforms
    canvas, grid_cols, slot_size, aspect_ratio, image_size, center_bottom = (
        build_generation_canvas(
            view_labels=view_labels,
            tiles=args.tiles,
            chromakey_color=chromakey_color,
        )
    )
    grid_rows = math.ceil(view_count / grid_cols)

    out_dir = Path(args.output_dir) / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    canvas.save(out_dir / "canvas_input.png")

    print(f"Generating {args.name} ({view_count} views, tiles={args.tiles})...")
    print(f"  Canvas: {canvas.width}x{canvas.height} ({grid_cols}x{grid_rows} grid)")
    print(f"  Gemini: {aspect_ratio} ratio, {image_size} output")

    # Generate: send canvas + prompt
    prompt = build_generation_canvas_prompt(
        character_description=args.description,
        direction_mode=args.directions,
        style=args.style,
        max_colors=args.max_colors,
        chromakey_color=chromakey_color,
        tiles=args.tiles,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
    )

    result = await provider.generate_with_images(
        prompt=prompt,
        images=[canvas],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    result.image.save(out_dir / "raw.png")
    print(f"  Raw: {result.image.width}x{result.image.height}")

    # Second pass: remove platforms + labels
    cleanup_prompt = build_generation_cleanup_prompt(
        view_count, chromakey_color,
        grid_cols=grid_cols,
        grid_rows=grid_rows,
    )
    print("  Removing platforms...")
    cleaned = await provider.generate_with_images(
        prompt=cleanup_prompt,
        images=[result.image],
        aspect_ratio=aspect_ratio,
        image_size=image_size,
    )
    cleaned.image.save(out_dir / "sheet_cleaned.png")

    # Background removal (rembg + despill)
    from pixel_magic.background import remove_background

    sheet = remove_background(cleaned.image, chromakey_color=chromakey_color)
    sheet.save(out_dir / "sheet.png")
    print(f"  Sheet: {sheet.width}x{sheet.height} (background removed)")

    # Extract sprites
    from pixel_magic.extract import extract_sprites

    sprites = extract_sprites(sheet, expected_count=view_count)
    if sprites:
        views_dir = out_dir / "views"
        views_dir.mkdir(exist_ok=True)
        for i, sprite in enumerate(sprites):
            label = view_labels[i] if i < len(view_labels) else f"view_{i}"
            sprite.save(views_dir / f"{label}.png")
            print(f"  {label}: {sprite.width}x{sprite.height}")
        print(f"Extracted {len(sprites)} sprites to {views_dir}")

        # Resize if requested
        if args.sizes:
            from pixel_magic.resize import parse_sizes, resize_sprite

            sizes = parse_sizes(args.sizes)
            for size in sizes:
                size_dir = views_dir / f"{size}x{size}"
                size_dir.mkdir(exist_ok=True)
                for i, sprite in enumerate(sprites):
                    label = view_labels[i] if i < len(view_labels) else f"view_{i}"
                    resized = resize_sprite(sprite, size, num_colors=args.num_colors)
                    resized.save(size_dir / f"{label}.png")
                print(f"  Resized to {size}x{size}")
            print(f"Saved {len(sizes)} size variants")
    else:
        print("Warning: could not extract individual sprites from sheet")
```

Don't forget to add `import math` at the top of `__main__.py`.

- [ ] **Step 3: Verify CLI**

```bash
uv run pixel-magic generate --help
# Should show --tiles, NOT show --provider
```

- [ ] **Step 4: Commit**

```bash
git add src/pixel_magic/__main__.py
git commit -m "feat: generate command uses canvas pipeline with platforms"
```

---

### Task 5: Visual testing of generation canvas

**Files:** none (testing only)

- [ ] **Step 1: Generate canvas templates for all configs**

```bash
uv run python -c "
from pixel_magic.animate import build_generation_canvas
configs = [
    (['front_left', 'back_right'], 1, '4dir_tiles1'),
    (['front_left', 'back_right'], 4, '4dir_tiles4'),
    (['back', 'back_right', 'right', 'front_right', 'front'], 1, '8dir_tiles1'),
    (['back', 'back_right', 'right', 'front_right', 'front'], 4, '8dir_tiles4'),
    (['back', 'back_right', 'right', 'front_right', 'front'], 9, '8dir_tiles9'),
]
for labels, tiles, name in configs:
    canvas, cols, ss, ratio, size, centered = build_generation_canvas(labels, tiles=tiles)
    canvas.save(f'output/gen_test_{name}.png')
    print(f'{name}: {canvas.size} {cols}cols {ratio} {size} centered={centered}')
"
```

Verify all canvases look correct: platforms visible, labels readable, centered bottom row for 8-dir.

- [ ] **Step 2: Test full generation pipeline**

```bash
uv run pixel-magic generate --name test-samurai --description "a samurai warrior with a katana, straw hat, dark robes" --tiles 1

uv run pixel-magic generate --name test-golem --description "a stone golem, massive rocky body, glowing eyes" --tiles 4 --directions 4
```

Check `output/test-samurai/` and `output/test-golem/` for canvas_input.png, raw.png, sheet_cleaned.png, sheet.png, and views/.

- [ ] **Step 3: Commit any fixes**

---

### Task 6: Clean up docs and config

**Files:**
- Modify: `docs/cli.md`
- Modify: `docs/research/sprite-generation.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update cli.md**

Remove `--provider` from generate command docs. Add `--tiles` option. Update environment config section to remove OpenAI variables.

- [ ] **Step 2: Update CLAUDE.md**

Remove OpenAI references. Update the generate command example.

- [ ] **Step 3: Update sprite-generation research**

Add Approach section for platform-based generation. Note the retirement of OpenAI.

- [ ] **Step 4: Commit**

```bash
git add docs/ CLAUDE.md
git commit -m "docs: update for Gemini-only pipeline with platform generation"
```
