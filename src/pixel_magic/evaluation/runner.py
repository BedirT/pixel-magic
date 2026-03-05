"""Evaluation runner — orchestrates generation + judging across test cases."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from PIL import Image

from pixel_magic.config import Settings
from pixel_magic.evaluation.cases import EvalCase
from pixel_magic.evaluation.judge import JudgeResult, PixelArtJudge
from pixel_magic.generation.prompts import PromptBuilder
from pixel_magic.providers.base import GenerationConfig, ImageProvider
from pixel_magic.workflow import (
    AgentRuntime,
    AssetType,
    GenerationRequest,
    ProviderAdapter,
    WorkflowExecutor,
)

logger = logging.getLogger(__name__)


@dataclass
class EvalRunRecord:
    """Result of a single evaluation (one case, one run)."""

    case_name: str
    template_name: str
    variant_label: str
    model_used: str
    prompt_rendered: str
    judge: JudgeResult
    generation_time_s: float = 0.0
    image_path: str | None = None
    generation_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "case_name": self.case_name,
            "template_name": self.template_name,
            "variant_label": self.variant_label,
            "model_used": self.model_used,
            "generation_time_s": round(self.generation_time_s, 2),
            "image_path": self.image_path,
            "generation_metadata": self.generation_metadata,
            "judge": self.judge.to_dict(),
        }


@dataclass
class EvalRun:
    """A complete evaluation run across multiple cases."""

    variant_label: str
    model_name: str
    records: list[EvalRunRecord] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""

    @property
    def results(self) -> list[JudgeResult]:
        return [r.judge for r in self.records]

    def to_dict(self) -> dict:
        return {
            "variant_label": self.variant_label,
            "model_name": self.model_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_cases": len(self.records),
            "records": [r.to_dict() for r in self.records],
        }

    def save(self, path: Path) -> None:
        """Persist the run results as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> EvalRun:
        """Load a run from a JSON file."""
        data = json.loads(path.read_text())
        run = cls(
            variant_label=data["variant_label"],
            model_name=data["model_name"],
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
        )
        for rec_data in data.get("records", []):
            judge_data = rec_data.get("judge", {})
            judge = JudgeResult(
                scores=judge_data.get("scores", {}),
                feedback=judge_data.get("feedback", ""),
                error=judge_data.get("error"),
            )
            run.records.append(EvalRunRecord(
                case_name=rec_data["case_name"],
                template_name=rec_data["template_name"],
                variant_label=rec_data["variant_label"],
                model_used=rec_data["model_used"],
                prompt_rendered=rec_data.get("prompt_rendered", ""),
                judge=judge,
                generation_time_s=rec_data.get("generation_time_s", 0.0),
                image_path=rec_data.get("image_path"),
                generation_metadata=rec_data.get("generation_metadata", {}),
            ))
        return run


class EvalRunner:
    """Orchestrates evaluation: render prompt → generate image → judge quality."""

    def __init__(
        self,
        provider: ImageProvider,
        prompts: PromptBuilder,
        settings: Settings,
        judge: PixelArtJudge | None = None,
        output_dir: Path | None = None,
    ):
        self._provider = provider
        self._prompts = prompts
        self._settings = settings
        self._judge = judge or PixelArtJudge(provider)
        self._output_dir = output_dir or settings.output_dir / "eval"
        self._workflow_executor = WorkflowExecutor(
            settings=settings,
            provider=ProviderAdapter(provider, settings),
            agents=AgentRuntime(model=settings.agent_model, api_key=settings.openai_api_key),
        )

    async def run_case(
        self,
        case: EvalCase,
        variant_label: str = "default",
    ) -> EvalRunRecord:
        """Run a single evaluation case: generate + judge."""
        # Render prompt
        rendered = self._prompts.render(case.template_name, **case.params)

        # Generate
        config = GenerationConfig(image_size=self._settings.image_size)
        t0 = time.monotonic()

        try:
            result = await self._provider.generate(rendered, config)
            gen_time = time.monotonic() - t0
        except Exception as e:
            logger.error("Generation failed for case '%s': %s", case.name, e)
            return EvalRunRecord(
                case_name=case.name,
                template_name=case.template_name,
                variant_label=variant_label,
                model_used="error",
                prompt_rendered=rendered,
                judge=JudgeResult(error=str(e)),
                generation_metadata={"error": str(e)},
            )

        # Save generated image
        img_dir = self._output_dir / variant_label / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        img_path = img_dir / f"{case.name}.png"
        result.image.save(img_path)

        # Judge
        style = case.params.get("style", "16-bit SNES RPG style")
        max_colors = int(case.params.get("max_colors", "16"))

        judge_result = await self._judge.evaluate(
            result.image,
            asset_type=case.asset_type,
            style=style,
            max_colors=max_colors,
            expected_count=case.expected_count,
        )

        return EvalRunRecord(
            case_name=case.name,
            template_name=case.template_name,
            variant_label=variant_label,
            model_used=result.model_used,
            prompt_rendered=rendered,
            judge=judge_result,
            generation_time_s=gen_time,
            image_path=str(img_path),
            generation_metadata=result.metadata,
        )

    async def run_case_agent(
        self,
        case: EvalCase,
        variant_label: str = "default",
    ) -> EvalRunRecord:
        """Run a single evaluation case through the rewritten workflow executor."""
        p = case.params
        request = self._build_workflow_request(case)
        t0 = time.monotonic()
        result = await self._workflow_executor.run(request)
        gen_time = time.monotonic() - t0

        if result.status.value != "success":
            err_msg = result.errors[0].message if result.errors else "workflow failed"
            logger.error("Workflow generation failed for case '%s': %s", case.name, err_msg)
            return EvalRunRecord(
                case_name=case.name,
                template_name=case.template_name,
                variant_label=variant_label,
                model_used=result.metrics.model if result.metrics else "agent",
                prompt_rendered="(workflow agent mode)",
                judge=JudgeResult(error=err_msg),
                generation_time_s=gen_time,
                generation_metadata={
                    "mode": "agent",
                    "status": result.status.value,
                    "stage": result.stage.value,
                    "errors": [e.model_dump(mode="json") for e in result.errors],
                },
            )

        if result.artifacts is None:
            return EvalRunRecord(
                case_name=case.name,
                template_name=case.template_name,
                variant_label=variant_label,
                model_used=result.metrics.model if result.metrics else "agent",
                prompt_rendered="(workflow agent mode)",
                judge=JudgeResult(error="missing artifacts"),
                generation_time_s=gen_time,
                generation_metadata={"mode": "agent", "status": result.status.value},
            )

        frame_path = ""
        for key in sorted(result.artifacts.frame_paths):
            paths = result.artifacts.frame_paths[key]
            if paths:
                frame_path = paths[0]
                break

        if not frame_path:
            judge_result = JudgeResult(error="No frames generated")
        else:
            judge_image = Image.open(frame_path).convert("RGBA")
            style = p.get("style", "16-bit SNES RPG style")
            max_colors = int(p.get("max_colors", "16"))
            judge_result = await self._judge.evaluate(
                judge_image,
                asset_type=case.asset_type,
                style=style,
                max_colors=max_colors,
                expected_count=case.expected_count,
            )

        prompt_rendered = "(workflow agent mode)"
        if result.plan and result.plan.planned_prompts:
            prompt_rendered = result.plan.planned_prompts[0].prompt

        return EvalRunRecord(
            case_name=case.name,
            template_name=case.template_name,
            variant_label=variant_label,
            model_used=result.metrics.model if result.metrics else "agent",
            prompt_rendered=prompt_rendered,
            judge=judge_result,
            generation_time_s=gen_time,
            image_path=frame_path or result.artifacts.output_dir,
            generation_metadata={
                "mode": "agent",
                "status": result.status.value,
                "job_id": result.job_id,
                "stage": result.stage.value,
                "frame_count": result.artifacts.total_frames,
                "retry_count": result.metrics.retry_count if result.metrics else 0,
            },
        )

    @staticmethod
    def _split_csv(raw: str) -> list[str]:
        return [p.strip() for p in raw.split(",") if p.strip()]

    def _build_workflow_request(self, case: EvalCase) -> GenerationRequest:
        p = case.params
        style = p.get("style", "16-bit SNES RPG style")
        resolution = p.get("resolution", "64x64")
        max_colors = int(p.get("max_colors", "16"))

        if case.asset_type in ("character_directions", "character_animation"):
            direction_mode = 8 if "8dir" in case.template_name else 4
            if case.asset_type == "character_animation":
                animation_name = p.get("animation_name", "anim")
                frame_count = int(p.get("frame_count", "4"))
                animations = {
                    animation_name: {
                        "frame_count": frame_count,
                        "description": p.get("animation_description", animation_name),
                    }
                }
            else:
                animations = {"pose": {"frame_count": 1, "description": "single pose"}}

            return GenerationRequest(
                asset_type=AssetType.CHARACTER,
                name=case.name,
                objective=p.get("character_description", case.description or case.name),
                style=style,
                resolution=resolution,
                max_colors=max_colors,
                parameters={
                    "direction_mode": direction_mode,
                    "animations": animations,
                },
            )

        if case.asset_type == "tileset":
            tile_types = self._split_csv(p.get("tile_types", ""))
            return GenerationRequest(
                asset_type=AssetType.TILESET,
                name=case.name,
                objective=f"{p.get('biome', 'biome')} isometric tileset",
                style=style,
                resolution=f"{int(p.get('tile_width', '64'))}x{int(p.get('tile_height', '32'))}",
                max_colors=max_colors,
                expected_frames=max(1, len(tile_types)),
                parameters={
                    "tile_types": tile_types,
                    "biome": p.get("biome", ""),
                },
            )

        if case.asset_type == "items":
            items = self._split_csv(p.get("item_descriptions", ""))
            return GenerationRequest(
                asset_type=AssetType.ITEMS,
                name=case.name,
                objective=f"Item icon set: {p.get('item_descriptions', '')}",
                style=style,
                resolution=resolution,
                max_colors=max_colors,
                expected_frames=max(1, len(items)),
                parameters={"descriptions": items},
            )

        if case.asset_type == "effects":
            frame_count = int(p.get("frame_count", "6"))
            return GenerationRequest(
                asset_type=AssetType.EFFECT,
                name=case.name,
                objective=p.get("effect_description", case.description or case.name),
                style=style,
                resolution=resolution,
                max_colors=max_colors,
                expected_frames=frame_count,
                parameters={
                    "frame_count": frame_count,
                    "color_emphasis": p.get("color_emphasis", ""),
                },
            )

        if case.asset_type == "ui":
            elements = self._split_csv(p.get("element_descriptions", ""))
            return GenerationRequest(
                asset_type=AssetType.UI,
                name=case.name,
                objective=f"UI set: {p.get('element_descriptions', '')}",
                style=style,
                resolution=resolution,
                max_colors=max_colors,
                expected_frames=max(1, len(elements)),
                parameters={"descriptions": elements},
            )

        return GenerationRequest(
            asset_type=AssetType.CUSTOM,
            name=case.name,
            objective=case.description or case.name,
            style=style,
            resolution=resolution,
            max_colors=max_colors,
            expected_frames=max(1, case.expected_count),
            parameters={},
        )

    async def run_all(
        self,
        cases: list[EvalCase],
        variant_label: str = "default",
        repeats: int = 1,
        concurrency: int = 1,
        mode: Literal["direct", "agent"] = "direct",
    ) -> EvalRun:
        """Run all cases (optionally repeated) and return an EvalRun.

        Args:
            cases: Test cases to evaluate.
            variant_label: Label for this run.
            repeats: Number of times to repeat each case.
            concurrency: Max parallel generations (1 = sequential).
            mode: "direct" uses PromptBuilder+provider, "agent" uses the full agent pipeline.
        """
        run = EvalRun(
            variant_label=variant_label,
            model_name=self._settings.gemini_model
            if self._settings.provider == "gemini"
            else self._settings.openai_model,
            started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # Build flat task list preserving order
        tasks: list[tuple[int, EvalCase, int]] = []
        for repeat_idx in range(repeats):
            for i, case in enumerate(cases):
                tasks.append((repeat_idx * len(cases) + i, case, repeat_idx))

        total = len(tasks)

        run_fn = self.run_case_agent if mode == "agent" else self.run_case

        if concurrency <= 1:
            # Sequential (original behaviour)
            for idx, case, repeat_idx in tasks:
                logger.info(
                    "[%d/%d] Evaluating case '%s' (repeat %d, mode=%s)",
                    idx + 1, total, case.name, repeat_idx + 1, mode,
                )
                record = await run_fn(case, variant_label)
                run.records.append(record)
                self._log_record(record)
        else:
            # Parallel with bounded concurrency
            sem = asyncio.Semaphore(concurrency)
            results: list[tuple[int, EvalRunRecord]] = []
            completed = 0

            async def _worker(idx: int, case: EvalCase, repeat_idx: int) -> None:
                nonlocal completed
                async with sem:
                    logger.info(
                        "[started] case '%s' (repeat %d) — %d/%d queued",
                        case.name, repeat_idx + 1, idx + 1, total,
                    )
                    record = await run_fn(case, variant_label)
                    completed += 1
                    logger.info(
                        "[%d/%d done] case '%s'", completed, total, case.name,
                    )
                    self._log_record(record)
                    results.append((idx, record))

            await asyncio.gather(
                *(_worker(idx, case, rep) for idx, case, rep in tasks)
            )

            # Restore deterministic order
            for _, record in sorted(results, key=lambda x: x[0]):
                run.records.append(record)

        run.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Save results
        results_path = self._output_dir / variant_label / "results.json"
        run.save(results_path)
        logger.info("Evaluation results saved to %s", results_path)

        return run

    @staticmethod
    def _log_record(record: EvalRunRecord) -> None:
        if record.judge.error:
            logger.warning("  → ERROR: %s", record.judge.error)
        else:
            logger.info(
                "  → overall=%.2f, gen_time=%.1fs",
                record.judge.overall,
                record.generation_time_s,
            )
