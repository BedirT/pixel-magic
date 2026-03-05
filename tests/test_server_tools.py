"""MCP tool-surface tests for workflow-native server behavior."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest
from PIL import Image

from pixel_magic.config import Settings
from pixel_magic.providers.base import GenerationResult
from pixel_magic.server import extend_character_animation, mcp
from pixel_magic.workflow import AgentRuntime, ProviderAdapter, WorkflowExecutor


def _make_strip(frame_count: int, frame_size: tuple[int, int] = (16, 16)) -> Image.Image:
    width = frame_count * frame_size[0]
    height = frame_size[1]
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for i in range(frame_count):
        base_x = i * frame_size[0]
        for y in range(2, 14):
            for x in range(2, 14):
                image.putpixel((base_x + x, y), (45, 80, 140, 255))
    return image


class DummyProvider:
    async def generate(self, prompt, config=None) -> GenerationResult:
        _ = config
        match = re.search(r"Horizontal strip of (\d+) frames", prompt)
        frame_count = int(match.group(1)) if match else 1
        image = _make_strip(frame_count)
        return GenerationResult(
            image=image,
            prompt_used=prompt,
            model_used="dummy",
            metadata={"frame_count": frame_count},
        )

    async def generate_with_references(
        self,
        prompt,
        reference_images,
        config=None,
    ) -> GenerationResult:
        _ = reference_images
        return await self.generate(prompt, config=config)

    async def evaluate_image(self, image, prompt) -> dict:
        _ = image, prompt
        return {"overall": 1.0}

    async def start_session(self, config=None):  # pragma: no cover - not needed in test
        _ = config
        raise NotImplementedError

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_mcp_registry_contains_extend_and_not_legacy():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert "extend_character_animation" in names
    assert "add_character_animation" not in names


@pytest.mark.asyncio
async def test_extend_character_animation_smoke(monkeypatch, tmp_path):
    reference_path = tmp_path / "ref.png"
    _make_strip(1).save(reference_path)

    settings = Settings(output_dir=tmp_path, palettes_dir=tmp_path, OPENAI_API_KEY="")
    provider = DummyProvider()
    adapter = ProviderAdapter(provider, settings)
    agents = AgentRuntime(model=settings.agent_model, api_key="")
    executor = WorkflowExecutor(settings=settings, provider=adapter, agents=agents)
    state = SimpleNamespace(workflow_executor=executor)

    monkeypatch.setattr("pixel_magic.server._get_state", lambda _ctx: state)
    response = await extend_character_animation(
        ctx=None,
        character_name="knight",
        animation_name="jump",
        reference_image_path=str(reference_path),
        frame_count=2,
        description="jump loop",
        direction_mode=4,
    )
    payload = json.loads(response)

    assert payload["status"] == "success"
    assert payload["artifacts"]["total_frames"] == 4
    assert payload["metrics"]["retry_count"] == 0
    assert payload["output_paths"]
