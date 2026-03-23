"""Deterministic state-machine executor for the rewritten generation flow."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from PIL import Image

from pixel_magic.config import Settings
from pixel_magic.generation.extractor import extract_frames
from pixel_magic.models.asset import CompositeLayout
from pixel_magic.models.palette import Palette
from pixel_magic.pipeline.cleanup import cleanup_sprite
from pixel_magic.pipeline.palette import extract_adaptive_palette, quantize_image
from pixel_magic.pipeline.template import generate_grid_template
from pixel_magic.qa.deterministic import run_deterministic_qa
from pixel_magic.tracing import get_tracer
from pixel_magic.usage import build_usage_entry, summarize_usage_entries
from pixel_magic.workflow.agents import AgentRuntime
from pixel_magic.workflow.exporter import export_assets
from pixel_magic.workflow.models import (
    AssetType,
    DeterministicGate,
    ErrorCode,
    FinalDecision,
    GenerationRequest,
    JobError,
    JobMetrics,
    JobResult,
    JobStatus,
    StageName,
    StageTrace,
    ValidationPacket,
)
from pixel_magic.workflow.provider_adapter import ProviderAdapter
from pixel_magic.workflow.tools import apply_patch_to_plan

_tracer = get_tracer("pixel_magic.workflow.executor")


def _safe_layout(value: str) -> CompositeLayout:
    try:
        return CompositeLayout(value)
    except ValueError:
        return CompositeLayout.HORIZONTAL_STRIP


def _load_palette(settings: Settings, palette_name: str | None) -> Palette | None:
    if not palette_name:
        return None
    path = settings.palettes_dir / f"{palette_name}.hex"
    if path.exists():
        return Palette.from_hex_file(path)
    return None


def _representative_frame_stats(groups: dict[str, list[Image.Image]]) -> dict[str, dict[str, Any]]:
    """Collect lightweight per-group frame stats for validator context."""
    stats: dict[str, dict[str, Any]] = {}
    for key, frames in groups.items():
        if not frames:
            stats[key] = {"frame_count": 0}
            continue
        sample = frames[0]
        alpha = sample.getchannel("A")
        nonzero = alpha.point(lambda v: 255 if v > 0 else 0)
        bbox = nonzero.getbbox()
        stats[key] = {
            "frame_count": len(frames),
            "sample_size": [sample.width, sample.height],
            "sample_bbox": list(bbox) if bbox else None,
        }
    return stats


def _parse_resolution(value: str) -> tuple[int, int]:
    width, height = value.lower().split("x", 1)
    return int(width), int(height)


def _center_on_canvas(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    target_w, target_h = target_size
    if image.size == target_size:
        return image

    crop_left = max((image.width - target_w) // 2, 0)
    crop_top = max((image.height - target_h) // 2, 0)
    crop_right = crop_left + min(image.width, target_w)
    crop_bottom = crop_top + min(image.height, target_h)
    visible = image.crop((crop_left, crop_top, crop_right, crop_bottom))

    canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
    paste_x = (target_w - visible.width) // 2
    paste_y = (target_h - visible.height) // 2
    canvas.paste(visible, (paste_x, paste_y))
    return canvas


def _normalize_frame_to_resolution(
    frame: Image.Image,
    *,
    target_size: tuple[int, int],
    settings: Settings,
) -> tuple[Image.Image, dict[str, Any]]:
    """Normalize a raw provider frame to the target resolution.

    For pixel-art-style images (AI output at 1024px), we skip the
    destructive grid-projection pipeline and simply resize with
    LANCZOS to preserve visual quality.  Actual low-res pixel art
    (already at or below target) passes through unchanged.
    """
    target_w, target_h = target_size

    normalized = frame
    method = "passthrough"

    if normalized.width > target_w or normalized.height > target_h:
        # Pre-binarize alpha at full resolution BEFORE downscaling.
        # AI models output sprite-body pixels at alpha 224-254 and faint
        # halo pixels at alpha 1-30.  A low threshold (32) keeps all sprite
        # content while stripping only the halo — preventing LANCZOS from
        # blending halo colour into sprite edges during the downscale.
        if settings.alpha_policy == "binary" and normalized.mode == "RGBA":
            r, g, b, a = normalized.split()
            a = a.point(lambda v: 255 if v >= 32 else 0)
            normalized = Image.merge("RGBA", (r, g, b, a))

        scale = min(target_w / normalized.width, target_h / normalized.height)
        resized_size = (
            max(1, round(normalized.width * scale)),
            max(1, round(normalized.height * scale)),
        )
        if resized_size != normalized.size:
            normalized = normalized.resize(resized_size, Image.LANCZOS)
            method = "lanczos_downscale"

            # LANCZOS reintroduces semi-transparent edge pixels —
            # binarize again with a low threshold to preserve edges.
            if settings.alpha_policy == "binary" and normalized.mode == "RGBA":
                r, g, b, a = normalized.split()
                a = a.point(lambda v: 255 if v >= 32 else 0)
                normalized = Image.merge("RGBA", (r, g, b, a))

    normalized = _center_on_canvas(normalized, target_size)

    return normalized, {
        "input_size": [frame.width, frame.height],
        "projected_size": [normalized.width, normalized.height],
        "method": method,
        "target_size": [target_w, target_h],
    }


class WorkflowExecutor:
    """Runs the fixed generation state machine with one final-retry budget."""

    def __init__(
        self,
        *,
        settings: Settings,
        provider: ProviderAdapter,
        agents: AgentRuntime,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.agents = agents

    async def run(self, request: GenerationRequest) -> JobResult:
        """Execute the full workflow for one request."""
        with _tracer.start_as_current_span("pixel_magic.workflow") as root_span:
            root_span.set_attribute("workflow.asset_type", request.asset_type.value)
            root_span.set_attribute("workflow.name", request.name)
            root_span.set_attribute("workflow.resolution", request.resolution)
            root_span.set_attribute("workflow.provider", self.provider.provider_name)
            root_span.set_attribute("workflow.model", self.provider.model_name)
            return await self._run_impl(request, root_span)

    async def _run_impl(self, request: GenerationRequest, root_span) -> JobResult:
        """Inner implementation wrapped by the root tracing span."""
        job_id = uuid.uuid4().hex
        started = time.monotonic()
        warnings: list[str] = []
        timeout_raw = request.parameters.get("timeout_s")
        timeout_s: float | None = None
        if timeout_raw is not None:
            try:
                timeout_s = float(timeout_raw)
            except (TypeError, ValueError):
                timeout_s = None
                warnings.append(f"Ignored invalid timeout_s value: {timeout_raw!r}")
        if timeout_s is not None and timeout_s <= 0:
            timeout_s = None
        trace: list[StageTrace] = []
        generation_calls = 0
        retry_count = 0
        generation_usage_entries: list[dict[str, Any]] = []
        agent_usage_entries: list[dict[str, Any]] = []
        stage = StageName.INPUT_VALIDATE
        effective_request = request
        external_reference_images: dict[str, Image.Image] = {}

        def usage_buckets() -> dict[str, Any]:
            return {
                "generation": summarize_usage_entries(generation_usage_entries),
                "agent": summarize_usage_entries(agent_usage_entries),
                "judge": summarize_usage_entries([]),
            }

        def record_agent_event(agent_stage: str, note: str = "") -> None:
            agent_usage_entries.append(
                {
                    "prompt_key": agent_stage,
                    "provider": getattr(self.agents, "provider", ""),
                    "model": getattr(self.agents, "model", ""),
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "notes": note,
                }
            )

        def add_trace(
            current_stage: StageName,
            ok: bool,
            message: str = "",
            data: dict[str, Any] | None = None,
        ) -> None:
            trace.append(
                StageTrace(
                    stage=current_stage,
                    ok=ok,
                    message=message,
                    data=data or {},
                )
            )

        def fail(
            code: ErrorCode,
            message: str,
            *,
            details: dict[str, Any] | None = None,
            plan=None,
            deterministic_gate=None,
            final_validation=None,
            artifacts=None,
        ) -> JobResult:
            duration = time.monotonic() - started
            add_trace(stage, False, message, details or {})
            return JobResult(
                status=JobStatus.FAILED,
                job_id=job_id,
                stage=stage,
                request=effective_request,
                plan=plan,
                artifacts=artifacts,
                deterministic_gate=deterministic_gate,
                final_validation=final_validation,
                metrics=JobMetrics(
                    provider=self.provider.provider_name,
                    model=self.provider.model_name,
                    total_generation_calls=generation_calls,
                    retry_count=retry_count,
                    duration_s=round(duration, 3),
                    usage=usage_buckets(),
                ),
                warnings=warnings,
                errors=[
                    JobError(
                        code=code,
                        message=message,
                        stage=stage,
                        details=details or {},
                    )
                ],
                trace=trace,
            )

        def timeout_failure() -> JobResult | None:
            if timeout_s is None:
                return None
            elapsed = time.monotonic() - started
            if elapsed <= timeout_s:
                return None
            return fail(
                ErrorCode.TIMEOUT,
                "Workflow timed out",
                details={"timeout_s": timeout_s, "elapsed_s": round(elapsed, 3)},
            )

        raw_reference_paths = request.parameters.get("external_reference_paths", [])
        if raw_reference_paths and not isinstance(raw_reference_paths, list):
            return fail(
                ErrorCode.INVALID_INPUT,
                "external_reference_paths must be a list of file paths",
                details={"value": raw_reference_paths},
            )
        if not isinstance(raw_reference_paths, list):
            raw_reference_paths = []

        single_reference_path = request.parameters.get("reference_image_path")
        if isinstance(single_reference_path, str) and single_reference_path.strip():
            raw_reference_paths.append(single_reference_path.strip())

        normalized_reference_paths: list[str] = []
        for raw_path in raw_reference_paths:
            path = Path(str(raw_path))
            if not path.exists() or not path.is_file():
                return fail(
                    ErrorCode.INVALID_INPUT,
                    "Reference image path does not exist",
                    details={"path": str(path)},
                )
            try:
                loaded = Image.open(path).convert("RGBA")
            except Exception as exc:
                return fail(
                    ErrorCode.INVALID_INPUT,
                    "Failed to load reference image",
                    details={"path": str(path), "error": str(exc)},
                )

            canonical = str(path.resolve())
            external_reference_images[canonical] = loaded
            external_reference_images[str(path)] = loaded
            normalized_reference_paths.append(canonical)

        if normalized_reference_paths:
            updated_params = dict(effective_request.parameters)
            updated_params["external_reference_paths"] = normalized_reference_paths
            effective_request = effective_request.model_copy(update={"parameters": updated_params})

        add_trace(
            StageName.INPUT_VALIDATE,
            True,
            "request validated",
            {"external_reference_count": len(normalized_reference_paths)},
        )

        stage = StageName.ROUTE
        timed_out = timeout_failure()
        if timed_out is not None:
            return timed_out
        try:
            plan, routed_by = await self.agents.route_and_plan(effective_request)
        except Exception as exc:
            return fail(
                ErrorCode.PLAN_INVALID,
                "Routing/planning failed",
                details={"error": str(exc)},
            )
        record_agent_event(StageName.ROUTE.value, routed_by)
        add_trace(stage, True, "request routed", {"routed_by": routed_by})

        stage = StageName.PLAN
        timed_out = timeout_failure()
        if timed_out is not None:
            return timed_out

        if plan.asset_type != effective_request.asset_type:
            warnings.append(
                f"Planner asset_type mismatch ({plan.asset_type} != "
                f"{effective_request.asset_type}); request type kept."
            )
            plan = plan.model_copy(update={"asset_type": effective_request.asset_type})

        if not plan.planned_prompts:
            return fail(
                ErrorCode.PLAN_INVALID,
                "Planner returned no prompts",
                details={"plan": plan.model_dump()},
                plan=plan,
            )
        add_trace(
            stage,
            True,
            "plan ready",
            {
                "prompt_count": len(plan.planned_prompts),
                "expected_total_frames": plan.expected_total_frames,
            },
        )

        final_validation = None
        deterministic_gate = None
        raw_images: dict[str, Image.Image] = {}
        processed_groups: dict[str, list[Image.Image]] = {}
        extraction_stats: dict[str, Any] = {}
        target_frame_size = _parse_resolution(effective_request.resolution)

        while True:
            stage = StageName.GENERATE
            timed_out = timeout_failure()
            if timed_out is not None:
                return timed_out
            raw_images = {}
            generated_meta: dict[str, Any] = {}
            try:
                with _tracer.start_as_current_span("workflow.generate") as gen_span:
                    gen_span.set_attribute("workflow.stage", "GENERATE")
                    gen_span.set_attribute("workflow.prompt_count", len(plan.planned_prompts))
                    for prompt in plan.planned_prompts:
                        timed_out = timeout_failure()
                        if timed_out is not None:
                            return timed_out
                        refs: list[Image.Image] = []
                        if prompt.reference_key:
                            ref = raw_images.get(prompt.reference_key)
                            if ref is not None:
                                refs.append(ref)
                        if prompt.external_reference_paths:
                            for ref_path in prompt.external_reference_paths:
                                ref = external_reference_images.get(ref_path)
                                if ref is not None:
                                    refs.append(ref)
                        elif normalized_reference_paths:
                            for ref_path in normalized_reference_paths:
                                ref = external_reference_images.get(ref_path)
                                if ref is not None:
                                    refs.append(ref)
                        # Inject grid template for multi-frame generation
                        # (skip for reference_sheet — JSON prompt describes its own layout)
                        if prompt.expected_frames > 1 and target_frame_size and prompt.layout != "reference_sheet":
                            tw, th = target_frame_size
                            grid_tpl = generate_grid_template(
                                count=prompt.expected_frames,
                                cell_w=tw,
                                cell_h=th,
                                asset_type=effective_request.asset_type.value,
                            )
                            refs.insert(0, grid_tpl)
                        result = await self.provider.generate(prompt.prompt, refs or None)
                        raw_images[prompt.key] = result.image
                        usage_entry = build_usage_entry(
                            result.metadata,
                            provider=self.provider.provider_name,
                            model=result.model_used or self.provider.model_name,
                            prompt_key=prompt.key,
                            reference_count=len(refs or []),
                        )
                        generation_usage_entries.append(usage_entry)
                        generated_meta[prompt.key] = {
                            "model_used": result.model_used,
                            "metadata": {
                                **dict(result.metadata or {}),
                                "normalized_usage": usage_entry["normalized_usage"],
                                "cost_inputs": {
                                    "provider": usage_entry["provider"],
                                    "model": usage_entry["model"],
                                    "input_tokens": usage_entry["input_tokens"],
                                    "output_tokens": usage_entry["output_tokens"],
                                    "total_tokens": usage_entry["total_tokens"],
                                },
                            },
                        }
                        generation_calls += 1
                    gen_span.set_attribute("workflow.generation_calls", generation_calls)
            except Exception as exc:
                return fail(
                    ErrorCode.PROVIDER_ERROR,
                    "Image generation failed",
                    details={"error": str(exc)},
                    plan=plan,
                )
            add_trace(
                stage,
                True,
                "generation complete",
                {"calls": generation_calls, "generated_meta": generated_meta},
            )

            stage = StageName.EXTRACT
            timed_out = timeout_failure()
            if timed_out is not None:
                return timed_out
            extracted_groups: dict[str, list[Image.Image]] = {}
            extraction_stats = {
                "groups": {},
                "raw_sizes": {},
                "normalized_sizes": {},
                "target_resolution": list(target_frame_size),
            }
            try:
                for prompt in plan.planned_prompts:
                    image = raw_images[prompt.key]
                    extraction_stats["raw_sizes"][prompt.key] = [image.width, image.height]
                    if prompt.expected_frames <= 1:
                        if self.provider.provider_name == "gemini":
                            from pixel_magic.pipeline.chromakey import remove_chromakey
                            frames = [remove_chromakey(image, color=self.settings.chromakey_color)]
                        else:
                            frames = [image]
                    else:
                        frames = extract_frames(
                            image,
                            _safe_layout(prompt.layout),
                            prompt.expected_frames,
                            provider=self.provider.provider_name,
                            chromakey_color=self.settings.chromakey_color,
                        )

                    if len(frames) != prompt.expected_frames:
                        return fail(
                            ErrorCode.EXTRACTION_MISMATCH,
                            "Extracted frame count mismatch",
                            details={
                                "prompt_key": prompt.key,
                                "expected_frames": prompt.expected_frames,
                                "actual_frames": len(frames),
                            },
                            plan=plan,
                        )

                    normalized_frames: list[Image.Image] = []
                    normalization_details: list[dict[str, Any]] = []
                    for frame in frames:
                        normalized_frame, detail = _normalize_frame_to_resolution(
                            frame,
                            target_size=target_frame_size,
                            settings=self.settings,
                        )
                        normalized_frames.append(normalized_frame)
                        normalization_details.append(detail)

                    extracted_groups[prompt.key] = normalized_frames
                    extraction_stats["groups"][prompt.key] = len(normalized_frames)
                    extraction_stats["normalized_sizes"][prompt.key] = normalization_details
            except Exception as exc:
                return fail(
                    ErrorCode.EXTRACTION_MISMATCH,
                    "Frame extraction failed",
                    details={"error": str(exc)},
                    plan=plan,
                )
            add_trace(stage, True, "frame extraction complete", extraction_stats)

            stage = StageName.POSTPROCESS
            timed_out = timeout_failure()
            if timed_out is not None:
                return timed_out
            all_frames = [f for frames in extracted_groups.values() for f in frames]
            palette = _load_palette(self.settings, effective_request.palette_name)
            if palette is None and all_frames:
                palette = extract_adaptive_palette(all_frames, effective_request.max_colors)
            # Ensure outline color is in palette when outlines are enabled
            if palette is not None and self.settings.enforce_outline:
                outline_color = (0, 0, 0, 255)
                if outline_color not in palette.colors:
                    palette.colors.append(outline_color)

            processed_groups = {}
            try:
                for key, frames in extracted_groups.items():
                    processed_frames: list[Image.Image] = []
                    for frame in frames:
                        processed = frame
                        if palette is not None:
                            processed = quantize_image(processed, palette)
                        processed = cleanup_sprite(
                            processed,
                            palette.colors if palette else None,
                            self.settings.min_island_size,
                            self.settings.max_hole_size,
                            self.settings.enforce_outline,
                        )
                        processed_frames.append(processed)
                    processed_groups[key] = processed_frames
            except Exception as exc:
                return fail(
                    ErrorCode.INTERNAL_ERROR,
                    "Postprocess stage failed",
                    details={"error": str(exc)},
                    plan=plan,
                )
            add_trace(stage, True, "postprocess complete")

            stage = StageName.DETERMINISTIC_GATE
            timed_out = timeout_failure()
            if timed_out is not None:
                return timed_out
            # Skip palette_delta for batch asset types where frames are
            # intentionally different sprites (not animation frames).
            _batch_types = {AssetType.CHARACTER, AssetType.TILESET, AssetType.ITEMS, AssetType.UI, AssetType.EFFECT}
            qa_report = run_deterministic_qa(
                [f for frames in processed_groups.values() for f in frames],
                palette=palette,
                alpha_policy=self.settings.alpha_policy,
                expected_frame_count=plan.expected_total_frames,
                expected_frame_size=target_frame_size,
                min_island_size=self.settings.min_island_size,
                skip_palette_delta=request.asset_type in _batch_types,
            )
            checks = qa_report.to_dict()["checks"]
            failed_checks = [c for c in checks if not c["passed"]]
            deterministic_gate = DeterministicGate(
                passed=qa_report.passed,
                checks=checks,
                failure_reasons=[f"{c['name']}: {c['details']}" for c in failed_checks],
            )
            if not deterministic_gate.passed:
                return fail(
                    ErrorCode.QA_FAILED,
                    "Deterministic QA gate failed",
                    details={"failed_checks": deterministic_gate.failure_reasons},
                    plan=plan,
                    deterministic_gate=deterministic_gate,
                )
            add_trace(stage, True, "deterministic gate passed")

            # Skip validator — proceed directly to export
            break

        stage = StageName.EXPORT
        timed_out = timeout_failure()
        if timed_out is not None:
            return timed_out
        try:
            manifest = export_assets(
                groups=processed_groups,
                raw_images=raw_images,
                output_root=self.settings.output_dir,
                name=effective_request.name,
                request=effective_request,
            )
        except Exception as exc:
            return fail(
                ErrorCode.EXPORT_FAILED,
                "Export stage failed",
                details={"error": str(exc)},
                plan=plan,
                deterministic_gate=deterministic_gate,
                final_validation=final_validation,
            )
        add_trace(stage, True, "export complete", {"output_dir": manifest.output_dir})

        stage = StageName.FINALIZE
        duration = time.monotonic() - started
        add_trace(stage, True, "job finalized")

        root_span.set_attribute("workflow.status", "success")
        root_span.set_attribute("workflow.duration_s", round(duration, 3))
        root_span.set_attribute("workflow.generation_calls", generation_calls)
        root_span.set_attribute("workflow.retry_count", retry_count)
        usage = usage_buckets()
        gen_usage = usage.get("generation", {})
        root_span.set_attribute("workflow.total_tokens", gen_usage.get("total_tokens", 0))
        root_span.set_attribute("workflow.estimated_cost_usd", gen_usage.get("estimated_cost_usd", 0.0))

        return JobResult(
            status=JobStatus.SUCCESS,
            job_id=job_id,
            stage=stage,
            request=effective_request,
            plan=plan,
            artifacts=manifest,
            deterministic_gate=deterministic_gate,
            final_validation=final_validation,
            metrics=JobMetrics(
                provider=self.provider.provider_name,
                model=self.provider.model_name,
                total_generation_calls=generation_calls,
                retry_count=retry_count,
                duration_s=round(duration, 3),
                usage=usage_buckets(),
            ),
            warnings=warnings,
            errors=[],
            trace=trace,
        )
