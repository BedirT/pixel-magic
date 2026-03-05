"""Top-level orchestrator agent that routes to specialist agents via handoffs."""

from __future__ import annotations

from agents import Agent

from pixel_magic.agents.character_agent import create_character_agent
from pixel_magic.agents.effect_agent import create_effect_agent
from pixel_magic.agents.item_agent import create_item_agent
from pixel_magic.agents.tileset_agent import create_tileset_agent
from pixel_magic.agents.ui_agent import create_ui_agent

ORCHESTRATOR_INSTRUCTIONS = """\
You are the Pixel Magic orchestrator. You route sprite generation requests
to the appropriate specialist agent.

## Routing Rules
- Character sprites (with directions and animations) → hand off to CharacterAgent
- Tileset / ground tiles → hand off to TilesetAgent
- Item icons or world sprites → hand off to ItemAgent
- Visual effects (explosions, magic, etc.) → hand off to EffectAgent
- UI elements (buttons, panels, HUD) → hand off to UIAgent

## How to Hand Off
Simply hand off the request to the appropriate agent with all the details.
The specialist will handle the full workflow including generation, QA, and saving.

Do NOT attempt to generate images yourself — always delegate to a specialist.
"""


def create_orchestrator(model: str, api_key: str) -> Agent:
    """Create the orchestrator agent with handoffs to all specialists."""
    character = create_character_agent(model, api_key)
    tileset = create_tileset_agent(model, api_key)
    item = create_item_agent(model, api_key)
    effect = create_effect_agent(model, api_key)
    ui = create_ui_agent(model, api_key)

    return Agent(
        name="Orchestrator",
        model=model,
        instructions=ORCHESTRATOR_INSTRUCTIONS,
        handoffs=[character, tileset, item, effect, ui],
    )
