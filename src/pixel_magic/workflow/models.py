"""Structured models for the rewritten generation workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AssetType(StrEnum):
    """Supported high-level asset categories."""

    CHARACTER = "character"
    TILESET = "tileset"
    ITEMS = "items"
    EFFECT = "effect"
    UI = "ui"
    CUSTOM = "custom"


class JobStatus(StrEnum):
    """Terminal job status."""

    SUCCESS = "success"
    FAILED = "failed"


class StageName(StrEnum):
    """Execution state-machine stages."""

    INPUT_VALIDATE = "input_validate"
    ROUTE = "route"
    PLAN = "plan"
    GENERATE = "generate"
    EXTRACT = "extract"
    POSTPROCESS = "postprocess"
    DETERMINISTIC_GATE = "deterministic_gate"
    FINAL_VALIDATOR_AGENT = "final_validator_agent"
    EXPORT = "export"
    FINALIZE = "finalize"


class ErrorCode(StrEnum):
    """Stable machine-readable error codes."""

    INVALID_INPUT = "INVALID_INPUT"
    PLAN_INVALID = "PLAN_INVALID"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    EXTRACTION_MISMATCH = "EXTRACTION_MISMATCH"
    QA_FAILED = "QA_FAILED"
    EXPORT_FAILED = "EXPORT_FAILED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATOR_FAILED = "VALIDATOR_FAILED"


class FinalDecision(StrEnum):
    """Final validator decision options."""

    PASS = "pass"
    RETRY = "retry"
    FAIL = "fail"


class GenerationRequest(BaseModel):
    """Normalized generation request consumed by the new executor."""

    asset_type: AssetType
    name: str = Field(default="asset", min_length=1, max_length=128)
    objective: str = Field(min_length=1, max_length=4000)
    style: str = Field(default="16-bit pixel art")
    resolution: str = Field(default="64x64")
    max_colors: int = Field(default=16, ge=2, le=128)
    expected_frames: int = Field(default=1, ge=1, le=4096)
    layout: str = Field(default="horizontal_strip")
    palette_name: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("resolution")
    @classmethod
    def _validate_resolution(cls, value: str) -> str:
        parts = value.lower().split("x")
        if len(parts) != 2:
            raise ValueError("resolution must be formatted as WxH")
        if not all(p.isdigit() for p in parts):
            raise ValueError("resolution must be numeric WxH")
        width, height = int(parts[0]), int(parts[1])
        if width < 8 or height < 8:
            raise ValueError("resolution must be at least 8x8")
        if width > 2048 or height > 2048:
            raise ValueError("resolution must be at most 2048x2048")
        return f"{width}x{height}"


class PlannedPrompt(BaseModel):
    """One model-generation task in an execution plan."""

    key: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=12000)
    expected_frames: int = Field(default=1, ge=1, le=4096)
    layout: str = Field(default="horizontal_strip")
    reference_key: str | None = None
    external_reference_paths: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    """Structured planner output consumed by the deterministic executor."""

    asset_type: AssetType
    expected_total_frames: int = Field(ge=1, le=4096)
    planned_prompts: list[PlannedPrompt] = Field(min_length=1)
    qa_min_score: float = Field(default=0.7, ge=0.0, le=1.0)
    notes: str = ""


class CorrectionPatch(BaseModel):
    """Patch instructions produced by the correction planner."""

    prompt_suffix: str = ""
    append_constraints: list[str] = Field(default_factory=list)
    expected_frame_overrides: dict[str, int] = Field(default_factory=dict)
    max_colors_override: int | None = Field(default=None, ge=2, le=128)
    notes: str = ""


class DeterministicGate(BaseModel):
    """Result of the deterministic QA gate."""

    passed: bool
    checks: list[dict[str, Any]] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)


class FinalValidationDecision(BaseModel):
    """Final validator agent decision for pass/retry/fail."""

    decision: FinalDecision
    overall_score: float = Field(ge=0.0, le=1.0)
    critical_issues: list[str] = Field(default_factory=list)
    retry_instructions: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""


class ValidationPacket(BaseModel):
    """Payload sent to the final validator agent."""

    request_summary: dict[str, Any]
    artifact_manifest: dict[str, Any]
    deterministic_gate: DeterministicGate
    extraction_stats: dict[str, Any]
    representative_frames: dict[str, dict[str, Any]] = Field(default_factory=dict)
    export_stats: dict[str, Any] = Field(default_factory=dict)


class ArtifactManifest(BaseModel):
    """Exported artifact paths grouped by generated segment."""

    output_dir: str
    atlas_path: str
    metadata_path: str
    raw_paths: dict[str, str] = Field(default_factory=dict)
    frame_paths: dict[str, list[str]] = Field(default_factory=dict)
    total_frames: int = 0


class StageTrace(BaseModel):
    """One stage trace entry used for observability and tests."""

    stage: StageName
    ok: bool
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class JobMetrics(BaseModel):
    """Execution metrics for a completed job."""

    provider: str
    model: str
    total_generation_calls: int = 0
    retry_count: int = 0
    duration_s: float = 0.0


class JobError(BaseModel):
    """Structured failure details."""

    code: ErrorCode
    message: str
    stage: StageName
    details: dict[str, Any] = Field(default_factory=dict)


class JobResult(BaseModel):
    """Final normalized job response envelope."""

    status: JobStatus
    job_id: str
    stage: StageName
    request: GenerationRequest
    plan: ExecutionPlan | None = None
    artifacts: ArtifactManifest | None = None
    deterministic_gate: DeterministicGate | None = None
    final_validation: FinalValidationDecision | None = None
    metrics: JobMetrics | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[JobError] = Field(default_factory=list)
    trace: list[StageTrace] = Field(default_factory=list)
