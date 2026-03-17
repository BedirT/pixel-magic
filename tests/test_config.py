"""Tests for config module."""

from pixel_magic.config import Settings, get_settings, reset_settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.provider == "openai"
        assert s.direction_mode == 4
        assert s.palette_size == 16
        assert s.alpha_policy == "binary"

    def test_api_key_gemini(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        s = Settings(provider="gemini")
        assert s.get_api_key() == "test-key"

    def test_api_key_openai(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
        s = Settings(provider="openai")
        assert s.get_api_key() == "oai-key"


class TestSingleton:
    def test_get_settings_returns_same(self):
        reset_settings()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        reset_settings()
