"""Pre-defined evaluation test cases for each prompt template category."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    """A single evaluation scenario with known inputs."""

    name: str
    template_name: str
    asset_type: str  # judge rubric key: character_directions, character_animation, etc.
    params: dict[str, str] = field(default_factory=dict)
    expected_count: int = 1
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "template_name": self.template_name,
            "asset_type": self.asset_type,
            "params": self.params,
            "expected_count": self.expected_count,
        }


# ── Standard test cases ───────────────────────────────────────────────


def get_standard_cases() -> list[EvalCase]:
    """Return the canonical set of evaluation test cases."""
    return [
        # ── Character directions ──
        EvalCase(
            name="warrior_4dir",
            template_name="character_directions_4dir",
            asset_type="character_directions",
            params={
                "character_description": "a medieval knight with plate armor, sword, and shield",
                "style": "16-bit SNES RPG style",
                "resolution": "64x64",
                "max_colors": "16",
            },
            expected_count=2,
            description="Classic RPG knight in 4-direction (2 unique) mode",
        ),
        EvalCase(
            name="mage_4dir",
            template_name="character_directions_4dir",
            asset_type="character_directions",
            params={
                "character_description": "an elven mage in blue robes with a glowing staff",
                "style": "16-bit SNES RPG style",
                "resolution": "64x64",
                "max_colors": "16",
            },
            expected_count=2,
            description="Fantasy mage character with magic effects",
        ),
        EvalCase(
            name="thief_8dir",
            template_name="character_directions_8dir",
            asset_type="character_directions",
            params={
                "character_description": "a hooded rogue with dual daggers and a dark cloak",
                "style": "16-bit SNES RPG style",
                "resolution": "64x64",
                "max_colors": "16",
            },
            expected_count=5,
            description="Rogue character in 8-direction (5 unique) mode",
        ),

        # ── Character animation ──
        EvalCase(
            name="warrior_walk",
            template_name="character_animation",
            asset_type="character_animation",
            params={
                "character_description": "a medieval knight with plate armor",
                "animation_name": "walk",
                "animation_description": "walking cycle with swinging arms",
                "frame_count": "4",
                "direction": "south",
                "style": "16-bit SNES RPG style",
                "resolution": "64x64",
                "max_colors": "16",
            },
            expected_count=4,
            description="4-frame walk cycle facing south",
        ),
        EvalCase(
            name="mage_attack",
            template_name="character_animation",
            asset_type="character_animation",
            params={
                "character_description": "an elven mage in blue robes",
                "animation_name": "attack",
                "animation_description": "casting a spell with staff raised, magic particles emanating from the tip",
                "frame_count": "6",
                "direction": "south",
                "style": "16-bit SNES RPG style",
                "resolution": "64x64",
                "max_colors": "16",
            },
            expected_count=6,
            description="6-frame spell-casting animation",
        ),

        # ── Tilesets ──
        EvalCase(
            name="forest_ground",
            template_name="tileset_ground",
            asset_type="tileset",
            params={
                "biome": "temperate forest",
                "tile_types": "grass, dirt, stone path",
                "tile_width": "64",
                "tile_height": "32",
                "count": "3",
                "style": "16-bit isometric RPG style",
                "max_colors": "16",
            },
            expected_count=3,
            description="3 forest ground tiles — grass, dirt, stone",
        ),
        EvalCase(
            name="desert_ground",
            template_name="tileset_ground",
            asset_type="tileset",
            params={
                "biome": "scorching desert",
                "tile_types": "sand, cracked earth, sandstone",
                "tile_width": "64",
                "tile_height": "32",
                "count": "3",
                "style": "16-bit isometric RPG style",
                "max_colors": "12",
            },
            expected_count=3,
            description="3 desert ground tiles",
        ),

        # ── Items ──
        EvalCase(
            name="rpg_weapons",
            template_name="item_icons_batch",
            asset_type="items",
            params={
                "item_descriptions": "iron sword, wooden bow, fire staff",
                "count": "3",
                "resolution": "32x32",
                "style": "16-bit SNES RPG style",
                "max_colors": "16",
            },
            expected_count=3,
            description="3 weapon icons at 32x32",
        ),
        EvalCase(
            name="consumables",
            template_name="item_icons_batch",
            asset_type="items",
            params={
                "item_descriptions": "red health potion, blue mana potion, golden key, treasure chest",
                "count": "4",
                "resolution": "32x32",
                "style": "16-bit SNES RPG style",
                "max_colors": "16",
            },
            expected_count=4,
            description="4 consumable/key item icons",
        ),

        # ── Effects ──
        EvalCase(
            name="fire_explosion",
            template_name="effect_animation",
            asset_type="effects",
            params={
                "effect_description": "fiery explosion",
                "frame_count": "6",
                "resolution": "64x64",
                "style": "16-bit pixel art",
                "max_colors": "12",
                "color_emphasis": "red, orange, yellow",
            },
            expected_count=6,
            description="6-frame fire explosion effect",
        ),
        EvalCase(
            name="heal_spell",
            template_name="effect_animation",
            asset_type="effects",
            params={
                "effect_description": "green healing aura with sparkles",
                "frame_count": "4",
                "resolution": "64x64",
                "style": "16-bit pixel art",
                "max_colors": "10",
                "color_emphasis": "green, white, gold",
            },
            expected_count=4,
            description="4-frame healing spell effect",
        ),

        # ── UI ──
        EvalCase(
            name="rpg_ui",
            template_name="ui_elements_batch",
            asset_type="ui",
            params={
                "element_descriptions": "health bar frame, mana bar frame, inventory slot",
                "count": "3",
                "resolution": "64x64",
                "style": "16-bit RPG UI style",
                "max_colors": "8",
            },
            expected_count=3,
            description="3 RPG UI elements",
        ),
    ]
