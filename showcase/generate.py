#!/usr/bin/env python3
"""Generate all Ember Depths showcase assets and track costs.

Usage:
    uv run python showcase/generate.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@dataclass
class CommandCost:
    """Cost tracking for a single CLI command."""
    command: str
    api_calls: int = 0
    prompt_tokens: int = 0
    candidates_tokens: int = 0
    total_tokens: int = 0
    elapsed_sec: float = 0.0
    images_generated: int = 0
    error: str | None = None


@dataclass
class CostTracker:
    """Accumulates costs across all commands."""
    commands: list[CommandCost] = field(default_factory=list)

    def add(self, cost: CommandCost) -> None:
        self.commands.append(cost)

    @property
    def total_api_calls(self) -> int:
        return sum(c.api_calls for c in self.commands)

    @property
    def total_tokens(self) -> int:
        return sum(c.total_tokens for c in self.commands)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.commands)

    @property
    def total_candidates_tokens(self) -> int:
        return sum(c.candidates_tokens for c in self.commands)

    @property
    def total_images(self) -> int:
        return sum(c.images_generated for c in self.commands)

    @property
    def total_elapsed(self) -> float:
        return sum(c.elapsed_sec for c in self.commands)

    def print_report(self) -> None:
        print("\n" + "=" * 80)
        print("SHOWCASE GENERATION COST REPORT")
        print("=" * 80)

        # Per-command breakdown
        print(f"\n{'Command':<50} {'Calls':>6} {'Images':>7} {'Tokens':>10} {'Time':>8}")
        print("-" * 80)
        for c in self.commands:
            status = "FAIL" if c.error else "OK"
            time_str = f"{c.elapsed_sec:.1f}s"
            print(f"{c.command:<50} {c.api_calls:>6} {c.images_generated:>7} {c.total_tokens:>10} {time_str:>8}  {status}")
            if c.error:
                print(f"  Error: {c.error}")

        # Totals
        print("-" * 80)
        print(f"{'TOTAL':<50} {self.total_api_calls:>6} {self.total_images:>7} {self.total_tokens:>10} {self.total_elapsed:>7.1f}s")

        # Token breakdown
        print(f"\nToken breakdown:")
        print(f"  Prompt tokens:    {self.total_prompt_tokens:>10}")
        print(f"  Output tokens:    {self.total_candidates_tokens:>10}")
        print(f"  Total tokens:     {self.total_tokens:>10}")

        # Save as JSON
        report_path = Path(__file__).parent / "cost_report.json"
        report = {
            "commands": [
                {
                    "command": c.command,
                    "api_calls": c.api_calls,
                    "images_generated": c.images_generated,
                    "prompt_tokens": c.prompt_tokens,
                    "candidates_tokens": c.candidates_tokens,
                    "total_tokens": c.total_tokens,
                    "elapsed_sec": round(c.elapsed_sec, 1),
                    "error": c.error,
                }
                for c in self.commands
            ],
            "totals": {
                "api_calls": self.total_api_calls,
                "images_generated": self.total_images,
                "prompt_tokens": self.total_prompt_tokens,
                "candidates_tokens": self.total_candidates_tokens,
                "total_tokens": self.total_tokens,
                "elapsed_sec": round(self.total_elapsed, 1),
            },
        }
        report_path.write_text(json.dumps(report, indent=2))
        print(f"\nFull report saved to: {report_path}")


# Monkey-patch the provider to count calls
_original_generate_content = None
_call_counter = {"api_calls": 0, "prompt_tokens": 0, "candidates_tokens": 0, "total_tokens": 0, "images": 0}


def _reset_counter():
    _call_counter["api_calls"] = 0
    _call_counter["prompt_tokens"] = 0
    _call_counter["candidates_tokens"] = 0
    _call_counter["total_tokens"] = 0
    _call_counter["images"] = 0


def _patch_provider():
    """Wrap GeminiProvider._generate_content to count API calls."""
    from pixel_magic.providers.gemini import GeminiProvider

    original = GeminiProvider._generate_content

    async def tracked_generate(self, contents, prompt_text, aspect_ratio=None, image_size=None):
        result = await original(self, contents, prompt_text, aspect_ratio, image_size)
        _call_counter["api_calls"] += 1
        _call_counter["images"] += 1
        _call_counter["prompt_tokens"] += result.usage.prompt_tokens
        _call_counter["candidates_tokens"] += result.usage.candidates_tokens
        _call_counter["total_tokens"] += result.usage.total_tokens
        return result

    GeminiProvider._generate_content = tracked_generate


def run_command(args: list[str], tracker: CostTracker) -> None:
    """Run a pixel-magic CLI command and track its cost."""
    cmd_str = "pixel-magic " + " ".join(args)
    print(f"\n{'='*60}")
    print(f"Running: {cmd_str}")
    print(f"{'='*60}")

    _reset_counter()
    start = time.monotonic()

    try:
        from pixel_magic.__main__ import main as cli_main

        old_argv = sys.argv
        sys.argv = ["pixel-magic"] + args
        try:
            cli_main()
        finally:
            sys.argv = old_argv

        elapsed = time.monotonic() - start
        cost = CommandCost(
            command=cmd_str,
            api_calls=_call_counter["api_calls"],
            images_generated=_call_counter["images"],
            prompt_tokens=_call_counter["prompt_tokens"],
            candidates_tokens=_call_counter["candidates_tokens"],
            total_tokens=_call_counter["total_tokens"],
            elapsed_sec=elapsed,
        )
        print(f"  Done in {elapsed:.1f}s — {cost.api_calls} API calls, {cost.total_tokens} tokens")

    except Exception as e:
        elapsed = time.monotonic() - start
        cost = CommandCost(
            command=cmd_str,
            api_calls=_call_counter["api_calls"],
            images_generated=_call_counter["images"],
            prompt_tokens=_call_counter["prompt_tokens"],
            candidates_tokens=_call_counter["candidates_tokens"],
            total_tokens=_call_counter["total_tokens"],
            elapsed_sec=elapsed,
            error=str(e),
        )
        print(f"  FAILED after {elapsed:.1f}s: {e}")

    tracker.add(cost)


SHOWCASE_DIR = Path(__file__).parent / "assets"


# All showcase commands as arg lists
COMMANDS: list[list[str]] = [
    # --- Characters ---
    ["generate", "--name", "ember-knight",
     "--description", "medieval knight in dark steel armor with orange flame accents, wielding a flaming longsword, red cape",
     "--directions", "4", "--tiles", "1", "--sizes", "32,64",
     "--output-dir", str(SHOWCASE_DIR / "characters")],

    ["generate", "--name", "forest-goblin",
     "--description", "small green-skinned goblin with a wooden club, leaf hat, tattered brown loincloth",
     "--directions", "4", "--chromakey", "blue", "--sizes", "32,64",
     "--output-dir", str(SHOWCASE_DIR / "characters")],

    ["generate", "--name", "cave-bat",
     "--description", "large purple bat with glowing red eyes, leathery wings spread wide, fangs visible",
     "--directions", "4", "--sizes", "32,64",
     "--output-dir", str(SHOWCASE_DIR / "characters")],

    ["generate", "--name", "fire-imp",
     "--description", "tiny red imp wreathed in orange flame, pointed horns, mischievous grin, holding a fireball",
     "--directions", "4", "--sizes", "32,64",
     "--output-dir", str(SHOWCASE_DIR / "characters")],

    ["generate", "--name", "lava-dragon",
     "--description", "ancient red dragon with molten cracks glowing orange across its scales, massive wings, curled tail",
     "--directions", "4", "--tiles", "4", "--sizes", "64,128",
     "--output-dir", str(SHOWCASE_DIR / "characters")],

    # --- Character animations (4-dir gives front_left/back_right) ---
    ["animate", "--name", "ember-knight", "--animation", "walk", "--frames", "6",
     "--direction", "front_left",
     "--platform", "--output-dir", str(SHOWCASE_DIR / "characters")],

    ["animate", "--name", "ember-knight", "--animation", "idle", "--frames", "4",
     "--direction", "front_left",
     "--platform", "--output-dir", str(SHOWCASE_DIR / "characters")],

    ["animate", "--name", "ember-knight", "--animation", "attack", "--frames", "5",
     "--direction", "front_left",
     "--platform", "--no-loop", "--output-dir", str(SHOWCASE_DIR / "characters")],

    # --- Tiles ---
    ["tile", "--theme", "custom",
     "--types", "grass,moss stone,cracked path,water puddle,flowers,root-covered stone",
     "--style", "16-bit SNES RPG style, overgrown ancient ruins",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "tiles")],

    ["tile", "--theme", "custom",
     "--types", "dark stone,crystal floor,wet stone,underground water,gravel,glowing moss",
     "--style", "16-bit SNES RPG style, underground cave",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "tiles")],

    ["tile", "--theme", "custom",
     "--types", "basalt,lava,cracked obsidian,ash,magma vein,cooled lava",
     "--style", "16-bit SNES RPG style, volcanic hellscape",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "tiles")],

    # --- Objects ---
    ["object", "--preset", "custom",
     "--names", "broken pillar,vine archway,ancient chest,moss boulder,mushroom,overgrown statue",
     "--description", "overgrown ancient ruins in a forest",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "objects")],

    ["object", "--preset", "custom",
     "--names", "crystal cluster,stalactite,mine cart,mushroom patch,bones pile,cave torch",
     "--description", "underground cave and abandoned mine",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "objects")],

    ["object", "--preset", "custom",
     "--names", "lava fountain,obsidian spike,fire brazier,dragon egg,charred tree,magma crystal",
     "--description", "volcanic hellscape with molten lava",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "objects")],

    # --- Effects ---
    ["effect", "--name", "sword-slash", "--frames", "5", "--no-loop",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "effects")],

    ["effect", "--name", "fire-explosion", "--frames", "6", "--no-loop",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "effects")],

    ["effect", "--name", "magic-shield", "--frames", "6", "--loop",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "effects")],

    ["effect", "--name", "healing-glow", "--frames", "6", "--loop",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "effects")],

    ["effect", "--name", "lava-bubble", "--frames", "5", "--loop",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "effects")],

    ["effect", "--name", "poison-cloud", "--frames", "6", "--loop",
     "--sizes", "32,64", "--output-dir", str(SHOWCASE_DIR / "effects")],
]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate Ember Depths showcase assets")
    parser.add_argument("--start-from", type=int, default=1,
                        help="Start from command N (1-indexed, default: 1)")
    parser.add_argument("--only", type=int, default=None,
                        help="Run only command N (1-indexed)")
    opts = parser.parse_args()

    _patch_provider()
    tracker = CostTracker()

    start_idx = opts.start_from - 1
    if opts.only is not None:
        commands_to_run = [COMMANDS[opts.only - 1]]
    else:
        commands_to_run = COMMANDS[start_idx:]

    for cmd_args in commands_to_run:
        run_command(cmd_args, tracker)

    tracker.print_report()


if __name__ == "__main__":
    main()
