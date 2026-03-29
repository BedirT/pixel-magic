"""Effect animation — presets and resolution for subjectless VFX sprites."""

from __future__ import annotations


# Predefined effect presets
EFFECT_PRESETS: dict[str, list[str]] = {
    "combat": ["explosion", "slash", "shield_hit"],
    "magic": ["magic_circle", "healing_aura", "energy_ball"],
    "nature": ["smoke", "fire", "water_splash"],
    "status": ["poison_cloud", "stun_stars", "buff_glow"],
}

# Effects that naturally loop (vs. one-shot like explosions)
_NATURALLY_LOOPING: set[str] = {
    "magic_circle",
    "healing_aura",
    "energy_ball",
    "fire",
    "poison_cloud",
    "stun_stars",
    "buff_glow",
}


def resolve_effect_labels(
    name: str | None,
    preset: str | None,
    custom_names: str,
) -> tuple[str, list[str]]:
    """Resolve CLI args into a set name and list of effect labels.

    Returns (set_name, labels).
    """
    if name:
        return name, [name]

    if preset is None:
        raise ValueError("Either --name or --preset is required")

    if preset == "custom":
        labels = [t.strip() for t in custom_names.split(",") if t.strip()]
        if not labels:
            raise ValueError("--names is required when using --preset custom")
        return "custom", labels

    labels = EFFECT_PRESETS.get(preset, [])
    if not labels:
        available = ", ".join(sorted(EFFECT_PRESETS.keys()))
        raise ValueError(f"Unknown preset '{preset}'. Available: {available}, custom")
    return preset, labels


def infer_loop_default(effect_name: str) -> bool:
    """Infer whether an effect should loop by default."""
    return effect_name in _NATURALLY_LOOPING
