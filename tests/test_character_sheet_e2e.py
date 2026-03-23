"""End-to-end tests for the JSON multi-view character sheet pipeline."""

from __future__ import annotations

import asyncio
import json

from PIL import Image

from pixel_magic.config import Settings
from pixel_magic.generation.prompt_library.characters import build_character_sheet_prompt
from pixel_magic.providers.base import GenerationResult
from pixel_magic.workflow.executor import WorkflowExecutor
from pixel_magic.workflow.models import (
    AssetType,
    CorrectionPatch,
    ExecutionPlan,
    FinalDecision,
    FinalValidationDecision,
    GenerationRequest,
    JobStatus,
    PlannedPrompt,
)
from pixel_magic.workflow.tools import build_plan_from_request


# ── Helpers ───────────────────────────────────────────────────────────


def _make_multiview_sheet(
    view_count: int,
    sprite_size: tuple[int, int] = (48, 48),
    gap: int = 30,
) -> Image.Image:
    """Build a synthetic multi-view reference sheet on transparent background.

    Creates `view_count` colored rectangles spaced horizontally — simulates
    what the image model would return for a character reference sheet.
    """
    total_w = view_count * sprite_size[0] + (view_count - 1) * gap
    total_h = sprite_size[1] + 20  # slight vertical padding
    img = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))

    colors = [
        (200, 60, 60, 255),
        (60, 60, 200, 255),
        (60, 200, 60, 255),
        (200, 200, 60, 255),
        (200, 60, 200, 255),
    ]

    for i in range(view_count):
        x_start = i * (sprite_size[0] + gap)
        y_start = 10  # center vertically
        color = colors[i % len(colors)]
        for y in range(y_start, y_start + sprite_size[1]):
            for x in range(x_start, x_start + sprite_size[0]):
                img.putpixel((x, y), color)

    return img


class StubProvider:
    provider_name = "stub"
    model_name = "stub-model"

    def __init__(self, image: Image.Image):
        self._image = image
        self.calls: list[str] = []

    async def generate(self, prompt: str, references=None) -> GenerationResult:
        self.calls.append(prompt)
        return GenerationResult(
            image=self._image,
            prompt_used=prompt,
            model_used=self.model_name,
            metadata={},
        )


class StubAgents:
    def __init__(self, plan: ExecutionPlan):
        self.plan = plan

    async def route_and_plan(self, request):
        return self.plan, "StubPlanner"

    async def final_validate(self, request, plan, packet):
        return FinalValidationDecision(
            decision=FinalDecision.PASS,
            overall_score=0.9,
            critical_issues=[],
            retry_instructions="",
            confidence=0.8,
            notes="auto pass",
        )

    async def plan_correction(self, request, plan, packet, retry_instructions):
        return CorrectionPatch(
            prompt_suffix=retry_instructions,
            append_constraints=[],
            notes="stub correction",
        )


# ── JSON Prompt Structure Tests ───────────────────────────────────────


def test_json_prompt_4dir_structure():
    prompt_str = build_character_sheet_prompt(
        character_description="A young ranger with a green cloak and wooden bow",
        direction_mode=4,
        resolution="64x64",
        max_colors=16,
    )
    data = json.loads(prompt_str)

    assert data["purpose"] == "character_sprite_reference_sheet"
    assert data["image_type"] == "pixel_art"
    assert data["style"] == "isometric"
    assert len(data["views"]) == 2
    assert data["views"][0]["facing"].startswith("front-left")
    assert data["views"][1]["facing"].startswith("back-right")
    assert data["character"]["description"] == "A young ranger with a green cloak and wooden bow"
    assert data["art_details"]["max_colors"] == 16
    assert data["art_details"]["target_resolution_per_view"] == "64x64"
    assert "transparent" in data["background"]["type"]


def test_json_prompt_8dir_structure():
    prompt_str = build_character_sheet_prompt(
        character_description="An armored knight",
        direction_mode=8,
        resolution="64x64",
        max_colors=24,
    )
    data = json.loads(prompt_str)

    assert len(data["views"]) == 5
    facings = [v["facing"] for v in data["views"]]
    assert "back (north)" in facings[0]
    assert "front (south)" in facings[-1]


def test_json_prompt_includes_palette_hint():
    prompt_str = build_character_sheet_prompt(
        character_description="A fire mage",
        palette_hint="warm reds, oranges, and deep purples",
    )
    data = json.loads(prompt_str)
    assert data["color_palette_hint"] == "warm reds, oranges, and deep purples"


def test_json_prompt_omits_palette_hint_when_empty():
    prompt_str = build_character_sheet_prompt(
        character_description="A fire mage",
        palette_hint="",
    )
    data = json.loads(prompt_str)
    assert "color_palette_hint" not in data


def test_json_prompt_gemini_provider_uses_chromakey():
    prompt_str = build_character_sheet_prompt(
        character_description="A thief",
        provider="gemini",
        chromakey_color="green",
    )
    data = json.loads(prompt_str)
    assert "#00FF00" in data["background"]["rule"] or "green" in data["background"]["rule"]


# ── Plan Building Tests ───────────────────────────────────────────────


def test_plan_4dir_single_sheet_prompt():
    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        objective="A samurai with katana",
        style="16-bit RPG",
        resolution="64x64",
        max_colors=16,
        parameters={"direction_mode": 4},
    )
    plan = build_plan_from_request(request)

    assert len(plan.planned_prompts) == 1
    assert plan.expected_total_frames == 2
    sheet = plan.planned_prompts[0]
    assert sheet.key == "character_sheet"
    assert sheet.layout == "reference_sheet"
    assert sheet.expected_frames == 2

    # Verify prompt is valid JSON with correct view count
    data = json.loads(sheet.prompt)
    assert len(data["views"]) == 2


def test_plan_8dir_single_sheet_prompt():
    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        objective="A wizard with staff",
        style="16-bit RPG",
        resolution="64x64",
        max_colors=16,
        parameters={"direction_mode": 8},
    )
    plan = build_plan_from_request(request)

    assert len(plan.planned_prompts) == 1
    assert plan.expected_total_frames == 5
    sheet = plan.planned_prompts[0]
    assert sheet.expected_frames == 5

    data = json.loads(sheet.prompt)
    assert len(data["views"]) == 5


def test_plan_extension_mode_unchanged():
    """Extension mode should still use per-direction animation strips, not JSON sheets."""
    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        objective="Extend hero",
        style="16-bit RPG",
        resolution="64x64",
        max_colors=16,
        parameters={
            "extension_mode": True,
            "direction_mode": 4,
            "external_reference_paths": ["/tmp/ref.png"],
            "animations": {"idle": {"frame_count": 4, "description": "idle stance"}},
        },
    )
    plan = build_plan_from_request(request)

    # Extension mode: 1 anim × 2 dirs = 2 prompts, each horizontal_strip
    assert len(plan.planned_prompts) == 2
    assert all(p.layout == "horizontal_strip" for p in plan.planned_prompts)


# ── Full Pipeline E2E Tests ───────────────────────────────────────────


def test_e2e_character_4dir_pipeline(tmp_path):
    """Full pipeline: plan → generate → extract → QA → export for 4-dir character."""
    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        name="test_hero",
        objective="A young adventurer with a backpack and red boots",
        style="16-bit SNES RPG style",
        resolution="64x64",
        max_colors=16,
        parameters={"direction_mode": 4},
    )

    plan = build_plan_from_request(request)
    sheet_image = _make_multiview_sheet(view_count=2, sprite_size=(48, 48))

    settings = Settings(output_dir=str(tmp_path))
    provider = StubProvider(sheet_image)
    agents = StubAgents(plan)
    executor = WorkflowExecutor(settings=settings, provider=provider, agents=agents)

    result = asyncio.get_event_loop().run_until_complete(executor.run(request))

    assert result.status == JobStatus.SUCCESS, f"Failed: {result.errors}"

    # Provider should have been called exactly once (single sheet)
    assert len(provider.calls) == 1

    # The prompt sent to the provider should be valid JSON
    sent_prompt = provider.calls[0]
    data = json.loads(sent_prompt)
    assert data["purpose"] == "character_sprite_reference_sheet"

    # Should have extracted 2 frames
    assert result.artifacts is not None
    assert result.artifacts.generated_total_frames >= 2


def test_e2e_character_8dir_pipeline(tmp_path):
    """Full pipeline for 8-dir character (5 views)."""
    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        name="test_knight",
        objective="A heavily armored knight with a tower shield and broadsword",
        style="16-bit SNES RPG style",
        resolution="64x64",
        max_colors=16,
        parameters={"direction_mode": 8},
    )

    plan = build_plan_from_request(request)
    sheet_image = _make_multiview_sheet(view_count=5, sprite_size=(48, 48))

    settings = Settings(output_dir=str(tmp_path))
    provider = StubProvider(sheet_image)
    agents = StubAgents(plan)
    executor = WorkflowExecutor(settings=settings, provider=provider, agents=agents)

    result = asyncio.get_event_loop().run_until_complete(executor.run(request))

    assert result.status == JobStatus.SUCCESS, f"Failed: {result.errors}"
    assert len(provider.calls) == 1
    assert result.artifacts is not None
    assert result.artifacts.generated_total_frames >= 5


def test_e2e_diverse_character_prompts():
    """Verify JSON prompt generation works for various character descriptions."""
    prompts = [
        ("A child with a messy hair, blue shirt, red shorts, and an oversized backpack", 4),
        ("A tall elven archer with silver hair and a longbow", 4),
        ("A dwarf blacksmith with soot-covered apron and a massive hammer", 8),
        ("A ninja with dark wrappings and twin daggers, crouched stance", 4),
        ("A robot companion with glowing blue eyes and antenna", 8),
    ]

    for description, direction_mode in prompts:
        request = GenerationRequest(
            asset_type=AssetType.CHARACTER,
            objective=description,
            style="16-bit SNES RPG style",
            resolution="64x64",
            max_colors=16,
            parameters={"direction_mode": direction_mode},
        )
        plan = build_plan_from_request(request)

        assert len(plan.planned_prompts) == 1, f"Failed for: {description}"
        sheet = plan.planned_prompts[0]

        # Prompt must be valid JSON
        data = json.loads(sheet.prompt)
        assert data["character"]["description"] == description
        expected_views = 2 if direction_mode == 4 else 5
        assert len(data["views"]) == expected_views, f"Wrong view count for: {description}"
        assert sheet.expected_frames == expected_views
