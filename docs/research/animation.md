# Animation Research — What We Tried & Learned

**Date:** March 2026
**Goal:** Generate animation sprite sheets (walk, attack, idle, etc.) from a single character reference image.

---

## Approach 1: Sprite Sheet Generation via Image Models (Gemini/OpenAI)

**Idea:** Ask an image generation model to produce a sprite sheet (6 frames in a row) showing different poses of the same character.

**What we built:**
- `build_animation_prompt()` — narrative prompt with per-frame pose descriptions
- Gemini `generate_with_images()` — multimodal input (reference image + prompt)
- OpenAI Responses API with `image_generation` tool
- CLI `animate` subcommand with `--subject`, `--character`, `--animation`, `--direction`, `--frames-file`

**What worked:**
- 4:1 aspect ratio forced Gemini into a single-row 6-frame layout consistently
- Attack/swing animations produced visibly different sword positions across frames
- Narrative prompts (not JSON) worked better for Gemini
- Animation-type-aware default descriptions (walk, run, attack, idle) helped

**What didn't work:**
- Walk/idle animations had nearly identical poses — models copy the reference 6 times
- Character consistency drifted between frames (proportions, facing direction)
- Weapon/limbs bled across cell boundaries in some frames
- Isometric perspective broke during dynamic poses (attack wind-up caused rotation)
- No amount of prompt engineering made walk/idle visually distinct enough for game use

**Key lessons:**
- Image generation models don't understand animation — they generate a grid of similar images
- Dramatic actions (attack) work because the model knows what sword positions look like
- Subtle animations (walk, idle) fail because the model defaults to copying the reference
- For a robed character, leg descriptions are useless — legs are hidden by robes
- The subagent evaluator was too generous — always check results with your own eyes

---

## Approach 2: Local Video Generation (Wan 2.2 via mlx-video)

**Idea:** Use an open-source video model to animate the reference image, extract frames.

**What we built:**
- GGUF-to-MLX conversion pipeline (Q8_0 GGUF → MLX safetensors with key remapping)
- `WanProvider` wrapping mlx-video's `generate_video()`
- Frame extraction from MP4 output
- Conversion script handling VAE, T5 encoder, transformer weight format differences

**Models tried:**
- Wan 2.2 TI2V-5B (Q4 quantized) — converted and ran successfully
- Wan 2.2 I2V-14B (Q8_0 from GGUF) — converted and ran successfully after fixing config

**What worked:**
- 5B model: generated video in ~2 minutes, but output was generic (not pixel art)
- 14B model: generated video in ~14 minutes, character was recognizable, some movement
- GGUF→MLX pipeline worked after fixing: key name remapping (ffn.0→fc1), patch_embedding reshape (5D→2D), VAE sanitization, complete config.json with all fields

**What didn't work:**
- 14B model output was zoomed in, anti-aliased, blurry — not pixel art quality
- Pixel-animate LoRA (trained on 14B) OOM'd on 36GB RAM — LoRA merge dequantizes Q8→f16 which doubles model size
- 5B model incompatible with the pixel-animate LoRA (different dimensions: 3072 vs 5120)
- Full PyTorch→MLX conversion of 14B OOM'd during conversion (needs ~30GB+ just for the load)
- Without the pixel-animate LoRA, video output looks like generic AI video, not pixel art

**Key lessons:**
- 36GB RAM is borderline for 14B models — Q8_0 inference works but LoRA merge doesn't fit
- The pixel-animate LoRA was the critical ingredient for pixel art style — without it, results are generic
- GGUF and MLX quantization formats are different — mx.load() handles GGUF natively but weight key names need remapping for mlx-video's model architecture
- Video models fundamentally produce smooth/interpolated output — pixel art's deliberate choppiness is antithetical to what they're trained on
- Model conversion is fragile — config fields (boundary, cross_attn_norm, ffn_dim, out_dim) must all be correct or output is noise

---

## Approach 3: Commercial Video API (Runway Gen-4 Turbo / Gen-4.5)

**Idea:** Use Runway's API for image-to-video, save the output video.

**What we built:**
- `RunwayProvider` using the `runwayml` Python SDK
- Auto-padding to match aspect ratio (prevents cropping)
- 2-second minimum duration at 16:9 (1280x720)

**What worked:**
- API integration was simple — ~60 lines of code
- gen4_turbo: $0.10/clip, 2-second minimum, ~30 second generation
- gen4.5: $0.24/clip, higher quality
- Character was recognizable in the output
- Some movement/animation visible

**What didn't work:**
- Output quality was not good enough for pixel art sprites
- The model smooths/anti-aliases pixel art — loses the grid-perfect aesthetic
- 2 seconds is still too many frames for a 6-frame sprite animation
- gen4_turbo can't set last frame (no loop guarantee)
- Even gen4.5 (best quality) wasn't sufficient — needs an even better model
- Transparent PNG caused task failures — had to use JPEG with black padding

**Key lessons:**
- Runway is the only commercial API supporting <5 second clips (2s minimum)
- gen4_turbo: first-frame-only reference, no last-frame support
- gen3a_turbo and veo3.1 support first+last frame for looping, but min 4-5 seconds
- Image must be padded to match the ratio or Runway crops from center
- Video models are fundamentally designed for realistic footage, not sprite animation
- Even the best commercial models produce output that needs heavy post-processing for pixel art use

---

## Approach 4: Manual Testing on Runway Website

**Idea:** Test the same prompts directly on Runway's web UI to rule out our code as the issue.

**Prompt used:**
```
Static fixed camera, no camera movement. A pixel art character sprite performing walking cycle.
Isometric 3/4 top-down view. The character stays centered in frame, only the limbs move.
Solid flat background, completely static. Retro 16-bit video game sprite animation style.
```

**Result:** Runway 4.5 on the website produced better results than our API integration. The quality gap confirmed that the approach has potential but needs very high-end models and careful tuning. However, even the best results weren't directly usable as pixel art sprites without post-processing.

---

## Approach 5: Single-Frame Generation from Reference (Gemini)

**Idea:** Generate animation frames one at a time instead of a whole sprite sheet. We tried three variations:

**What we built:**
- `generate_with_images()` on GeminiProvider — multimodal input (images + text → image)
- CLI `animate` subcommand with `--name`, `--animation`, `--frames`, `--direction`, `--reference`, `--loop/--no-loop`
- Animation plan system with per-frame descriptions for walk, idle, attack at various frame counts

### 5a. Binary Subdivision

Give the model two anchor frames (before + after) and ask for the middle frame. Subdivide recursively to fill a full cycle.

**Result:** Character consistency was good, but poses barely changed. When both anchors are the same idle pose (looping animation), the midpoint stays close to idle. The model is pulled back toward the anchors instead of creating dramatic motion. Attack animations were slightly better than walk but still insufficient.

### 5b. Sequential Generation with Full Context

Generate frames in order. Each call receives ALL previously generated frames + the final frame (if looping) + a text prompt with the full animation plan showing what every frame should be.

**Result:** More pose variation than binary subdivision, but the model becomes conservative with accumulated context — makes tiny incremental changes. At 9 frames, frames stagnate (especially in recovery phase — frames 6-8 were nearly identical). The full animation plan with per-frame descriptions didn't help — model still produced similar-looking frames in the later sequence. 5-frame attack without the plan was actually the best variant here.

### 5c. Edit-Based (Inpainting Style)

Send only the PREVIOUS frame + an edit instruction ("move the katana to overhead position"). Each frame is an edit of the last, not a generation from scratch.

**Result:** Most pose variation of all three approaches — the edit framing gives the model permission to make bigger changes. BUT character consistency degrades with each frame. By frame 6, the character has drifted significantly from the original — proportions change, pixel art precision is lost, style becomes more painterly. Error compounds because each frame edits the already-drifted previous frame.

### Overall Approach 5 Lessons

- **Fundamental tension:** Approaches that preserve consistency (5a, 5b) produce minimal pose variation. Approaches that produce good pose variation (5c) lose consistency.
- **Image generation models don't understand animation** — they don't have a concept of "the same character in a different pose." They either copy the reference or drift.
- **The problem is not prompt engineering** — we tried narrative prompts, JSON prompts, animation plans, edit instructions. The model's behavior is dominated by the input images, not the text.
- **Cost is very low** (~$0.01/frame) so this remains viable if quality can be solved.
- **Generated frames are larger than reference** (Gemini outputs ~1024px) — would need existing resize pipeline.

---

## Considered & Rejected

### PixelLab (pixellab.ai)

Purpose-built pixel art generation tool with Python SDK (`pixellab` on PyPI), REST API, and MCP server. Supports skeleton-based and text-prompt animation, 4/8 directional variants, sprite sheets. Pricing: $12–$50/mo. Reviews are positive for static assets.

**Why rejected:** Doesn't support custom animation properly — limited to their predefined animation types. Not flexible enough for our use case of generating arbitrary animation cycles from a reference image.

### God Mode AI (godmodeai.co)

Auto-rigs 2D sprites and applies from a library of 2000+ animations, exports as Spine files. Pay-per-credit model.

**Why not pursued:** Significant quality gap between promo materials and actual user output. Forces rigging + animation together (no fine-tuning individual components). Community reports of quality issues. Not pixel-art-specific.

---

## Approaches Still Worth Trying

### A. ComfyUI + AnimateDiff + Pixel Art LoRA (Local)

**Idea:** Fully local pipeline using Stable Diffusion with AnimateDiff for animation + ControlNet for pose consistency + pixel art LoRA for style. Unlike video models, this generates frames as pixel art natively — no post-processing needed.

**Why this is different from what we tried:**
- Generates pixel art directly (LoRA-driven) — not smooth video that needs pixelization
- Per-frame control via ControlNet — can specify exact poses, not just a text prompt
- Palette-locked workflows reported 82% reduction in inter-frame palette variance
- One studio reported 99.3% frame-to-frame palette match
- SpriteSheetMaker ComfyUI node handles output formatting

**Pipeline:**
1. Train or use existing pixel art LoRA on character
2. AnimateDiff + ControlNet for pose-consistent animation frames
3. Palette-lock workflow to enforce consistent colors
4. Image pixelate node for grid-aligned output
5. SpriteSheetMaker node for final sprite sheet

**Downsides:** Heavy setup, requires ComfyUI familiarity, may need character-specific LoRA training for consistency. Unknown how well it works on macOS (most workflows assume NVIDIA GPU).

### B. AI Auto-Rig + Skeletal Animation

**Idea:** Skip frame-by-frame generation entirely. Auto-rig the reference sprite, apply animation from a library or text prompt.

**Why this is different from what we tried:**
- Not a generation model at all — transforms the existing sprite deterministically
- Same rig + same animation = same result every time
- Game-engine-ready formats (Spine, sprite sheet)

**Tools:**
- **Pixa** (pixa.com) — upload image → auto-detect articulation points → rig → animate
- **Spine2D** (spine2d.com) — AI-powered rigging, industry-standard Spine export

**Downsides:** Rigged animation looks different from hand-drawn frame-by-frame pixel art. Pixel art characters (especially small ones) may not rig well — limbs are often 1-2 pixels wide. Not clear if any of these tools have APIs for programmatic use.

---

## Ruled Out (Same Category as What We Tried)

### Video generation models (Hailuo, Kling, Wan 2.5, Seedance, etc.)

All video models — including Hailuo I2V-01-Live (marketed for "2D art animation" but really Live2D-style illustration), Kling 2.5/2.6, Wan 2.5, Seedance 1.0 Pro — share the same fundamental problem we already hit with Runway and Wan 2.2: they produce smooth, anti-aliased, interpolated output. Pixel art's grid-aligned, limited-palette aesthetic is the opposite of what these models are trained to produce. Better model quality doesn't fix this — it makes the output smoother, which is the wrong direction.

---

## Approach 6: Grid Canvas with Platforms + Gemini Image Config (CURRENT — WORKING)

**Idea:** Instead of a horizontal strip, arrange frames in a 2D grid that matches Gemini's supported aspect ratios. Add isometric platform tiles for perspective grounding, pixel-art frame numbers for ordering, and auto-scale the character based on tile count. Let Gemini fill in the empty slots, then clean up platforms in a second pass.

**What we built:**
- Grid canvas layout (`build_canvas()`) — frames in cols×rows targeting supported Gemini ratios (1:1, 5:4, 4:3, 3:2, 16:9)
- Pixel-art frame numbers — hardcoded 3×5 bitmap digits, white with black outline, top-left of each cell
- Multi-tile isometric platforms (`create_platform_grid()`) — 1 tile (walk/idle), 4 tiles / 2×2 (attack), 9 tiles / 3×3 (cast/spell). Drawn as unified blocks with grid lines (not pasted individual tiles — eliminates seam artifacts)
- Auto char_scale — character shrinks for larger grids (0.80 / 0.54 / 0.40) keeping canvas compact
- Character centered on tile grid — feet positioned at grid center, not top
- Gemini `image_config` — passes `aspect_ratio` and `image_size` to control output dimensions
- Canvas padding — pads to exact Gemini ratio with chromakey fill, slots centered in evenly-divided cells
- Platform + number removal — second Gemini pass strips platforms and frame numbers
- Grid-aware frame extraction — extracts from cell-centered positions

**What works:**
- **Walk (1 tile, 6f loop):** Good pose variation across the cycle, character stays consistent
- **Attack (4 tiles, 4f no-loop):** Katana slash with full extension, visible slash effects — extra floor space lets the character swing wide
- **Cast (9 tiles, 4f no-loop):** Energy vortex spell effect that spreads across the large platform
- Grid layout gives Gemini natural image proportions (no extreme aspect ratios)
- Frame numbers give Gemini explicit ordering context in the 2D grid
- Platforms establish ground plane and isometric perspective — Gemini respects the 3/4 top-down angle
- Canvas sizes stay compact (~900-1400px, well within Gemini limits)
- Second pass platform removal works reliably

**Key design decisions:**
- Grid layout targets Gemini's supported ratios (not arbitrary 16:9) — eliminates output distortion
- Landscape-only ratios (no portrait) — animation grids read left-to-right naturally
- Waste penalty in grid scoring — prefers exact-fit grids (3×2 for 6 frames, 2×2 for 4) over closer-ratio grids with empty cells
- `image_size` picks smallest tier covering the canvas (1K for ≤1024px, 2K for ≤2048px)
- Padding distributed by centering slots in cells — not packed top-left

**Canvas configurations (samurai, 345×482 reference):**

| Tiles | Frames | Grid | Gemini Ratio | Size | Canvas |
|-------|--------|------|-------------|------|--------|
| 1 | 6 (loop) | 3×2 | 1:1 | 2K | 1035×1035 |
| 1 | 4 (once) | 2×2 | 1:1 | 1K | 996×996 |
| 4 | 6 (loop) | 3×2 | 5:4 | 2K | 1296×1037 |
| 4 | 4 (once) | 2×2 | 1:1 | 1K | 908×908 |
| 9 | 6 (loop) | 3×2 | 4:3 | 2K | 1422×1067 |
| 9 | 4 (once) | 2×2 | 1:1 | 1K | 948×948 |

**Why this works when previous approaches didn't:**
- Platforms solve the perspective problem — model sees where the ground is and maintains isometric angle
- Grid layout solves the aspect ratio problem — Gemini handles natural proportions better than extreme strips
- Frame numbers solve the ordering problem — model knows frame sequence in a 2D grid
- Multi-tile scaling solves the room problem — attack/cast animations get floor space without ballooning canvas
- Second-pass cleanup is simple and reliable — just remove non-character pixels

**Cost:** ~$0.02-0.04 per animation (generation + cleanup pass)

---

## Approach 6b: Improved Prompts, Slot Padding & Reference Forwarding (April 2026 — IN PROGRESS)

Building on Approach 6, this round addressed quality issues with dynamic poses, frame consistency, and model instruction adherence.

### Problems identified in Approach 6

1. **Pose overflow** — attack/lunge/spell animations extend beyond the standing-pose slot boundaries. The model generates clipped limbs and weapons because slots are sized to the static reference.
2. **Character drift** — Gemini only sees the reference embedded in the canvas at slot 1 (small, surrounded by chromakey). Proportions, colors, and details drift across frames.
3. **Fixed animation types** — the old `--animation-type walk` enum limited users to predefined motions. Users couldn't describe arbitrary animations.
4. **No per-frame control** — the prompt said "fill the middle slots" but never described what each frame should look like. The model guessed, producing repetitive or discontinuous poses.
5. **Frame number readability** — small Pixelify Sans font caused Gemini to misread "2" as "3", producing wrong frame ordering.
6. **No visual containment** — slots had no borders, so the model had no visual cue for where one frame ends and the next begins. Characters bled across slot boundaries.
7. **Vague prompt instructions** — "fill the remaining slots" instead of exact numbers; ordinal image references ("the FIRST image") instead of named references.

### What we changed

**A. Slot padding (`--padding`, default 0.2)**

Pad the reference frame and slot_bg by a configurable fraction before building the canvas. A 0.2 padding means 20% extra space on each side — a 316×499 reference becomes a 442×698 slot. This gives dynamic poses room to extend without clipping.

Implementation: padding happens in `generate_animation()` after platform compositing but before `build_canvas()`. For multi-batch, batch 0 produces padded slots; batch N>0 extracts the overlap frame at padded size (no compounding). `build_canvas`, `build_empty_canvas`, and `extract_frames` are untouched.

**B. Reference image forwarding**

Send the clean reference sprite as a separate image to Gemini, alongside (and before) the canvas. The prompt names it explicitly: `{"image_1": "character_reference", "description": "Clean standalone view of the character..."}`. This gives Gemini an uncluttered view of proportions, colors, and details — not just the small reference embedded in slot 1 of a busy canvas.

Image order: `[character_reference, previous_batch_sheet?, canvas_template]`

**C. Free-form animation descriptions**

Replaced `--animation-type` (fixed enum: walk, run, attack, idle, etc.) with `--animation-description` (free text). Users describe any motion they want:
```
--animation-description "a heavy overhead sword slash — raises sword with both hands and brings it down in a diagonal arc"
```

**D. Per-frame pose descriptions (`--frame-poses`)**

Required for animate/animate-object. Each fillable slot gets a detailed pose description from the user:
```
--frame-poses \
  "sword arm rises, weight shifts to back foot, shield tucked" \
  "sword fully overhead, knees bent, cape blown upward" \
  "mid-swing diagonal arc, arms extended, torso twisted" \
  ...
```

These flow into the prompt's `frames` array:
```json
"frames": [
  {"slot": 1, "description": "reference pose — do not modify", "anchor": true},
  {"slot": 2, "description": "sword arm rises, weight shifts to back foot..."},
  ...
]
```

**E. Thick white slot borders**

Added visible white borders (3px for standard slots, 4px for large canvases) between slots with 2-4px gaps. This gives the model a clear visual boundary for each frame. The prompt references them: "Each slot is enclosed in a thick white border with visible gaps between them — keep all drawing WITHIN the bordered area."

A cleanup pass (Gemini 2nd call) removes borders and frame numbers after generation, before frame extraction. This runs for ALL animations now, not just platform mode.

**F. Larger frame numbers**

Bumped font size from `cell_w // 18` to `cell_w // 10` (minimum 24px). Frame numbers are now clearly legible and Gemini no longer misreads them.

**G. Named image references in prompts**

Replaced fragile ordinal references ("the FIRST image", "the SECOND image") with named references:
```json
"attached_images": [
  {"image_1": "character_reference", "description": "Clean standalone view..."},
  {"image_2": "canvas_template", "description": "The grid canvas with numbered slots..."}
]
```

For multi-batch continuation:
```json
"attached_images": [
  {"image_1": "character_reference", "description": "..."},
  {"image_2": "previous_batch_sheet", "description": "..."},
  {"image_3": "canvas_template", "description": "..."}
]
```

**H. Generation plan section**

Multi-batch prompts now include explicit planning context so the model doesn't try to cram the entire animation into one batch:
```json
"generation_plan": {
  "total_animation_frames": 10,
  "total_batches": 2,
  "this_batch": "Batch 1 of 2: generates frames 1–6 of 10 total",
  "instruction": "Generate only the 6 frames shown on this canvas. Do NOT try to complete the entire 10-frame animation."
}
```

**I. Character orientation**

The prompt now includes the facing direction: `"orientation": "The character is facing south-west in an isometric 3/4 top-down view."` Threaded from CLI `--direction` through `generate_animation` → `_generate_single_batch` → prompt builder.

**J. Exact slot counts in instructions**

Replaced vague "fill the remaining slots" with exact numbers: "Fill the 5 remaining slots (slots 2–6)" or "Fill the 4 remaining slots (slots 7–10)".

**K. Thinking mode support**

Added `thinking: bool` parameter to `GeminiProvider.generate_with_images()`. When enabled, uses Gemini's `thinking_config` with a 4096-token budget. Early tests show the model adheres more closely to per-frame pose descriptions with thinking enabled — it plans the pose progression before generating.

**L. Prompt debug output**

Every generation now saves the rendered JSON prompt to the output directory (`prompt.json` for single-batch, `batch_N_prompt.json` for multi-batch). Essential for debugging prompt issues.

### Test results (April 2026)

Tested three scenarios with detailed per-frame poses:

| Test | Frames | Platform | Result |
|------|--------|----------|--------|
| Walk cycle (loop) | 4 | none | Subtle weight transfer, loop closure works. Detailed poses helped but walk cycles remain challenging. |
| Sword attack (no-loop) | 6 | 4-tile | Best results — clear progression from coil → overhead → slash → follow-through. 4-tile platform gave room for lunge. |
| Fire spell (no-loop) | 5 | 9-tile | Good fire effects — channeling → flame glow → eruption. 9-tile platform provided space for VFX spread. |

**With thinking mode enabled:** Sword attack at 12 frames showed notably better adherence to pose descriptions. The model produced more distinct intermediate poses rather than blending adjacent frames.

### Key lessons (so far)

- **Per-frame descriptions matter enormously** — but they must be physically accurate and respect the character's actual equipment (one-handed sword if shield is equipped, not two-handed).
- **More frames help quality** — 12-frame attack animations give more room for subtle pose transitions than 6-frame ones. The model doesn't have to make huge jumps between frames.
- **Writing good frame descriptions is hard** — requires understanding animation principles (anticipation, follow-through, weight transfer). This motivated the planned animation design agent.
- **Thinking mode improves adherence** — the model plans better when it can "think" before generating.
- **Slot borders solve containment** — characters no longer bleed across slot boundaries.
- **Reference forwarding visibly improves consistency** — especially in multi-batch runs where the canvas reference is small.

### What's still not solved

- **Model sometimes ignores pose descriptions** — especially subtle details like shield position or cape direction. Thinking mode helps but doesn't guarantee compliance.
- **Font rendering** — Pixelify Sans "5" can still look like "8" at certain sizes. May need a different font or switch to bitmap digits.
- **Walk/idle animations** — still the weakest category. Subtle motions are hard for the model to differentiate from the reference pose.
- **Automatic pose generation** — writing 10+ detailed frame descriptions manually is tedious. Planned: animation design agent that takes "walk" and produces proper frame-by-frame descriptions.

---

## Approach 6c: Animation Cleanup Pass (April 2026)

**Problem:** With thick white borders and large frame numbers on the canvas, these guide elements persist in Gemini's output. Platform removal was already a second Gemini pass — extended this to ALL animations.

**What we built:**
- `build_animation_cleanup_prompt()` — JSON prompt instructing Gemini to remove white borders, frame numbers, and any guide artifacts while preserving the character/object artwork
- Non-platform animations now get a cleanup pass too (previously only platform mode had one)
- Template: `animation_cleanup.json.j2`

**Result:** Clean frames with no residual borders or numbers. The cleanup pass is lightweight (~1-2 seconds) and reliable.

**Cost impact:** Every animation now costs 2 Gemini calls per batch instead of 1 (or 2 for platform, now 2 for all). Total cost ~$0.03-0.06 per animation.

---

## Approach 6d: Canvas Polish, Cleanup Hardening & Model Comparison (April 2, 2026)

Building on 6b/6c, this session focused on canvas visual quality, cleanup robustness, and comparing Gemini models.

### Canvas layout improvements

**Problem:** Slot borders were too thin for the model to see clearly; frame numbers were tiny and positioned inside the slot area where the reference sprite covered them; boxes were not properly distributed across the page.

**What we changed:**
- **Border thickness tuning** — tested 5px, 25px, and 100px. 5px was the sweet spot: clearly visible without wasting canvas space.
- **Frame number repositioning** — moved from inside the slot area to the corner of the border band. Increased font size to `max(32, cell_w // 6)` (~61px for typical slots).
- **Proper grid distribution** — slots now use even page division with proper margins between boxes and around edges, rather than being centered within cells with minimal gaps.
- **Default padding bumped to 0.2** — characters were filling 98% of reference image bbox (316x499 sprite in 316x499 image). Added 20% padding by default so dynamic poses have room.

### Cleanup prompt hardening

**Problem:** Gemini Pro added shadow/ground artifacts (brown smudges, dirt patches, gradients) behind characters. The original cleanup prompt only asked to remove "thick white cell borders, white frame numbers, white gaps" — it didn't address background contamination.

**What we changed:**
- Added removal targets: "any shadows or ground artifacts", "any color variation in the background — gradients, smudges, dirt patches, or shading"
- Strengthened background rule: "The ENTIRE background must be one single flat color: {hex_color}. No gradients, no shadows, no ground, no shading, no variation whatsoever"
- Added pixel-level specificity: "Every pixel that is not part of a {subject} must be exactly {hex_color}"
- Added explicit shadow removal: "If the {subject} has a shadow or ground plane underneath it, REMOVE IT"

**Result:** Clean solid chromakey backgrounds even with Pro model output that added heavy shadow/ground effects.

### Model comparison: Gemini 3.1 Flash vs 2.5 Pro

Tested identical prompts (knight walk cycle, 6 frames, south_east, looping) on both models.

| Aspect | 3.1 Flash (8192 thinking) | 2.5 Pro (8192 thinking) |
|--------|--------------------------|------------------------|
| Pose variation | Subtle — frames look similar | Better — visible leg/arm differences |
| Character consistency | Good | Good (slightly better detail preservation) |
| Background artifacts | Clean green | Added shadows, ground planes, color gradients |
| Cleanup ease | Minimal cleanup needed | Aggressive cleanup prompt needed |
| Speed | ~15-20s per batch | ~25-35s per batch |
| Walk cycle quality | Still weak — minimal foot/leg differentiation | Improved — but still not game-ready |

**Key finding:** Pro generates better poses but adds unwanted realism (shadows, ground planes) that contaminates the chromakey. Flash is cleaner but less expressive. Neither model solves walk cycles.

### Multi-batch + platform (12-frame run cycle)

Tested 12-frame run cycle with 4-tile platform on Flash. Results were poor:
- Batch 2 overlap frame (slot 6) had brown background contamination from batch 1
- Platform cleanup mangled sprites — partial removal left green smudges
- Character size inconsistent between batches
- Frame 10 overlap was tiny/broken, frames 11-12 lost platform entirely

**Conclusion:** Multi-batch works acceptably for non-platform animations but the platform cleanup pass struggles with accumulated artifacts across batches. The overlap frame carries contamination from one batch to the next.

### Thinking budget

Tested thinking budgets: 5000 and 8192 tokens. 8192 was kept as default. The model uses thinking time to plan pose progression before generating.

---

## Approach 7: Single-Frame Sequential Generation (CURRENT — WORKING)

**Idea:** Generate one frame at a time instead of a whole grid. Each Gemini call receives the reference sprite + the most recently generated frame as image context, plus a focused JSON prompt describing just that one frame's pose. No canvas grid, no frame numbers, no cleanup pass.

**What we built:**
- `generate_animation()` loops through `frame_poses`, making one Gemini call per frame
- `build_single_frame_prompt()` — focused JSON template describing one frame's pose, animation context, and art constraints
- Aspect ratio snapping with portrait support (3:4, 2:3, 9:16) to match reference dimensions
- Scale normalization — generated frames rescaled to match reference height, then padded to uniform bounding box with bottom-center anchoring
- Removed: `BatchInfo`, `_compute_batches`, `_generate_single_batch`, `_slice_frame_poses`, canvas-based animation templates, cleanup pass for animations
- CLI simplified: `--frame-poses` is the only frame control (each entry = one Gemini call). Removed `--frames`, `--padding`, `--tiles`, `--platform` from animate/animate-object commands.

**What works:**
- **Walk cycle (9 frames, loop):** Clear leg alternation, arm swing, cape motion. Much better pose variation than grid approach.
- **Spear attack (7 frames, no-loop):** Clean anticipation → thrust → follow-through → recovery arc. Spear extension looks natural.
- **Shield spell (7 frames, no-loop):** Magical barrier dome forms naturally in middle frames, energy effects appear without prompting.
- Character consistency maintained across all frames via reference image context
- No grid artifacts, no borders, no frame numbers to clean up
- No frame count limit — 9+ frames work fine
- Cost: ~$0.01/frame (one Gemini call each)

**Why this works when the grid approach didn't:**
- Each frame gets Gemini's full attention and resolution — not a small slot in a grid
- The model only needs to generate ONE pose, not understand animation sequence ordering in a grid
- Reference + previous frame context provides both consistency anchor and motion continuity
- No cleanup pass needed (no guides to remove) — saves cost and avoids cleanup artifacts
- Portrait aspect ratio matching keeps output close to reference dimensions

**What's still not perfect:**
- Generated frames are slightly larger than reference (~416×624 vs 316×499 at 2:3/512) — handled by scale normalization
- Subtle walk/idle motions still less dramatic than attack/spell, but significantly better than grid approach
- Each frame is an independent Gemini call — no batch discount, cost scales linearly with frame count

**Cost:** ~$0.01/frame × N frames (e.g., 9-frame walk = ~$0.09)

---

## Overall Conclusions

1. **Approach 7 (single-frame sequential generation) produces the best results.** Each frame gets full Gemini attention; reference + previous frame context maintains consistency while allowing pose variation. No grid artifacts, no cleanup needed.

2. **Approach 6 (grid canvas) was a useful stepping stone** but ultimately limited by the model's ability to fill multiple slots consistently in a grid. The cleanup pass introduced its own artifacts.

3. **Video models** (Approaches 2-4) fail because they smooth/anti-alias pixel art.

4. **Image models generating frames individually** (Approach 5) failed when tried earlier, but the key difference with Approach 7 is: focused single-frame prompts with reference context, not full animation plans or edit chains.

5. **The bottleneck is prompt quality.** With single-frame generation, the main factor in animation quality is the per-frame pose descriptions. The animation design agent automates this.

6. **Remaining opportunities:**
   - Higher-resolution base characters (256×256) for more detail per frame
   - Hybrid model pipeline — Pro for some frames, Flash for others
   - Walk/idle cycles still benefit from more exaggerated pose descriptions
   - Cost optimization — parallel frame generation where independence allows it

---

## Cost Reference

| Method | Cost/clip | Min duration | Quality for pixel art |
|--------|-----------|-------------|----------------------|
| Gemini sprite sheet | ~$0.01 | N/A (image) | Poor (inconsistent poses) |
| Wan 2.2 14B local | Free (compute) | 17 frames | Poor without LoRA |
| Wan 2.2 14B + LoRA | Free (compute) | 17 frames | Unknown (OOM on 36GB) |
| Runway Gen-4 Turbo | $0.10 | 2 seconds | Mediocre |
| Runway Gen-4.5 | $0.24 | 2 seconds | Decent but not pixel-perfect |
| PixelLab | $12–50/mo | N/A (frames) | Good for static, limited animation |
| ComfyUI + AnimateDiff | Free (compute) | N/A (frames) | Unknown (untested) |
| Gemini frame interp. | ~$0.01/frame | N/A (frames) | Consistent but minimal motion |
| Gemini frame edit | ~$0.01/frame | N/A (frames) | Good motion but character drifts |
| Gemini grid canvas (deprecated) | ~$0.02-0.04/anim | N/A (grid) | Good — but grid artifacts and cleanup issues |
| Gemini grid + improved prompts (deprecated) | ~$0.03-0.06/anim | N/A (grid) | Better but cleanup pass added its own problems |
| **Gemini single-frame (current)** | **~$0.01/frame** | **N/A (frames)** | **Best — full attention per frame, no grid artifacts** |
| Pixel Engine | ~$0.04/frame | N/A (frames) | Unknown (untested) |

## Files & Models (not committed)

- `models/Wan2.2-I2V-A14B-GGUF/` — Q8_0 GGUF weights (~30GB)
- `models/Wan2.2-I2V-A14B-MLX/` — converted MLX safetensors (~45GB)
- `models/Wan2.2-TI2V-5B-MLX-Q4/` — 5B model Q4 (~16GB)
- `models/pixel-animate-lora/` — pixel art LoRA for 14B (~3.6GB)
- All under `models/` which is gitignored
