"""Provider-agnostic LLM layer.

This module is the whole point of the project: every model call in
the app goes through here, so switching from a free Gemini key to a
fully offline Ollama box is one line in `.env` -- no code changes.

Design notes
------------
* Strategy / Adapter : `ProviderSpec` describes each backend; the rest
                       of the codebase depends on this interface, never
                       on a vendor SDK.
* Factory            : `crew_llm()` and `ask_vision()` build the right
                       object for the active provider.
* litellm            : one OpenAI-shaped call surface for every vendor,
                       which is what makes the adapter thin.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------
@dataclass(frozen=True)
class ProviderSpec:
    """Everything the app needs to know about one backend."""

    chat_model: str       # used for agent reasoning
    vision_model: str     # used for image understanding
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    supports_vision: bool = True


PROVIDERS: dict[str, ProviderSpec] = {
    # Free tier, real vision support, no credit card.
    "gemini": ProviderSpec(
        # Google retires older Flash versions for new API keys, so this
        # default moves over time. Override with CHAT_MODEL /
        # VISION_MODEL in .env if your key sees a different lineup.
        chat_model="gemini/gemini-3.6-flash",
        vision_model="gemini/gemini-3.6-flash",
        api_key_env="GEMINI_API_KEY",
    ),
    # Fully local. Free forever, slower, needs ~8GB RAM.
    "ollama": ProviderSpec(
        chat_model="ollama/llama3.1",
        vision_model="ollama/llava",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    ),
    # Free ":free" models exist but rotate; check the dashboard.
    "openrouter": ProviderSpec(
        chat_model="openrouter/meta-llama/llama-3.3-70b-instruct:free",
        vision_model="openrouter/meta-llama/llama-4-maverick:free",
        api_key_env="OPENROUTER_API_KEY",
    ),
}


class ProviderError(RuntimeError):
    """Raised when the configured provider is unusable."""


def active_provider() -> str:
    name = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if name not in PROVIDERS:
        raise ProviderError(
            f"Unknown LLM_PROVIDER={name!r}. "
            f"Choose one of: {', '.join(sorted(PROVIDERS))}"
        )
    return name


def spec() -> ProviderSpec:
    """Active provider spec, with optional per-model env overrides."""
    base = PROVIDERS[active_provider()]
    return ProviderSpec(
        chat_model=os.getenv("CHAT_MODEL") or base.chat_model,
        vision_model=os.getenv("VISION_MODEL") or base.vision_model,
        api_key_env=base.api_key_env,
        base_url=base.base_url,
        supports_vision=base.supports_vision,
    )


def _api_key(s: ProviderSpec) -> Optional[str]:
    if not s.api_key_env:
        return None                      # local providers need no key
    key = os.getenv(s.api_key_env)
    if not key:
        raise ProviderError(
            f"{s.api_key_env} is not set. Copy .env.example to .env "
            f"and fill it in."
        )
    return key


# ---------------------------------------------------------------
# 1. Reasoning LLM handed to every CrewAI agent
# ---------------------------------------------------------------
def crew_llm():
    """Build the CrewAI LLM for the active provider.

    Without this, CrewAI silently falls back to OpenAI via litellm,
    which fails with a confusing auth error on any other backend.
    """
    from crewai import LLM  # imported lazily so tests stay fast

    s = spec()
    kwargs: dict = {"model": s.chat_model}
    if (key := _api_key(s)) is not None:
        kwargs["api_key"] = key
    if s.base_url:
        kwargs["base_url"] = s.base_url
    return LLM(**kwargs)


# ---------------------------------------------------------------
# 2. Vision calls
# ---------------------------------------------------------------
def encode_image(image_input: str) -> str:
    """Return a base64 string for a local path or an http(s) URL."""
    if image_input.startswith("http"):
        resp = requests.get(image_input, timeout=30)
        resp.raise_for_status()
        raw = resp.content
    else:
        path = Path(image_input)
        if not path.is_file():
            raise FileNotFoundError(f"No file found at path: {image_input}")
        raw = path.read_bytes()
    return base64.b64encode(raw).decode("utf-8")


def ask_vision(prompt: str, image_input: str, max_tokens: int = 700) -> str:
    """Send one image + one prompt to the active vision model."""
    from litellm import completion

    s = spec()
    encoded = encode_image(image_input)

    kwargs: dict = {
        "model": s.vision_model,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded}"
                        },
                    },
                ],
            }
        ],
    }
    if (key := _api_key(s)) is not None:
        kwargs["api_key"] = key
    if s.base_url:
        kwargs["api_base"] = s.base_url

    response = completion(**kwargs)
    return response["choices"][0]["message"]["content"]


def ask_text(prompt: str, max_tokens: int = 300) -> str:
    """Plain text completion on the active provider."""
    from litellm import completion

    s = spec()
    kwargs: dict = {
        "model": s.chat_model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if (key := _api_key(s)) is not None:
        kwargs["api_key"] = key
    if s.base_url:
        kwargs["api_base"] = s.base_url

    response = completion(**kwargs)
    return response["choices"][0]["message"]["content"]
