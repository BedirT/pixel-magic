"""Tests for EvalRunner agent mode on the rewritten workflow executor."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image

from pixel_magic.config import Settings
from pixel_magic.evaluation.cases import EvalCase
from pixel_magic.evaluation.judge import DIMENSIONS, JudgeResult
from pixel_magic.evaluation.runner import EvalRunner
from pixel_magic.generation.prompts import PromptBuilder
from pixel_magic.providers.base import GenerationResult


def _make_strip(frame_count: int, *, bad_alpha: bool = False) -> Image.Image:
    frame_w, frame_h = 16, 16
    image = Image.new("RGBA", (frame_w * frame_count, frame_h), (0, 0, 0, 0))
    alpha = 120 if bad_alpha else 255
    for i in range(frame_count):
        base_x = i * frame_w
        color = (40, 70, 120, alpha)
        for y in range(2, 14):
            for x in range(2, 14):
                image.putpixel((base_x + x, y), color)
    return image


class DummyProvider:
    def __init__(self, *, bad_alpha: bool = False):
        self.bad_alpha = bad_alpha

    async def generate(self, prompt, config=None) -> GenerationResult:
        _ = config
        match = re.search(r"Horizontal strip of (\d+)", prompt)
        frame_count = int(match.group(1)) if match else 1
        image = _make_strip(frame_count, bad_alpha=self.bad_alpha)
        return GenerationResult(
            image=image,
            prompt_used=prompt,
            model_used="dummy-image-model",
            metadata={},
        )

    async def generate_with_references(
        self,
        prompt,
        reference_images,
        config=None,
    ) -> GenerationResult:
        _ = reference_images
        return await self.generate(prompt, config=config)

    async def close(self) -> None:
        return None


class DummyJudge:
    async def evaluate(self, image, asset_type, style, max_colors, expected_count) -> JudgeResult:
        _ = image, asset_type, style, max_colors, expected_count
        return JudgeResult(scores={dim: 0.8 for dim in DIMENSIONS}, feedback="ok")


def _items_case() -> EvalCase:
    return EvalCase(
        name="items_case",
        template_name="item_icons_batch",
        asset_type="items",
        params={
            "item_descriptions": "red potion, bronze key",
            "resolution": "32x32",
            "style": "16-bit RPG",
            "max_colors": "16",
        },
        expected_count=2,
    )


@pytest.mark.asyncio
async def test_run_case_agent_success(tmp_path):
    settings = Settings(output_dir=tmp_path, prompts_dir=Path("prompts"), OPENAI_API_KEY="")
    runner = EvalRunner(
        provider=DummyProvider(),
        prompts=PromptBuilder(),
        settings=settings,
        judge=DummyJudge(),
        output_dir=tmp_path / "eval",
    )

    record = await runner.run_case_agent(_items_case(), variant_label="agent_success")
    assert record.judge.error is None
    assert record.generation_metadata["mode"] == "agent"
    assert record.generation_metadata["status"] == "success"
    assert record.image_path is not None
    assert Path(record.image_path).exists()


@pytest.mark.asyncio
async def test_run_case_agent_failure_from_gate(tmp_path):
    settings = Settings(output_dir=tmp_path, prompts_dir=Path("prompts"), OPENAI_API_KEY="")
    runner = EvalRunner(
        provider=DummyProvider(bad_alpha=True),
        prompts=PromptBuilder(),
        settings=settings,
        judge=DummyJudge(),
        output_dir=tmp_path / "eval",
    )

    record = await runner.run_case_agent(_items_case(), variant_label="agent_failure")
    assert record.judge.error is not None
    assert record.generation_metadata["status"] == "failed"
