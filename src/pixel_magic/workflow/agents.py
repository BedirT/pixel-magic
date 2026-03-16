"""Agents SDK runtime for routing, planning, correction, and final validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agents import Agent, Runner

from pixel_magic.workflow.models import (
    AssetType,
    CorrectionPatch,
    ExecutionPlan,
    FinalDecision,
    FinalValidationDecision,
    GenerationRequest,
    ValidationPacket,
)
from pixel_magic.workflow.tools import (
    AgentToolContext,
    apply_correction_patch,
    build_plan_from_request,
    compile_validation_packet,
    default_final_decision,
    planner_tools_for_asset,
    score_artifact_set,
)


def _planner_instructions(asset_type: AssetType) -> str:
    return (
        "You are a strict planning agent for pixel-art generation. "
        "Return ONLY an ExecutionPlan that is internally consistent and complete. "
        "Use your specialized tools to build prompt packs, validate constraints, "
        "and estimate budget. "
        f"You are currently planning for asset_type='{asset_type.value}'. "
        "Do not invent unsupported steps."
    )


def _make_planner_agent(model: str, asset_type: AssetType) -> Agent[AgentToolContext]:
    return Agent[AgentToolContext](
        name=f"{asset_type.value.title()}PlannerAgent",
        model=model,
        instructions=_planner_instructions(asset_type),
        tools=planner_tools_for_asset(asset_type),
        output_type=ExecutionPlan,
    )


def create_request_router_agent(
    model: str,
    planners: list[Agent[AgentToolContext]],
) -> Agent[AgentToolContext]:
    """Create the request-router agent with planner handoffs."""
    return Agent[AgentToolContext](
        name="RequestRouterAgent",
        model=model,
        instructions=(
            "Route incoming requests to exactly one specialized planner via handoff. "
            "Choose planner strictly based on request asset_type. "
            "Do not output prose."
        ),
        handoffs=planners,
    )


def create_correction_planner_agent(model: str) -> Agent[AgentToolContext]:
    """Create correction planner that outputs a structured patch."""
    return Agent[AgentToolContext](
        name="CorrectionPlannerAgent",
        model=model,
        instructions=(
            "You produce exactly one CorrectionPatch for a failed validation. "
            "Keep changes minimal and deterministic: append clear constraints and "
            "only override frame counts when explicitly required."
        ),
        tools=[apply_correction_patch],
        output_type=CorrectionPatch,
    )


def create_final_validator_agent(model: str) -> Agent[AgentToolContext]:
    """Create final validator agent with structured pass/retry/fail output."""
    return Agent[AgentToolContext](
        name="FinalValidatorAgent",
        model=model,
        instructions=(
            "You are the final quality gate. Use validation tools and return "
            "FinalValidationDecision only. Choose 'retry' only when a single additional "
            "attempt is likely to materially improve quality."
        ),
        tools=[compile_validation_packet, score_artifact_set],
        output_type=FinalValidationDecision,
    )


@dataclass
class AgentRuntime:
    """Runtime wrapper around OpenAI Agents SDK with deterministic fallbacks."""

    model: str
    api_key: str
    provider: str = "openai"
    chromakey_color: str = "green"

    def __post_init__(self) -> None:
        self._enabled = bool(self.api_key)
        self._planners = [_make_planner_agent(self.model, t) for t in AssetType]
        self._router = create_request_router_agent(self.model, self._planners)
        self._correction = create_correction_planner_agent(self.model)
        self._validator = create_final_validator_agent(self.model)

    async def _run_agent(
        self,
        agent: Agent[AgentToolContext],
        prompt: str,
        context: AgentToolContext,
        max_turns: int = 8,
    ) -> Any:
        result = await Runner.run(agent, prompt, context=context, max_turns=max_turns)
        return result.final_output, result.last_agent.name

    async def route_and_plan(self, request: GenerationRequest) -> tuple[ExecutionPlan, str]:
        """Route request via handoff and return planner output."""
        if not self._enabled:
            return build_plan_from_request(request, self.provider, self.chromakey_color), "deterministic_fallback"

        context = AgentToolContext(
            request=request, provider=self.provider, chromakey_color=self.chromakey_color,
        )
        payload = json.dumps(request.model_dump(), indent=2)
        output, last_agent_name = await self._run_agent(
            self._router,
            (
                "Route and plan this request. "
                "Use a specialist planner handoff and return an ExecutionPlan.\n\n"
                f"{payload}"
            ),
            context=context,
            max_turns=12,
        )

        if isinstance(output, ExecutionPlan):
            return output, last_agent_name
        return build_plan_from_request(request, self.provider, self.chromakey_color), "fallback_due_to_unstructured_output"

    async def plan_correction(
        self,
        request: GenerationRequest,
        plan: ExecutionPlan,
        packet: ValidationPacket,
        retry_instructions: str,
    ) -> CorrectionPatch:
        """Return one correction patch for the single allowed retry."""
        if not self._enabled:
            return CorrectionPatch(
                prompt_suffix=retry_instructions.strip(),
                append_constraints=["Increase separation between frames and preserve identity."],
                notes="deterministic_fallback",
            )

        context = AgentToolContext(
            request=request, plan=plan, validation_packet=packet,
            provider=self.provider, chromakey_color=self.chromakey_color,
        )
        payload = {
            "retry_instructions": retry_instructions,
            "request": request.model_dump(),
            "plan": plan.model_dump(),
            "validation_packet": packet.model_dump(),
        }
        output, _ = await self._run_agent(
            self._correction,
            (
                "Generate a minimal CorrectionPatch from this payload. "
                "Do not output prose.\n\n"
                f"{json.dumps(payload, indent=2)}"
            ),
            context=context,
            max_turns=8,
        )

        if isinstance(output, CorrectionPatch):
            return output
        return CorrectionPatch(
            prompt_suffix=retry_instructions.strip(),
            append_constraints=["Improve consistency and readability."],
            notes="fallback_due_to_unstructured_output",
        )

    async def final_validate(
        self,
        request: GenerationRequest,
        plan: ExecutionPlan,
        packet: ValidationPacket,
    ) -> FinalValidationDecision:
        """Run final validator agent or deterministic fallback."""
        if not self._enabled:
            return FinalValidationDecision(**default_final_decision(packet))

        context = AgentToolContext(
            request=request, plan=plan, validation_packet=packet,
            provider=self.provider, chromakey_color=self.chromakey_color,
        )
        payload = json.dumps(packet.model_dump(), indent=2)
        output, _ = await self._run_agent(
            self._validator,
            (
                "Review this validation packet and return FinalValidationDecision.\n\n"
                f"{payload}"
            ),
            context=context,
            max_turns=8,
        )
        if isinstance(output, FinalValidationDecision):
            return output

        # Conservative fallback: treat unexpected outputs as retry suggestion if gate passed.
        default = default_final_decision(packet)
        if packet.deterministic_gate.passed:
            default["decision"] = FinalDecision.RETRY
            default["retry_instructions"] = (
                "Tighten frame separation and improve visual consistency while preserving style."
            )
            default["notes"] = "fallback_due_to_unstructured_output"
        return FinalValidationDecision(**default)
