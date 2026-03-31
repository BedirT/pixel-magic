"""Shared constants and helpers for prompt templates."""

from __future__ import annotations


CHROMAKEY_HEX: dict[str, str] = {
    "green": "#00FF00",
    "blue": "#0000FF",
    "pink": "#FF00FF",
}

VIEWS_4DIR: list[dict[str, str]] = [
    {
        "position": "left",
        "facing": "south_west",
        "description": "Front 3/4 isometric view facing south-west — face and chest visible from above",
    },
    {
        "position": "right",
        "facing": "north_east",
        "description": "Rear 3/4 isometric view facing north-east — back and top of head visible",
    },
]

VIEWS_8DIR: list[dict[str, str]] = [
    {
        "position": "far_left",
        "facing": "north",
        "description": "Full rear isometric view facing north — top of head and back visible",
    },
    {
        "position": "center_left",
        "facing": "north_east",
        "description": "Rear 3/4 isometric view facing north-east — back and right shoulder visible from above",
    },
    {
        "position": "center",
        "facing": "east",
        "description": "Side isometric view facing east — right profile visible",
    },
    {
        "position": "center_right",
        "facing": "south_east",
        "description": "Front 3/4 isometric view facing south-east — face and chest visible from above",
    },
    {
        "position": "far_right",
        "facing": "south",
        "description": "Front isometric view facing south — face and front of body visible",
    },
]

POSITION_NAMES_4DIR: list[str] = ["left platform", "right platform"]
POSITION_NAMES_8DIR: list[str] = [
    "top-left platform", "top-center platform", "top-right platform",
    "bottom-left platform", "bottom-right platform",
]

ANIMATION_DESCRIPTIONS: dict[str, str] = {
    "walk": "a walk cycle — the character takes steps forward, legs alternating, arms swinging naturally. Each frame shows a different phase of the stride.",
    "idle": "an idle/breathing animation — very subtle motion, the character shifts weight slightly and breathes. Minimal movement.",
    "attack": "an attack animation — the character winds up, strikes with their weapon at full extension, then follows through.",
    "run": "a run cycle — similar to walk but faster, with more exaggerated leg extension and body lean.",
    "cast": "a spell casting animation — the character raises their hands, channels energy, and releases a spell.",
    "hurt": "a hurt/flinch animation — the character recoils from an impact, staggers back with head and torso tilting away from the hit.",
    "death": "a death animation — the character collapses, falling to the ground and ending in a prone or crumpled pose.",
    "dodge": "a dodge/evade animation — the character quickly sidesteps or rolls to one side, body low, then recovers to standing.",
    "jump": "a jump animation — the character crouches, springs upward with arms rising, hangs at the peak, then descends and lands.",
    "block": "a block/guard animation — the character raises a shield or weapon defensively, bracing for impact with a wide stance.",
}

OBJECT_ANIMATION_DESCRIPTIONS: dict[str, str] = {
    "sway": "a gentle swaying animation — the object rocks side to side as if blown by wind. Subtle, rhythmic motion. The base stays planted.",
    "flicker": "a flickering animation — the flame or light source pulses and shifts shape between frames. Organic, jittery movement.",
    "burn": "a burning animation — flames dance and smoke wisps rise. The fire shape changes each frame while the base stays grounded.",
    "pulse": "a pulsing/glowing animation — the object brightens and dims rhythmically. Subtle scale or luminosity shifts.",
    "open": "an opening animation — the object's lid, door, or cover swings open revealing the interior.",
    "bob": "a bobbing animation — the object gently floats up and down in place. Smooth, continuous vertical motion.",
    "spin": "a rotating animation — the object turns in place, showing different facets each frame.",
}

EFFECT_ANIMATION_DESCRIPTIONS: dict[str, str] = {
    "explosion": "an explosion — starts as a bright flash, expands outward with fire and debris, then dissipates into smoke and embers.",
    "slash": "a slash effect — a sharp arc of energy sweeps across the frame, trailing light, then fades away.",
    "shield_hit": "a shield impact — concentric rings of energy pulse outward from a central hit point, then fade.",
    "magic_circle": "a rotating magic circle — glowing runes and geometric patterns spin and pulse with arcane energy.",
    "healing_aura": "a healing aura — gentle green/white particles rise upward, glowing warmly, in a cyclical pattern.",
    "energy_ball": "an energy ball — a sphere of crackling energy pulses, sparks, and shifts shape between frames.",
    "smoke": "a smoke puff — a cloud billows outward from the center, expanding and thinning as it dissipates.",
    "fire": "a fire animation — flames dance and flicker, changing shape organically each frame while maintaining the same base position.",
    "water_splash": "a water splash — droplets erupt upward and arc outward in all directions, then settle.",
    "poison_cloud": "a poison cloud — sickly green gas swirls and undulates in place with subtle drifting particles.",
    "stun_stars": "stun stars — small stars orbit in a circle above, twinkling and spinning rhythmically.",
    "buff_glow": "a buff glow — a radiant aura pulses outward rhythmically, with rising energy particles.",
}


def background_instruction(chromakey_color: str = "green") -> str:
    """One-line background instruction for prompts."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    return f"solid {chromakey_color} ({hex_color}) background (every non-sprite pixel must be exactly {hex_color})"


def background_rule(chromakey_color: str = "green") -> str:
    """Full background rule for prompts."""
    hex_color = CHROMAKEY_HEX.get(chromakey_color, "#00FF00")
    return (
        f"The ENTIRE image background MUST be solid {chromakey_color} ({hex_color}) "
        f"— no transparency, no gradients, no shadows, just flat {chromakey_color}"
    )
