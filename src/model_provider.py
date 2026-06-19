from __future__ import annotations

from dataclasses import dataclass


import os

@dataclass
class ProviderConfig:
    provider: str
    model_name: str
    temperature: float
    api_key: str | None = None
    base_url: str | None = None


def normalize_provider(value: str) -> str:
    val = value.lower().strip()
    if val == "anthorpic":
        return "anthropic"
    return val


def build_chat_model(config: ProviderConfig):
    if config.provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=config.model_name, temperature=config.temperature, api_key=config.api_key, timeout=15, max_retries=2)
    elif config.provider == "custom":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=config.model_name, temperature=config.temperature, api_key=config.api_key or "sk-fake", base_url=config.base_url, timeout=30, max_retries=5)
    elif config.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=config.model_name, temperature=config.temperature, google_api_key=config.api_key, timeout=15, max_retries=2)
    elif config.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=config.model_name, temperature=config.temperature, api_key=config.api_key, timeout=15, max_retries=2)
    elif config.provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=config.model_name, temperature=config.temperature, base_url=config.base_url, timeout=15)
    elif config.provider == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=config.model_name, temperature=config.temperature, api_key=config.api_key, base_url="https://openrouter.ai/api", timeout=15, max_retries=2)
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")
