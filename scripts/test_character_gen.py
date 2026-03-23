"""Quick script to test real character generation with the JSON multi-view approach."""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pixel_magic.config import Settings
from pixel_magic.workflow.executor import WorkflowExecutor
from pixel_magic.workflow.models import AssetType, GenerationRequest, JobStatus
from pixel_magic.workflow.provider_adapter import ProviderAdapter, create_provider
from pixel_magic.workflow.agents import AgentRuntime


async def run_character(name: str, description: str, direction_mode: int = 4):
    settings = Settings()
    provider_impl = create_provider(settings)
    provider = ProviderAdapter(provider=provider_impl, settings=settings)
    agents = AgentRuntime(
        model=settings.agent_model,
        api_key=settings.openai_api_key,
        provider=settings.provider,
        chromakey_color=settings.chromakey_color,
    )
    executor = WorkflowExecutor(settings=settings, provider=provider, agents=agents)

    request = GenerationRequest(
        asset_type=AssetType.CHARACTER,
        name=name,
        objective=description,
        style="16-bit SNES RPG style",
        resolution="64x64",
        max_colors=16,
        parameters={
            "direction_mode": direction_mode,
            "palette_hint": "",
        },
    )

    print(f"\n{'='*60}")
    print(f"Generating: {name}")
    print(f"Description: {description}")
    print(f"Direction mode: {direction_mode} ({2 if direction_mode == 4 else 5} views)")
    print(f"Provider: {settings.provider} / {provider.model_name}")
    print(f"{'='*60}")

    # Show the JSON prompt that will be sent
    plan_prompt = request
    from pixel_magic.workflow.tools import build_plan_from_request
    plan = build_plan_from_request(request, provider=settings.provider, chromakey_color=settings.chromakey_color)
    print(f"\nJSON prompt (first 500 chars):")
    print(plan.planned_prompts[0].prompt[:500])
    print("...")

    print(f"\nRunning full pipeline...")
    result = await executor.run(request)

    print(f"\nStatus: {result.status.value}")
    if result.status == JobStatus.SUCCESS:
        print(f"Output dir: {result.artifacts.output_dir}")
        print(f"Generated frames: {result.artifacts.generated_total_frames}")
        print(f"Total frames (with mirrors): {result.artifacts.total_frames}")
        print(f"Atlas: {result.artifacts.atlas_path}")
        for group_name, paths in result.artifacts.frame_paths.items():
            print(f"  {group_name}: {len(paths)} frame(s)")
            for p in paths:
                print(f"    -> {p}")
    else:
        print(f"Errors:")
        for err in result.errors:
            print(f"  [{err.stage.value}] {err.message}")
            if err.data:
                print(f"    {err.data}")

    if result.metrics:
        print(f"\nMetrics:")
        print(f"  Generation calls: {result.metrics.total_generation_calls}")
        print(f"  Duration: {result.metrics.duration_s:.1f}s")

    return result


async def main():
    # Test 1: Simple character, 4-dir (2 views)
    r1 = await run_character(
        "backpack_kid",
        "A young child with messy dark hair, light blue t-shirt, dark red shorts, white socks, red sneakers, and an oversized orange school backpack",
        direction_mode=4,
    )

    # Test 2: Fantasy character, 4-dir
    r2 = await run_character(
        "fire_mage",
        "A fire mage in flowing crimson robes with golden trim, holding a staff topped with a flickering flame crystal, pointed hat, long white beard",
        direction_mode=4,
    )

    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"backpack_kid: {r1.status.value}")
    print(f"fire_mage:    {r2.status.value}")

    if r1.status == JobStatus.SUCCESS:
        print(f"\nbackpack_kid output: {r1.artifacts.output_dir}")
    if r2.status == JobStatus.SUCCESS:
        print(f"fire_mage output:    {r2.artifacts.output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
