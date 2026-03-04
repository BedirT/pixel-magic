"""Application configuration via Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pixel Magic configuration — loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="PIXEL_MAGIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider
    provider: Literal["gemini", "openai"] = "gemini"

    # Gemini settings
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    gemini_model: str = "gemini-2.0-flash-exp"
    gemini_image_model: str = "gemini-2.0-flash-exp"
    gemini_thinking_level: Literal["minimal", "high"] = "minimal"

    # OpenAI settings
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = "gpt-image-1"
    openai_quality: Literal["low", "medium", "high"] = "medium"

    # Generation defaults
    direction_mode: Literal[4, 8] = 4
    image_size: str = "1024x1024"
    default_resolution: str = "64x64"
    palette_size: int = 16
    alpha_policy: Literal["binary", "keep8bit"] = "binary"
    alpha_threshold: float = 0.5

    # QA
    qa_vision_enabled: bool = True
    qa_max_retries: int = 3
    qa_min_vision_score: float = 0.7

    # Pipeline
    grid_range_min: int = 2
    grid_range_max: int = 32
    grid_confidence_threshold: float = 0.7
    dither_type: Literal["none", "ordered", "error_diffusion"] = "none"
    dither_strength: float = 0.3
    min_island_size: int = 2
    max_hole_size: int = 2
    enforce_outline: bool = False

    # Export
    atlas_padding: int = 1
    export_individual_pngs: bool = True
    export_godot_tres: bool = True

    # Paths
    output_dir: Path = Path("output")
    prompts_dir: Path = Path("prompts")
    palettes_dir: Path = Path("palettes")

    def get_api_key(self) -> str:
        """Return the active provider's API key."""
        if self.provider == "gemini":
            return self.google_api_key
        return self.openai_api_key


# Global settings instance — re-create if you need different config
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset global settings (for testing or reconfiguration)."""
    global _settings
    _settings = None
