"""State-machine tests for the rewritten workflow executor."""

from __future__ import annotations

import asyncio

import pytest
from PIL import Image

from pixel_magic.config import Settings
from pixel_magic.providers.base import GenerationResult
from pixel_magic.workflow.executor import WorkflowExecutor
from pixel_magic.workflow.models import (
    AssetType,
    CorrectionPatch,
    ErrorCode,
    ExecutionPlan,
    FinalDecision,
    FinalValidationDecision,
    GenerationRequest,
    JobStatus,
    PlannedPrompt,
    StageName,
)


def _binary_sprite(size: tuple[int, int] = (16, 16)) -> Image.Image:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    for y in range(4, 12):
        for x in range(4, 12):
            image.putpixel((x, y), (255, 0, 0, 255))
    return image


def _semi_alpha_sprite(size: tuple[int, int] = (16, 16)) -> Image.Image:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    for y in range(size[1]):
        for x in range(size[0]):
            image.putpixel((x, y), (255, 0, 0, 120))
    return image


def _separator_strip(
    frame_count: int,
    frame_size: tuple[int, int] = (32, 32),
) -> Image.Image:
    width = frame_count * frame_size[0] + max(0, frame_count - 1)
    height = frame_size[1]
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for index in range(frame_count):
        base_x = index * (frame_size[0] + 1)
        for y in range(frame_size[1]):
            for x in range(frame_size[0]):
                image.putpixel((base_x + x, y), (255, 0, 0, 255))
        if index < frame_count - 1:
            separator_x = base_x + frame_size[0]
            for y in range(frame_size[1]):
                image.putpixel((separator_x, y), (255, 0, 255, 255))
    return image


class StubProviderAdapter:
    provider_name = "stub"
    model_name = "stub-model"

    def __init__(self, images: list[Image.Image], delay_s: float = 0.0):
        self._images = images
        self._delay_s = delay_s
        self.calls: list[str] = []
        self.reference_counts: list[int] = []

    async def generate(self, prompt: str, references=None) -> GenerationResult:
        self.calls.append(prompt)
        self.reference_counts.append(len(references or []))
        if self._delay_s > 0:
            await asyncio.sleep(self._delay_s)
        idx = min(len(self.calls) - 1, len(self._images) - 1)
        return GenerationResult(
            image=self._images[idx],
            prompt_used=prompt,
            model_used=self.model_name,
            metadata={"idx": idx},
        )


class StubAgentRuntime:
    def __init__(self, plan: ExecutionPlan, decisions: list[FinalValidationDecision]):
        self.plan = plan
        self.decisions = decisions
        self.final_validate_calls = 0
        self.correction_calls = 0
        self.last_packet = None

    async def route_and_plan(self, request: GenerationRequest) -> tuple[ExecutionPlan, str]:
        _ = request
        return self.plan, "StubPlanner"

    async def final_validate(self, request, plan, packet) -> FinalValidationDecision:
        _ = request, plan
        self.final_validate_calls += 1
        self.last_packet = packet
        if self.decisions:
            return self.decisions.pop(0)
        return FinalValidationDecision(
            decision=FinalDecision.PASS,
            overall_score=0.9,
            critical_issues=[],
            retry_instructions="",
            confidence=0.8,
            notes="default pass",
        )

    async def plan_correction(self, request, plan, packet, retry_instructions) -> CorrectionPatch:
        _ = request, plan, packet
        self.correction_calls += 1
        return CorrectionPatch(
            prompt_suffix=retry_instructions,
            append_constraints=["Increase contrast"],
            max_colors_override=8,
            notes="stub correction",
        )


def _custom_plan(expected_frames: int = 1) -> ExecutionPlan:
    return ExecutionPlan(
        asset_type=AssetType.CUSTOM,
        expected_total_frames=expected_frames,
        planned_prompts=[
            PlannedPrompt(
                key="main",
                prompt="single sprite",
                expected_frames=expected_frames,
                layout="horizontal_strip",
            )
        ],
        qa_min_score=0.7,
        notes="stub plan",
    )


def _request(**kwargs) -> GenerationRequest:
    payload = {
        "asset_type": AssetType.CUSTOM,
        "name": "test_asset",
        "objective": "create one sprite",
        "style": "pixel",
        "resolution": "16x16",
        "max_colors": 16,
        "expected_frames": 1,
        "layout": "horizontal_strip",
        "parameters": {},
    }
    payload.update(kwargs)
    return GenerationRequest(**payload)


def _pass_decision() -> FinalValidationDecision:
    return FinalValidationDecision(
        decision=FinalDecision.PASS,
        overall_score=0.9,
        critical_issues=[],
        retry_instructions="",
        confidence=0.9,
        notes="ok",
    )


def _retry_decision() -> FinalValidationDecision:
    return FinalValidationDecision(
        decision=FinalDecision.RETRY,
        overall_score=0.6,
        critical_issues=["minor style drift"],
        retry_instructions="Increase frame separation",
        confidence=0.7,
        notes="retry once",
    )


def _fail_decision() -> FinalValidationDecision:
    return FinalValidationDecision(
        decision=FinalDecision.FAIL,
        overall_score=0.2,
        critical_issues=["unreadable silhouette"],
        retry_instructions="",
        confidence=0.95,
        notes="terminal fail",
    )


@pytest.mark.asyncio
async def test_executor_success_path(tmp_path):
    settings = Settings(output_dir=tmp_path, palettes_dir=tmp_path, OPENAI_API_KEY="", enforce_outline=False)
    provider = StubProviderAdapter([_binary_sprite()])
    agents = StubAgentRuntime(_custom_plan(), [_pass_decision()])
    executor = WorkflowExecutor(settings=settings, provider=provider, agents=agents)

    result = await executor.run(_request())
    assert result.status == JobStatus.SUCCESS
    assert result.stage == StageName.FINALIZE
    assert result.artifacts is not None
    assert result.artifacts.total_frames == 1

    stage_order = [t.stage for t in result.trace]
    assert stage_order == [
        StageName.INPUT_VALIDATE,
        StageName.ROUTE,
        StageName.PLAN,
        StageName.GENERATE,
        StageName.EXTRACT,
        StageName.POSTPROCESS,
        StageName.DETERMINISTIC_GATE,
        StageName.EXPORT,
        StageName.FINALIZE,
    ]


@pytest.mark.asyncio
async def test_executor_deterministic_gate_fail_is_terminal(tmp_path):
    settings = Settings(output_dir=tmp_path, palettes_dir=tmp_path, OPENAI_API_KEY="", enforce_outline=False)
    provider = StubProviderAdapter([_semi_alpha_sprite()])
    agents = StubAgentRuntime(_custom_plan(), [_pass_decision()])
    executor = WorkflowExecutor(settings=settings, provider=provider, agents=agents)

    result = await executor.run(_request())
    assert result.status == JobStatus.FAILED
    assert result.stage == StageName.DETERMINISTIC_GATE
    assert result.errors[0].code == ErrorCode.QA_FAILED
    assert agents.final_validate_calls == 0


@pytest.mark.asyncio
async def test_executor_timeout_behavior(tmp_path):
    settings = Settings(output_dir=tmp_path, palettes_dir=tmp_path, OPENAI_API_KEY="", enforce_outline=False)
    provider = StubProviderAdapter([_binary_sprite()], delay_s=0.05)
    agents = StubAgentRuntime(_custom_plan(), [_pass_decision()])
    executor = WorkflowExecutor(settings=settings, provider=provider, agents=agents)
    request = _request(parameters={"timeout_s": 0.01})

    result = await executor.run(request)
    assert result.status == JobStatus.FAILED
    assert result.errors[0].code == ErrorCode.TIMEOUT


@pytest.mark.asyncio
async def test_executor_invalid_reference_path_fails_input_validation(tmp_path):
    settings = Settings(output_dir=tmp_path, palettes_dir=tmp_path, OPENAI_API_KEY="", enforce_outline=False)
    provider = StubProviderAdapter([_binary_sprite()])
    agents = StubAgentRuntime(_custom_plan(), [_pass_decision()])
    executor = WorkflowExecutor(settings=settings, provider=provider, agents=agents)
    request = _request(
        parameters={
            "reference_image_path": str(tmp_path / "missing.png"),
        }
    )

    result = await executor.run(request)
    assert result.status == JobStatus.FAILED
    assert result.stage == StageName.INPUT_VALIDATE
    assert result.errors[0].code == ErrorCode.INVALID_INPUT


@pytest.mark.asyncio
async def test_executor_passes_external_reference_to_provider(tmp_path):
    ref_path = tmp_path / "reference.png"
    _binary_sprite().save(ref_path)

    settings = Settings(output_dir=tmp_path, palettes_dir=tmp_path, OPENAI_API_KEY="", enforce_outline=False)
    provider = StubProviderAdapter([_binary_sprite()])
    plan = ExecutionPlan(
        asset_type=AssetType.CHARACTER,
        expected_total_frames=1,
        planned_prompts=[
            PlannedPrompt(
                key="anim_south_east",
                prompt="anim",
                expected_frames=1,
                layout="horizontal_strip",
                external_reference_paths=[str(ref_path.resolve())],
            )
        ],
        qa_min_score=0.7,
        notes="extension plan",
    )
    agents = StubAgentRuntime(plan, [_pass_decision()])
    executor = WorkflowExecutor(settings=settings, provider=provider, agents=agents)
    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        name="hero_jump",
        objective="extend animation",
        style="pixel",
        resolution="16x16",
        max_colors=8,
        parameters={
            "reference_image_path": str(ref_path),
            "external_reference_paths": [str(ref_path)],
            "extension_mode": True,
        },
    )

    result = await executor.run(request)
    assert result.status == JobStatus.SUCCESS
    assert provider.reference_counts == [1]


@pytest.mark.asyncio
async def test_executor_projects_frames_to_requested_resolution(tmp_path):
    settings = Settings(output_dir=tmp_path, palettes_dir=tmp_path, OPENAI_API_KEY="", enforce_outline=False)
    provider = StubProviderAdapter([_separator_strip(2, (32, 32))])
    agents = StubAgentRuntime(_custom_plan(expected_frames=2), [_pass_decision()])
    executor = WorkflowExecutor(settings=settings, provider=provider, agents=agents)

    result = await executor.run(_request(expected_frames=2, resolution="16x16"))

    assert result.status == JobStatus.SUCCESS
    assert result.artifacts is not None
    assert result.artifacts.total_frames == 2
    for paths in result.artifacts.frame_paths.values():
        for path in paths:
            image = Image.open(path).convert("RGBA")
            assert image.size == (16, 16)


@pytest.mark.asyncio
async def test_executor_aggregates_generation_usage_in_metrics(tmp_path):
    settings = Settings(output_dir=tmp_path, palettes_dir=tmp_path, OPENAI_API_KEY="", enforce_outline=False)
    provider = StubProviderAdapter([_binary_sprite()])
    provider.model_name = "gpt-image-1"
    agents = StubAgentRuntime(_custom_plan(), [_pass_decision()])
    executor = WorkflowExecutor(settings=settings, provider=provider, agents=agents)

    provider._images = [_binary_sprite()]
    result = await executor.run(_request())

    assert result.status == JobStatus.SUCCESS
    assert result.metrics is not None
    generation_usage = result.metrics.usage["generation"]
    assert generation_usage["calls"] == 1
    assert generation_usage["input_tokens"] == 0
    assert generation_usage["output_tokens"] == 0
    assert generation_usage["entries"][0]["prompt_key"] == "main"
