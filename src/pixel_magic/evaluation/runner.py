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
from pixel_magic.models.asset import (
    AnimationDef,
    CharacterSpec,
    DEFAULT_ANIMATIONS,
    EffectSpec,
    ItemSpec,
    TilesetSpec,
    UIElementSpec,
)
from pixel_magic.providers.base import GenerationConfig, ImageProvider

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
        """Run a single evaluation case through the agent pipeline."""
        from pixel_magic.agents.runner import (
            run_character_generation,
            run_effect_generation,
            run_item_generation,
            run_tileset_generation,
            run_ui_generation,
        )

        img_dir = self._output_dir / variant_label / "images" / case.name
        img_dir.mkdir(parents=True, exist_ok=True)

        t0 = time.monotonic()
        frames: list[Image.Image] = []

        try:
            asset_type = case.asset_type
            p = case.params

            if asset_type in ("character_directions", "character_animation"):
                spec = CharacterSpec(
                    name=case.name,
                    description=p.get("character_description", ""),
                    style=p.get("style", "16-bit SNES RPG style"),
                    resolution=p.get("resolution", "64x64"),
                    max_colors=int(p.get("max_colors", "16")),
                    direction_mode=4,
                    animations=DEFAULT_ANIMATIONS,
                )
                clips = await run_character_generation(
                    self._provider, self._settings, spec, img_dir,
                )
                for anim_clips in clips.values():
                    for clip in anim_clips:
                        for f in clip.frames:
                            frames.append(f.image)
            elif asset_type == "tileset":
                tile_types = [t.strip() for t in p.get("tile_types", "").split(",")]
                spec = TilesetSpec(
                    name=case.name,
                    biome=p.get("biome", ""),
                    tile_types=tile_types,
                    tile_width=int(p.get("tile_width", "64")),
                    tile_height=int(p.get("tile_height", "32")),
                    style=p.get("style", "16-bit isometric RPG style"),
                    max_colors=int(p.get("max_colors", "16")),
                )
                assets = await run_tileset_generation(
                    self._provider, self._settings, spec, img_dir,
                )
                frames = [a.image for a in assets]
            elif asset_type == "items":
                descriptions = [d.strip() for d in p.get("item_descriptions", "").split(",")]
                spec = ItemSpec(
                    descriptions=descriptions,
                    resolution=p.get("resolution", "32x32"),
                    style=p.get("style", "16-bit SNES RPG style"),
                    max_colors=int(p.get("max_colors", "16")),
                )
                assets = await run_item_generation(
                    self._provider, self._settings, spec, img_dir,
                )
                frames = [a.image for a in assets]
            elif asset_type == "effects":
                spec = EffectSpec(
                    description=p.get("effect_description", ""),
                    frame_count=int(p.get("frame_count", "6")),
                    resolution=p.get("resolution", "64x64"),
                    style=p.get("style", "16-bit pixel art"),
                    max_colors=int(p.get("max_colors", "12")),
                    color_emphasis=p.get("color_emphasis", ""),
                )
                clip = await run_effect_generation(
                    self._provider, self._settings, spec, img_dir,
                )
                frames = [f.image for f in clip.frames]
            elif asset_type == "ui":
                descriptions = [d.strip() for d in p.get("element_descriptions", "").split(",")]
                spec = UIElementSpec(
                    descriptions=descriptions,
                    resolution=p.get("resolution", "64x64"),
                    style=p.get("style", "16-bit RPG UI style"),
                    max_colors=int(p.get("max_colors", "8")),
                )
                assets = await run_ui_generation(
                    self._provider, self._settings, spec, img_dir,
                )
                frames = [a.image for a in assets]
            else:
                raise ValueError(f"Unknown asset_type: {asset_type}")

            gen_time = time.monotonic() - t0
        except Exception as e:
            logger.error("Agent generation failed for case '%s': %s", case.name, e)
            return EvalRunRecord(
                case_name=case.name,
                template_name=case.template_name,
                variant_label=variant_label,
                model_used="agent",
                prompt_rendered="(agent mode)",
                judge=JudgeResult(error=str(e)),
                generation_metadata={"error": str(e), "mode": "agent"},
            )

        # Judge the first frame (or a composite if multiple)
        if frames:
            judge_image = frames[0]
            style = p.get("style", "16-bit SNES RPG style")
            max_colors = int(p.get("max_colors", "16"))
            judge_result = await self._judge.evaluate(
                judge_image,
                asset_type=case.asset_type,
                style=style,
                max_colors=max_colors,
                expected_count=1,
            )
        else:
            judge_result = JudgeResult(error="No frames generated")

        return EvalRunRecord(
            case_name=case.name,
            template_name=case.template_name,
            variant_label=variant_label,
            model_used="agent",
            prompt_rendered="(agent mode)",
            judge=judge_result,
            generation_time_s=gen_time,
            image_path=str(img_dir),
            generation_metadata={"mode": "agent", "frame_count": len(frames)},
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
