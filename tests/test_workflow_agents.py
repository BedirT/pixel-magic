"""Tests for AgentRuntime deterministic fallback behavior."""

from __future__ import annotations

import pytest

from pixel_magic.workflow.agents import AgentRuntime
from pixel_magic.workflow.models import (
    AssetType,
    DeterministicGate,
    FinalDecision,
    GenerationRequest,
    ValidationPacket,
)


@pytest.mark.asyncio
async def test_route_and_plan_fallback_without_api_key():
    runtime = AgentRuntime(model="gpt-5-mini", api_key="")
    request = GenerationRequest(
        asset_type=AssetType.ITEMS,
        objective="Potion + sword",
        style="16-bit",
        resolution="32x32",
        max_colors=16,
        parameters={"descriptions": ["potion", "sword"]},
    )

    plan, routed_by = await runtime.route_and_plan(request)
    assert routed_by == "deterministic_fallback"
    assert plan.asset_type == AssetType.ITEMS
    assert plan.expected_total_frames == 2


@pytest.mark.asyncio
async def test_final_validate_fallback_uses_gate_result():
    runtime = AgentRuntime(model="gpt-5-mini", api_key="")
    request = GenerationRequest(
        asset_type=AssetType.CUSTOM,
        objective="single icon",
        style="pixel",
        resolution="32x32",
        max_colors=8,
    )
    plan, _ = await runtime.route_and_plan(request)

    pass_packet = ValidationPacket(
        request_summary=request.model_dump(),
        artifact_manifest={"frame_count": 1},
        deterministic_gate=DeterministicGate(passed=True, checks=[], failure_reasons=[]),
        extraction_stats={},
    )
    fail_packet = ValidationPacket(
        request_summary=request.model_dump(),
        artifact_manifest={"frame_count": 1},
        deterministic_gate=DeterministicGate(
            passed=False,
            checks=[],
            failure_reasons=["qa failed"],
        ),
        extraction_stats={},
    )

    pass_decision = await runtime.final_validate(request, plan, pass_packet)
    fail_decision = await runtime.final_validate(request, plan, fail_packet)

    assert pass_decision.decision == FinalDecision.PASS
    assert fail_decision.decision == FinalDecision.FAIL


@pytest.mark.asyncio
async def test_plan_correction_fallback_returns_patch():
    runtime = AgentRuntime(model="gpt-5-mini", api_key="")
    request = GenerationRequest(
        asset_type=AssetType.CUSTOM,
        objective="single icon",
        style="pixel",
        resolution="32x32",
        max_colors=8,
    )
    plan, _ = await runtime.route_and_plan(request)
    packet = ValidationPacket(
        request_summary=request.model_dump(),
        artifact_manifest={"frame_count": 1},
        deterministic_gate=DeterministicGate(passed=True, checks=[], failure_reasons=[]),
        extraction_stats={},
    )

    patch = await runtime.plan_correction(
        request,
        plan,
        packet,
        retry_instructions="Increase contrast",
    )
    assert "Increase contrast" in patch.prompt_suffix
    assert patch.append_constraints
