from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from model_provider import ProviderConfig, normalize_provider


@dataclass
class LabConfig:
    """Student TODO: define the shared configuration for the lab.

    Hints:
    - Keep paths for the repo root, dataset directory, and state directory.
    - Add compact-memory settings such as threshold and number of messages to keep.
    - Add provider settings for `openai`, `custom`, `gemini`, `anthropic`, `ollama`, and `openrouter`.
    """

    base_dir: Path
    data_dir: Path
    state_dir: Path
    compact_threshold_tokens: int
    compact_keep_messages: int
    model: ProviderConfig
    judge_model: ProviderConfig


def load_config(base_dir: Path | None = None) -> LabConfig:
    root = (base_dir or Path(__file__).resolve().parent.parent).resolve()
    load_dotenv(root / ".env")
    
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    provider_str = normalize_provider(os.environ.get("LLM_PROVIDER", "openai"))
    model_name = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    
    api_key = None
    base_url = None
    
    if provider_str == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
    elif provider_str == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
    elif provider_str == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    elif provider_str == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    elif provider_str == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
    elif provider_str == "custom":
        api_key = os.environ.get("CUSTOM_API_KEY")
        base_url = os.environ.get("CUSTOM_BASE_URL")

    model_config = ProviderConfig(
        provider=provider_str,
        model_name=model_name,
        temperature=0.0,
        api_key=api_key,
        base_url=base_url
    )
    
    return LabConfig(
        base_dir=root,
        data_dir=root / "data",
        state_dir=state_dir,
        compact_threshold_tokens=2000,
        compact_keep_messages=2,
        model=model_config,
        judge_model=model_config
    )
