"""Tests for deterministic workflow tools and exporter helpers."""

from __future__ import annotations

import json

from PIL import Image

from pixel_magic.workflow.exporter import export_assets
from pixel_magic.workflow.models import (
    AssetType,
    CorrectionPatch,
    DeterministicGate,
    GenerationRequest,
    ValidationPacket,
)
from pixel_magic.workflow.tools import (
    apply_patch_to_plan,
    build_plan_from_request,
    default_final_decision,
)


def _make_frame(size: tuple[int, int] = (16, 16), alpha: int = 255) -> Image.Image:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    for y in range(4, 12):
        for x in range(4, 12):
            image.putpixel((x, y), (255, 20, 20, alpha))
    return image


def test_build_plan_character_counts_frames():
    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        objective="Ranger with cloak",
        style="16-bit RPG",
        resolution="64x64",
        max_colors=16,
        parameters={
            "direction_mode": 4,
            "animations": {
                "idle": {"frame_count": 2, "description": "idle pose"},
            },
        },
    )

    plan = build_plan_from_request(request)
    assert plan.asset_type == AssetType.CHARACTER
    assert plan.expected_total_frames == 6
    assert [p.key for p in plan.planned_prompts] == [
        "base_south_east",
        "base_north_east",
        "idle_south_east",
        "idle_north_east",
    ]


def test_build_plan_character_extension_mode_uses_external_reference():
    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        objective="Extend existing character with fishing animation",
        style="16-bit RPG",
        resolution="64x64",
        max_colors=16,
        parameters={
            "extension_mode": True,
            "direction_mode": 4,
            "external_reference_paths": ["/tmp/ref.png"],
            "animations": {
                "fishing": {"frame_count": 4, "description": "fishing loop"},
            },
        },
    )
    plan = build_plan_from_request(request)
    assert plan.expected_total_frames == 8
    assert len(plan.planned_prompts) == 2
    assert all(p.reference_key is None for p in plan.planned_prompts)
    assert all(p.external_reference_paths == ["/tmp/ref.png"] for p in plan.planned_prompts)


def test_apply_patch_to_plan_updates_prompts_and_totals():
    request = GenerationRequest(
        asset_type=AssetType.ITEMS,
        objective="Potion and key set",
        style="16-bit",
        resolution="32x32",
        max_colors=16,
        expected_frames=2,
        parameters={"descriptions": ["potion", "key"]},
    )
    plan = build_plan_from_request(request)
    patch = CorrectionPatch(
        prompt_suffix="Increase contrast.",
        append_constraints=["Keep outlines one-pixel thick."],
        expected_frame_overrides={"items_batch": 3},
        notes="manual correction",
    )

    patched = apply_patch_to_plan(plan, patch)
    assert patched.expected_total_frames == 3
    assert patched.planned_prompts[0].expected_frames == 3
    assert "Increase contrast." in patched.planned_prompts[0].prompt
    assert "Keep outlines one-pixel thick." in patched.planned_prompts[0].prompt
    assert "manual correction" in patched.notes


def test_default_final_decision_pass_and_fail():
    pass_packet = ValidationPacket(
        request_summary={"asset": "x"},
        artifact_manifest={"frames": 1},
        deterministic_gate=DeterministicGate(passed=True, checks=[], failure_reasons=[]),
        extraction_stats={"groups": {}},
    )
    fail_packet = ValidationPacket(
        request_summary={"asset": "x"},
        artifact_manifest={"frames": 1},
        deterministic_gate=DeterministicGate(
            passed=False,
            checks=[],
            failure_reasons=["alpha_compliance failed"],
        ),
        extraction_stats={"groups": {}},
    )

    pass_decision = default_final_decision(pass_packet)
    fail_decision = default_final_decision(fail_packet)

    assert pass_decision["decision"] == "pass"
    assert fail_decision["decision"] == "fail"
    assert fail_decision["critical_issues"] == ["alpha_compliance failed"]


def test_export_assets_writes_expected_files(tmp_path):
    raw = _make_frame()
    groups = {"idle": [_make_frame(), _make_frame()]}
    manifest = export_assets(
        groups=groups,
        raw_images={"raw_0": raw},
        output_root=tmp_path,
        name="hero test",
    )

    assert manifest.total_frames == 2
    assert len(manifest.raw_paths) == 1
    assert len(manifest.frame_paths["idle"]) == 2
    assert (tmp_path / "hero_test" / "hero_test_atlas.png").exists()
    assert (tmp_path / "hero_test" / "hero_test_metadata.json").exists()

    metadata = json.loads((tmp_path / "hero_test" / "hero_test_metadata.json").read_text())
    assert metadata["total_frames"] == 2
