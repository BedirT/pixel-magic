"""Minimal configuration via environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PIXEL_MAGIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")

    # Gemini
    gemini_image_model: str = "gemini-3.1-flash-image-preview"

    # Generation defaults
    direction_mode: int = 4
    image_size: str = "1024x1024"
    default_resolution: str = "64x64"
    max_colors: int = 16
    chromakey_color: Literal["green", "blue"] = "green"

    # Output
    output_dir: Path = Path("output")
