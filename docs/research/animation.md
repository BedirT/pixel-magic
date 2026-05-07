# Animation Research — What We Tried & Learned

**Date:** March 2026, updated May 2026
**Goal:** Generate animation sprite sheets (walk, attack, idle, etc.) from a single character reference image.

---

## Current Status (May 2026)

We are pausing animation-model work until we have reliable GPU access again,
probably in about a month.

The current production path remains the **Gemini grid canvas + platform
workflow**. It is still the only approach here that has produced usable game
sprite frames with acceptable identity and pose variation.

Recent experiments tested whether newer image generation and local video-model
workflows change that conclusion. They do not, yet:

- OpenAI image generation can create transparent outputs, but frame-to-frame
  motion is not controlled tightly enough.
- Yume 1.5 5B MLX runs locally at tiny settings, but the character mostly
  freezes and backgrounds/alpha are not stable.
- Wan2.2 Animate 14B GGUF is the most promising local video model family, but
  the current Codex/PyTorch runtime cannot use Apple MPS. CPU-only ComfyUI is
  too slow before sampling even starts.

Next revisit should start from **Wan2.2 Animate with a working accelerator**:
either a CUDA box, a fixed PyTorch/MPS environment, or an MLX-native
pose-conditioned WanAnimate path.

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

## Approaches To Revisit Later

### A. ComfyUI + AnimateDiff + Pixel Art LoRA (Paused)

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

**Status:** Paused until reliable GPU access is available. The May 2026
WanAnimate experiment proved that CPU-only ComfyUI is not a practical path for
this project.

**Downsides:** Heavy setup, requires ComfyUI familiarity, may need
character-specific LoRA training for consistency. Most workflows assume NVIDIA
GPU, and the current Codex/PyTorch runtime cannot use Apple MPS.

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

### Generic video generation models (Hailuo, Kling, Wan 2.5, Seedance, etc.)

Generic image-to-video models — including Hailuo I2V-01-Live (marketed for
"2D art animation" but really Live2D-style illustration), Kling 2.5/2.6,
Wan 2.5, Seedance 1.0 Pro — share the same fundamental problem we already hit
with Runway, Wan I2V, and Yume: they produce smooth, anti-aliased,
interpolated output. Pixel art's grid-aligned, limited-palette aesthetic is the
opposite of what they are trained to produce. Better model quality usually
makes the output smoother, which is the wrong direction.

Wan2.2 Animate is carved out from this ruling because it supports reference
character plus pose/background conditioning. It is still paused until a real
accelerator path is available.

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

## Approach 7: OpenAI Image Generation Retest (May 2026)

**Idea:** Re-test image-only animation now that Codex can directly generate
images and OpenAI image generation can produce transparent assets. Avoid
chromakey/background tricks and judge the result by adjacent-frame usability,
not rough thumbnail appeal.

**What we tried:**
- Direct walk and attack prompts
- Transparent edit workflows
- Transparent anchor canvas workflows
- Comparison against the existing Gemini grid output

**What worked:**
- Transparent assets can be generated directly.
- Rough contact sheets can look plausible at a glance.
- Direct image generation is fast enough for iteration.

**What didn't work:**
- Direct prompts often returned full opaque canvases instead of clean isolated
  sprites.
- Transparent/edit outputs had unstable alpha and semi-transparent edges.
- Frame bounding boxes shifted heavily between adjacent frames.
- The model changed the character shape instead of making subtle local motion.
- Anchor canvases improved framing but did not solve frame-to-frame
  consistency.

**Useful metric signal:**
- Some transparent OpenAI runs had adjacent alpha-union change ratios around
  `0.31-0.69`, which is far too much silhouette churn for a walk cycle.
- The Gemini grid baseline loop had a much better closure signal on walk:
  frame 6 -> frame 1 alpha change ratio was about `0.004`.

**Verdict:** Not production-usable. The issue is not transparency support; it is
motion continuity. The frames can look good independently and still fail as an
animation.

---

## Approach 8: Yume 1.5 5B via MLX (May 2026)

**Idea:** Use a smaller local MLX video model to animate a sprite input, then
extract a tiny set of frames.

**Runtime setup:**
- Used the GitHub `mlx-video` package, not the PyPI package. The PyPI package
  exposed only low-level helper modules.
- Downloaded `ckurasek/Yume-1.5-5B-720P-MLX` manually because passing the model
  repo as `--model-dir` did not auto-download it.

**Runs:**
- `384x640`, 17 frames, 10 steps, compiled: failed with a Metal GPU timeout.
- `256x448`, 5 frames, 2 steps, no compile, magenta background: completed in
  about 112 seconds, but magenta contaminated the sprite.
- `256x448`, 5 frames, 10 steps, no compile, dark background: completed in
  about 95 seconds and was the best Yume result.

**What worked:**
- MLX/Metal could run a local video model at very small settings.
- The character stayed somewhat recognizable in the best dark-background run.

**What didn't work:**
- Sprite motion was tiny to nonexistent.
- Background color drifted and flickered.
- Dark-background alpha recovery was not robust.
- Magenta-background extraction contaminated the sprite.
- No readable walk loop emerged.

**Verdict:** Viable as a local runtime smoke test, but not viable as a sprite
animation workflow.

---

## Approach 9: Wan2.2 Animate 14B GGUF via ComfyUI (May 2026)

**Idea:** Test a local model family designed for reference-character animation,
using WanAnimate's reference image + pose/background conditioning instead of
generic image-to-video prompting.

**Setup:**
- Installed a scratch ComfyUI runtime under `experiments/`.
- Added `ComfyUI-WanVideoWrapper`, `ComfyUI-GGUF`,
  `ComfyUI-VideoHelperSuite`, and `ComfyUI-KJNodes`.
- Downloaded `Kijai/WanVideo_comfy_GGUF`
  `Wan22Animate/Wan2_2_Animate_14B_Q4_K_M.gguf`.
- Downloaded WanVideoWrapper-compatible companion models from
  `Kijai/WanVideo_comfy`:
  - `umt5-xxl-enc-fp8_e4m3fn.safetensors`
  - `open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors`
  - `Wan2_1_VAE_bf16.safetensors`

**Important setup lesson:**
- The Comfy-Org `umt5_xxl_fp8_e4m3fn_scaled.safetensors` file is not compatible
  with WanVideoWrapper's T5 loader. The loader rejects `scaled_fp8`.

**Input harness:**
- Built a 5-frame `256x448` smoke test with:
  - dark reference image
  - alpha mask
  - sprite pose video
  - silhouette pose video
  - static dark background video
- The test intentionally used 5 frames because Wan wants `4n+1` frame counts.

**Runtime findings:**
- PyTorch 2.11.0 reported `mps_built=True` but `mps_available=False`.
- Creating an MPS tensor failed with:

```text
RuntimeError: The MPS backend is supported on MacOS 14.0+. Current OS version can be queried using `sw_vers`
```

- `sw_vers` reported macOS 26.3.1, so this appears to be a PyTorch/runtime gate
  problem rather than missing Apple hardware.
- Starting ComfyUI without `--cpu` then failed because it guessed CUDA:

```text
AssertionError: Torch not compiled with CUDA enabled
```

**CPU preflight:**
- ComfyUI with `--cpu` started and saw all model files.
- T5 text encoding completed and cached.
- CLIP image encoding failed in fp16 on CPU, then succeeded after switching the
  CLIP loader to fp32.
- The workflow reached `WanVideoAnimateEmbeds`, then sat in Wan VAE encoding
  for 13 minutes 37 seconds at `0/2` before sampling even began.

**Verdict:** The graph and model choice are plausible, but the current local
runtime is not usable. This is the candidate to revisit when we have GPU access
again.

---

## Overall Conclusions

1. **Approach 6 (grid canvas + platforms) remains the only usable workflow.**
   The combination of perspective grounding, proper Gemini config, and frame
   numbering solved the consistency + variation tension better than isolated
   frame generation or generic video.

2. **OpenAI image generation did not fix animation continuity.** Transparency
   support helps remove background fakery, but it does not make adjacent frames
   move correctly.

3. **Generic video models still fail the sprite standard.** They smooth,
   anti-alias, freeze, or drift instead of producing deliberate frame-to-frame
   pixel motion.

4. **Wan2.2 Animate is different enough to revisit.** It is built for
   reference-character animation and pose/background conditioning, but it needs
   a real accelerator path. CPU-only ComfyUI is not viable.

5. **Pause local video work until GPU access returns.** The next attempt should
   start with the WanAnimate GGUF workflow on CUDA or a fixed MPS runtime, not
   more prompt tuning.

6. **Remaining non-video opportunities:**
   - Higher-resolution base characters (256×256) for more detail per frame
   - Fine-tuning tile count per animation type automatically
   - Exploring whether skipping the cleanup pass and cropping platforms programmatically is more reliable

---

## Cost Reference

| Method | Cost/clip | Min duration | Quality for pixel art |
|--------|-----------|-------------|----------------------|
| Gemini sprite sheet | ~$0.01 | N/A (image) | Poor (inconsistent poses) |
| Wan 2.2 14B local | Free (compute) | 17 frames | Poor without LoRA |
| Wan 2.2 14B + LoRA | Free (compute) | 17 frames | Unknown (OOM on 36GB) |
| Yume 1.5 5B MLX | Free (compute) | 5 frames tested | Poor (mostly static, unstable background) |
| Wan2.2 Animate 14B GGUF | Free (compute) | 5 frames tested | Promising graph, blocked by GPU/runtime |
| Runway Gen-4 Turbo | $0.10 | 2 seconds | Mediocre |
| Runway Gen-4.5 | $0.24 | 2 seconds | Decent but not pixel-perfect |
| PixelLab | $12–50/mo | N/A (frames) | Good for static, limited animation |
| ComfyUI + AnimateDiff | Free (compute) | N/A (frames) | Paused until GPU access |
| Gemini frame interp. | ~$0.01/frame | N/A (frames) | Consistent but minimal motion |
| Gemini frame edit | ~$0.01/frame | N/A (frames) | Good motion but character drifts |
| OpenAI transparent image gen | Variable | N/A (frames) | Poor continuity despite transparency |
| **Gemini grid canvas** | **~$0.02-0.04/anim** | **N/A (grid)** | **Good — usable for game sprites** |
| Pixel Engine | ~$0.04/frame | N/A (frames) | Unknown (untested) |

## Files & Models (not committed)

- March 2026 local model experiments used uncommitted `models/` directories for
  Wan 2.2 and pixel-animation LoRA tests.
- May 2026 scratch experiments used uncommitted `experiments/` directories for
  OpenAI image tests, Yume MLX, and ComfyUI/WanAnimate.
- The May 2026 `experiments/` directory was deleted after the conclusions above
  were copied into this document. It contained about 21 GB of scratch runtimes,
  downloaded model files, and generated outputs.
