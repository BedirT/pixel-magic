# JSON-Structured Multi-View Character Generation

## Problem
Character generation currently makes **2 separate single-direction API calls** (SE + NE), each producing one sprite. This doesn't leverage the models' ability to produce consistent multi-view reference sheets in a single generation — which both GPT Image 1.5 and Gemini handle well when given a JSON-structured prompt.

## Approach: JSON Prompt Builder for Character Sheets

Instead of text-template prompts, characters will use a **JSON-structured prompt** that describes the character, views, palette, and art style in a structured format. One API call produces a **multi-view reference sheet** (all views on a single image).

### Key Design Decisions

1. **JSON prompt as a string** — The JSON is serialized to a string and sent as the prompt text. The existing `PromptTemplate` system stays intact; we add a new template type that builds JSON instead of prose.

2. **Solid gray background** — Multi-view sheets use `#6B6B6B` (or similar neutral gray) instead of transparent + magenta dividers. This matches what works well with image models and makes extraction cleaner.

3. **Single generation call** — For base character (non-extension), ONE call produces 2 views (front-left SE + back-right NE) on a single sheet. For 8-dir, ONE call produces 5 views.

4. **Extraction by connected-component** — Instead of magenta separator detection, we detect character sprites on the gray background by finding opaque/non-gray regions. The existing `auto_detect` path in the extractor already handles this.

---

## Implementation Steps

### Step 1: Add `build_character_json_prompt()` in `characters.py`

Create a function that builds a JSON prompt dict from request parameters:

```python
def build_character_json_prompt(
    character_description: str,
    views: list[dict],  # [{position, facing, description}, ...]
    style: str,
    resolution: str,
    max_colors: int,
    palette_hint: str = "",
    background_color: str = "#6B6B6B",
) -> str:
    """Build a JSON-structured prompt string for multi-view character generation."""
```

The JSON structure follows the pattern from the user's example:
- `image_type`, `style`, `background`
- `views[]` — position + facing + description
- `character` — type, build, description (from request.objective)
- `color_palette` — extracted from palette_hint or left for the model
- `art_details` — pixel density, shading, perspective
- `purpose` — "character_sprite_reference_sheet"

### Step 2: New template `character_multiview_sheet`

Register a new `PromptTemplate` whose `render()` output is the JSON string. The system_context remains a text prompt explaining the task, but the template body is the JSON.

Alternatively, bypass the template system and build the JSON directly in `build_plan_from_request` — simpler and avoids fighting `string.Template` with JSON braces.

**Decision: Build JSON directly in a helper function**, not through `PromptTemplate`. The template system uses `${var}` substitution which conflicts with JSON `{}`. We'll add `build_character_sheet_prompt()` as a standalone function in `characters.py` and call it from `build_plan_from_request`.

### Step 3: Update `build_plan_from_request` for CHARACTER (non-extension)

Change from:
- 2 `PlannedPrompt`s with `character_single_direction` template
- `expected_frames=1` each

To:
- 1 `PlannedPrompt` with key `"character_sheet"`
- Prompt text = JSON from `build_character_sheet_prompt()`
- `expected_frames=2` (or 5 for 8-dir)
- `layout="auto_detect"` (new layout strategy for gray-bg sheets)
- New field or parameter flag: `solid_background=True`

### Step 4: Update extraction to handle solid-background sheets

The extractor's `extract_frames()` currently tries separator detection first. For character sheets on gray backgrounds:

1. Add a new layout strategy `"reference_sheet"` that:
   - Converts the gray background to transparent (threshold-based: pixels close to `#6B6B6B` become alpha=0)
   - Then runs `auto_detect` (connected component analysis) to find individual sprites
   - Sorts detected sprites left-to-right by x-position
2. Wire this up in `extract_frames()` when `layout == "reference_sheet"`

### Step 5: Update executor to skip grid template for character sheets

In `executor.py`, the generate stage currently inserts a grid template reference for multi-frame prompts. For character sheets with `layout="reference_sheet"`, skip the grid template insertion — the JSON prompt already describes the layout.

### Step 6: Update QA for character sheets

- Skip `palette_delta` check (already skipped for batch types)
- The `frame_nonempty` check works as-is
- Frame count check: expected = number of views

### Step 7: Handle extension mode

Extension mode (adding animations to existing characters) stays on the current approach — it already works with reference images + magenta strips. No change needed.

### Step 8: Tests

- Update `test_build_plan_character_default` to expect 1 prompt with `expected_frames=2`
- Add test for JSON prompt structure validation
- Add test for 8-dir variant producing 1 prompt with `expected_frames=5`

---

## Files to Change

| File | Change |
|------|--------|
| `src/pixel_magic/generation/prompt_library/characters.py` | Add `build_character_sheet_prompt()` function |
| `src/pixel_magic/workflow/tools.py` | Update CHARACTER branch in `build_plan_from_request` |
| `src/pixel_magic/generation/extractor.py` | Add `reference_sheet` layout handler |
| `src/pixel_magic/workflow/executor.py` | Skip grid template for `reference_sheet` layout |
| `tests/test_workflow_tools.py` | Update character plan tests |

## What Stays the Same

- Extension mode (animation strips from reference images)
- All other asset types (effects, UI, tilesets, items)
- The `PromptTemplate` system — not modified, just not used for this specific case
- Export/postprocess pipeline — receives frames as before
