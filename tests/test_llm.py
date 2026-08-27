"""Provider-registry tests."""

import pytest

from src import llm


class TestProviderRegistry:
    def test_every_provider_declares_both_models(self):
        for name, spec in llm.PROVIDERS.items():
            assert spec.chat_model, f"{name} has no chat model"
            assert spec.vision_model, f"{name} has no vision model"

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "nope")
        with pytest.raises(llm.ProviderError):
            llm.active_provider()

    def test_defaults_to_gemini(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        assert llm.active_provider() == "gemini"

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("VISION_MODEL", "gemini/custom-model")
        assert llm.spec().vision_model == "gemini/custom-model"

    def test_missing_key_is_a_clear_error(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(llm.ProviderError, match="GEMINI_API_KEY"):
            llm._api_key(llm.spec())

    def test_local_provider_needs_no_key(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        assert llm._api_key(llm.spec()) is None


class TestEncodeImage:
    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            llm.encode_image("/tmp/definitely-not-here.jpg")

    def test_encodes_a_real_file(self, tmp_path):
        f = tmp_path / "x.jpg"
        f.write_bytes(b"hello")
        assert llm.encode_image(str(f)) == "aGVsbG8="
