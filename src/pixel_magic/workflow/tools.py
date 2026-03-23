"""Specialized agent tools and deterministic helpers for planning/validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents import RunContextWrapper, function_tool

from pixel_magic.generation.prompt_library._shared import (
    background_instruction,
    background_rule,
    framing_rules,
    perspective_rules,
)
from pixel_magic.generation.prompt_library.characters import (
    build_character_sheet_prompt,
)
from pixel_magic.generation.prompts import PromptBuilder
from pixel_magic.workflow.models import (
    AssetType,
    CorrectionPatch,
    DeterministicGate,
    ExecutionPlan,
    GenerationRequest,
    PlannedPrompt,
    ValidationPacket,
)


@dataclass
class AgentToolContext:
    """Context shared across planner/correction/validator agents."""

    request: GenerationRequest
    plan: ExecutionPlan | None = None
    validation_packet: ValidationPacket | None = None
    provider: str = "openai"
    chromakey_color: str = "green"


def _direction_names(direction_mode: int) -> list[str]:
    if direction_mode == 8:
        return ["south", "south_east", "east", "north_east", "north"]
    return ["south_east", "north_east"]


def _normalize_animation_specs(request: GenerationRequest) -> list[dict[str, Any]]:
    raw = request.parameters.get("animations")
    if isinstance(raw, dict):
        out: list[dict[str, Any]] = []
        for name, val in raw.items():
            if isinstance(val, str):
                out.append(
                    {
                        "name": name,
                        "frame_count": 4,
                        "description": val,
                    }
                )
                continue
            if isinstance(val, dict):
                out.append(
                    {
                        "name": name,
                        "frame_count": int(val.get("frame_count", 4)),
                        "description": str(val.get("description", name)),
                    }
                )
        if out:
            return out
    return [
        {"name": "idle", "frame_count": 4, "description": "breathing idle stance"},
        {"name": "walk", "frame_count": 6, "description": "walk cycle"},
    ]


def _effect_phase_hints(frame_count: int) -> list[tuple[str, str]]:
    """Build phase descriptions and occupancy hints for effect frame sequences."""
    if frame_count <= 1:
        return [("a readable top-down burst at peak intensity", "45-70%")]

    hints: list[tuple[str, str]] = []
    for index in range(frame_count):
        if index == 0:
            hints.append(("a compact orb, spark cluster, or rune burst just beginning to ignite", "20-35%"))
        elif index == frame_count - 1:
            hints.append(("a dissipating residue with broken fragments and trailing embers", "30-50%"))
        elif index <= frame_count // 2:
            hints.append(("the burst expanding outward with strong directional motion and a clear focal core", "45-70%"))
        else:
            hints.append(("the effect cooling and breaking apart while staying clearly readable", "40-60%"))
    return hints


# Lazy singleton for prompt builder
_prompt_builder: PromptBuilder | None = None


def _get_prompt_builder() -> PromptBuilder:
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder


def _template_vars(
    provider: str, chromakey_color: str, request: GenerationRequest,
) -> dict[str, str]:
    """Common template variables for all asset types."""
    return {
        "background_instruction": background_instruction(provider, chromakey_color),
        "background_rule": background_rule(provider, chromakey_color),
        "style": request.style,
        "resolution": request.resolution,
        "max_colors": str(request.max_colors),
        "palette_hint": request.parameters.get("palette_hint", ""),
    }


def build_plan_from_request(
    request: GenerationRequest,
    provider: str = "openai",
    chromakey_color: str = "green",
) -> ExecutionPlan:
    """Build execution plan using rich prompt templates from prompt_library."""
    prompts: list[PlannedPrompt] = []
    expected_total = 0
    pb = _get_prompt_builder()
    base_vars = _template_vars(provider, chromakey_color, request)

    if request.asset_type == AssetType.CHARACTER:
        extension_mode = bool(request.parameters.get("extension_mode", False))
        external_reference_paths = request.parameters.get("external_reference_paths", [])
        if not isinstance(external_reference_paths, list):
            external_reference_paths = []

        if extension_mode:
            # Extension mode: generate animation strips using reference image
            direction_mode = int(request.parameters.get("direction_mode", 4))
            dirs = _direction_names(direction_mode)
            animations = _normalize_animation_specs(request)
            tpl_name = "character_custom_animation"
            for anim in animations:
                for direction in dirs:
                    prompt_text = pb.render(
                        tpl_name,
                        **base_vars,
                        character_description=request.objective,
                        animation_name=anim["name"],
                        animation_description=anim["description"],
                        frame_count=str(anim["frame_count"]),
                        direction=direction,
                    )
                    prompts.append(
                        PlannedPrompt(
                            key=f"{anim['name']}_{direction}",
                            prompt=prompt_text,
                            expected_frames=int(anim["frame_count"]),
                            layout="horizontal_strip",
                            external_reference_paths=[
                                str(path) for path in external_reference_paths
                            ],
                        )
                    )
                    expected_total += int(anim["frame_count"])
            return ExecutionPlan(
                asset_type=request.asset_type,
                expected_total_frames=max(expected_total, 1),
                planned_prompts=prompts,
                qa_min_score=0.7,
                notes="Extension-mode plan using prompt templates",
            )

        # Multi-view reference sheet: one generation call produces all views
        direction_mode = int(request.parameters.get("direction_mode", 4))
        view_count = 2 if direction_mode == 4 else 5
        prompt_text = build_character_sheet_prompt(
            character_description=request.objective,
            direction_mode=direction_mode,
            style=request.style,
            resolution=request.resolution,
            max_colors=request.max_colors,
            palette_hint=request.parameters.get("palette_hint", ""),
            provider=provider,
            chromakey_color=chromakey_color,
        )
        prompts.append(
            PlannedPrompt(
                key="character_sheet",
                prompt=prompt_text,
                expected_frames=view_count,
                layout="reference_sheet",
            )
        )
        expected_total += view_count

    elif request.asset_type == AssetType.TILESET:
        tile_types = request.parameters.get("tile_types", [])
        if not isinstance(tile_types, list):
            tile_types = [str(tile_types)]
        count = max(1, len(tile_types))
        prompt_text = pb.render(
            "tileset_ground",
            **base_vars,
            biome=request.objective,
            tile_types=", ".join(str(t) for t in tile_types),
            count=str(count),
            tile_width=str(request.parameters.get("tile_width", 64)),
            tile_height=str(request.parameters.get("tile_height", 32)),
        )
        prompts.append(
            PlannedPrompt(
                key="tileset_batch",
                prompt=prompt_text,
                expected_frames=count,
                layout="horizontal_strip",
            )
        )
        expected_total += count

    elif request.asset_type == AssetType.ITEMS:
        descriptions = request.parameters.get("descriptions", [])
        if not isinstance(descriptions, list):
            descriptions = [str(descriptions)]
        count = max(1, len(descriptions))
        prompt_text = pb.render(
            "item_icons_batch",
            **base_vars,
            item_descriptions=", ".join(str(d) for d in descriptions),
            count=str(count),
            view=request.parameters.get("view", "front-facing icon"),
        )
        prompts.append(
            PlannedPrompt(
                key="items_batch",
                prompt=prompt_text,
                expected_frames=count,
                layout="horizontal_strip",
            )
        )
        expected_total += count

    elif request.asset_type == AssetType.EFFECT:
        frame_count = int(request.parameters.get("frame_count", request.expected_frames))
        frame_count = max(1, frame_count)
        perspective = request.parameters.get("perspective", "isometric")
        phase_hints = _effect_phase_hints(frame_count)
        previous_key: str | None = None
        for index, (phase_description, occupancy_hint) in enumerate(phase_hints):
            key = f"effect_{index:03d}"
            prompt_text = pb.render(
                "effect_single_frame",
                **base_vars,
                effect_description=request.objective,
                frame_index=str(index + 1),
                frame_count=str(frame_count),
                phase_description=phase_description,
                occupancy_hint=occupancy_hint,
                color_emphasis=request.parameters.get("color_emphasis", ""),
                perspective_rules=perspective_rules(perspective),
            )
            prompts.append(
                PlannedPrompt(
                    key=key,
                    prompt=prompt_text,
                    expected_frames=1,
                    layout="horizontal_strip",
                    reference_key=previous_key,
                )
            )
            previous_key = key
            expected_total += 1

    elif request.asset_type == AssetType.UI:
        descriptions = request.parameters.get("descriptions", [])
        if not isinstance(descriptions, list):
            descriptions = [str(descriptions)]
        if not descriptions:
            descriptions = ["UI element"]
        for index, description in enumerate(descriptions):
            prompt_text = pb.render(
                "ui_single",
                **base_vars,
                element_description=str(description),
            )
            prompts.append(
                PlannedPrompt(
                    key=f"ui_{index:03d}",
                    prompt=prompt_text,
                    expected_frames=1,
                    layout="horizontal_strip",
                )
            )
            expected_total += 1

    else:
        perspective = request.parameters.get("perspective", "isometric")
        prompt_text = pb.render(
            "custom_generation",
            **base_vars,
            description=request.objective,
            perspective_rules=perspective_rules(perspective),
        ) if pb.get("custom_generation") else (
            f"{request.objective}. Style: {request.style}. "
            f"Resolution: {request.resolution}. Max colors: {request.max_colors}."
        )
        prompts.append(
            PlannedPrompt(
                key="custom",
                prompt=prompt_text,
                expected_frames=request.expected_frames,
                layout=request.layout,
            )
        )
        expected_total += request.expected_frames

    return ExecutionPlan(
        asset_type=request.asset_type,
        expected_total_frames=max(expected_total, 1),
        planned_prompts=prompts,
        qa_min_score=0.7,
        notes="Plan using prompt templates",
    )


def apply_patch_to_plan(plan: ExecutionPlan, patch: CorrectionPatch) -> ExecutionPlan:
    """Apply correction patch instructions to a plan deterministically."""
    prompts: list[PlannedPrompt] = []
    suffix_parts = []
    if patch.prompt_suffix.strip():
        suffix_parts.append(patch.prompt_suffix.strip())
    if patch.append_constraints:
        suffix_parts.extend(c for c in patch.append_constraints if c.strip())
    suffix = ""
    if suffix_parts:
        suffix = "\nCorrections:\n- " + "\n- ".join(suffix_parts)

    for planned in plan.planned_prompts:
        expected_frames = planned.expected_frames
        if planned.key in patch.expected_frame_overrides:
            expected_frames = max(1, patch.expected_frame_overrides[planned.key])

        prompts.append(
            PlannedPrompt(
                key=planned.key,
                prompt=planned.prompt + suffix,
                expected_frames=expected_frames,
                layout=planned.layout,
                reference_key=planned.reference_key,
                external_reference_paths=list(planned.external_reference_paths),
            )
        )

    total = sum(p.expected_frames for p in prompts)
    return ExecutionPlan(
        asset_type=plan.asset_type,
        expected_total_frames=max(total, 1),
        planned_prompts=prompts,
        qa_min_score=plan.qa_min_score,
        notes=(plan.notes + f" | patched: {patch.notes}").strip(),
    )


def default_final_decision(packet: ValidationPacket) -> dict[str, Any]:
    """Deterministic fallback for final validation when LLM runtime is unavailable."""
    gate = packet.deterministic_gate
    if gate.passed:
        return {
            "decision": "pass",
            "overall_score": 0.85,
            "critical_issues": [],
            "retry_instructions": "",
            "confidence": 0.8,
            "notes": "Deterministic fallback validator accepted result.",
        }
    return {
        "decision": "fail",
        "overall_score": 0.2,
        "critical_issues": gate.failure_reasons or ["Deterministic QA failed"],
        "retry_instructions": "",
        "confidence": 0.9,
        "notes": "Deterministic fallback validator rejected result.",
    }


@function_tool
async def build_character_prompt_pack(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Build the default character prompt pack from the request."""
    plan = build_plan_from_request(ctx.context.request, ctx.context.provider, ctx.context.chromakey_color)
    return {
        "expected_total_frames": plan.expected_total_frames,
        "prompt_keys": [p.key for p in plan.planned_prompts],
    }


@function_tool
async def validate_character_constraints(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Validate basic character request constraints before planning."""
    req = ctx.context.request
    direction_mode = int(req.parameters.get("direction_mode", 4))
    return {
        "ok": direction_mode in (4, 8),
        "direction_mode": direction_mode,
        "resolution": req.resolution,
        "max_colors": req.max_colors,
    }


@function_tool
async def estimate_character_budget(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Estimate character generation cost footprint for planning."""
    plan = build_plan_from_request(ctx.context.request, ctx.context.provider, ctx.context.chromakey_color)
    calls = len(plan.planned_prompts)
    return {
        "estimated_generation_calls": calls,
        "estimated_seconds": calls * 12,
    }


@function_tool
async def build_tileset_prompt_pack(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Build default tileset prompt pack."""
    plan = build_plan_from_request(ctx.context.request, ctx.context.provider, ctx.context.chromakey_color)
    return {
        "expected_total_frames": plan.expected_total_frames,
        "prompt_keys": [p.key for p in plan.planned_prompts],
    }


@function_tool
async def validate_tileset_constraints(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Validate tileset-specific request constraints."""
    req = ctx.context.request
    tiles = req.parameters.get("tile_types", [])
    return {
        "ok": isinstance(tiles, list) and len(tiles) > 0,
        "tile_type_count": len(tiles) if isinstance(tiles, list) else 0,
    }


@function_tool
async def estimate_tileset_budget(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Estimate tileset planning budget."""
    plan = build_plan_from_request(ctx.context.request, ctx.context.provider, ctx.context.chromakey_color)
    return {"estimated_generation_calls": len(plan.planned_prompts), "estimated_seconds": 20}


@function_tool
async def build_items_prompt_pack(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Build default items prompt pack."""
    plan = build_plan_from_request(ctx.context.request, ctx.context.provider, ctx.context.chromakey_color)
    return {
        "expected_total_frames": plan.expected_total_frames,
        "prompt_keys": [p.key for p in plan.planned_prompts],
    }


@function_tool
async def validate_items_constraints(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Validate item request constraints."""
    req = ctx.context.request
    items = req.parameters.get("descriptions", [])
    return {
        "ok": isinstance(items, list) and len(items) > 0,
        "item_count": len(items) if isinstance(items, list) else 0,
    }


@function_tool
async def estimate_items_budget(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Estimate items generation budget."""
    plan = build_plan_from_request(ctx.context.request, ctx.context.provider, ctx.context.chromakey_color)
    return {"estimated_generation_calls": len(plan.planned_prompts), "estimated_seconds": 15}


@function_tool
async def build_effect_prompt_pack(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Build default effect prompt pack."""
    plan = build_plan_from_request(ctx.context.request, ctx.context.provider, ctx.context.chromakey_color)
    return {
        "expected_total_frames": plan.expected_total_frames,
        "prompt_keys": [p.key for p in plan.planned_prompts],
    }


@function_tool
async def validate_effect_constraints(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Validate effect request constraints."""
    req = ctx.context.request
    frame_count = int(req.parameters.get("frame_count", req.expected_frames))
    return {"ok": frame_count >= 1, "frame_count": frame_count}


@function_tool
async def estimate_effect_budget(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Estimate effect generation budget."""
    plan = build_plan_from_request(ctx.context.request, ctx.context.provider, ctx.context.chromakey_color)
    return {"estimated_generation_calls": len(plan.planned_prompts), "estimated_seconds": 12}


@function_tool
async def build_ui_prompt_pack(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Build default UI prompt pack."""
    plan = build_plan_from_request(ctx.context.request, ctx.context.provider, ctx.context.chromakey_color)
    return {
        "expected_total_frames": plan.expected_total_frames,
        "prompt_keys": [p.key for p in plan.planned_prompts],
    }


@function_tool
async def validate_ui_constraints(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Validate UI request constraints."""
    req = ctx.context.request
    desc = req.parameters.get("descriptions", [])
    return {
        "ok": isinstance(desc, list) and len(desc) > 0,
        "element_count": len(desc) if isinstance(desc, list) else 0,
    }


@function_tool
async def estimate_ui_budget(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Estimate UI generation budget."""
    plan = build_plan_from_request(ctx.context.request, ctx.context.provider, ctx.context.chromakey_color)
    return {"estimated_generation_calls": len(plan.planned_prompts), "estimated_seconds": 14}


@function_tool
async def compile_validation_packet(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Provide the validation packet to the final validator agent."""
    packet = ctx.context.validation_packet
    if packet is None:
        return {"ok": False, "reason": "validation_packet_missing"}
    return packet.model_dump()


@function_tool
async def score_artifact_set(
    ctx: RunContextWrapper[AgentToolContext],
) -> dict[str, Any]:
    """Compute a deterministic baseline score from QA metrics."""
    packet = ctx.context.validation_packet
    if packet is None:
        return {"overall_score": 0.0, "issues": ["validation_packet_missing"]}

    gate = packet.deterministic_gate
    failed = sum(1 for c in gate.checks if not c.get("passed", False))
    total = max(1, len(gate.checks))
    score = max(0.0, 1.0 - (failed / total))
    return {"overall_score": round(score, 3), "issues": gate.failure_reasons}


@function_tool
async def apply_correction_patch(
    ctx: RunContextWrapper[AgentToolContext],
    retry_instructions: str,
) -> dict[str, Any]:
    """Build a conservative correction patch from validator retry instructions."""
    _ = ctx
    suffix = retry_instructions.strip()
    if not suffix:
        suffix = "Improve frame separation, palette consistency, and subject clarity."
    patch = CorrectionPatch(
        prompt_suffix=suffix,
        append_constraints=["Preserve subject identity across all frames."],
        notes="Auto patch from retry instructions",
    )
    return patch.model_dump()


def planner_tools_for_asset(asset_type: AssetType) -> list[Any]:
    """Return planner-tool set for an asset type."""
    if asset_type == AssetType.CHARACTER:
        return [
            build_character_prompt_pack,
            validate_character_constraints,
            estimate_character_budget,
        ]
    if asset_type == AssetType.TILESET:
        return [build_tileset_prompt_pack, validate_tileset_constraints, estimate_tileset_budget]
    if asset_type == AssetType.ITEMS:
        return [build_items_prompt_pack, validate_items_constraints, estimate_items_budget]
    if asset_type == AssetType.EFFECT:
        return [build_effect_prompt_pack, validate_effect_constraints, estimate_effect_budget]
    if asset_type == AssetType.UI:
        return [build_ui_prompt_pack, validate_ui_constraints, estimate_ui_budget]
    return []


def summarize_gate(report: DeterministicGate) -> dict[str, Any]:
    """Compact deterministic gate report for observability."""
    return {
        "passed": report.passed,
        "failed_count": len(report.failure_reasons),
    }
