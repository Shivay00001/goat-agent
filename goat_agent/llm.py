"""
GOAT Agent — Unified LLM Interface
Supports: Ollama (local), OpenAI, Anthropic, Google Gemini
Merged from: goatcode/llm/interface.py + goatclaw BYOK system
"""

import json
import os
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass, field
import aiohttp


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    provider: str
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseLLMInterface(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a single response."""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """Chat completion with message history."""
        ...

    async def is_available(self) -> bool:
        """Check if the provider is reachable."""
        return True


class OllamaInterface(BaseLLMInterface):
    """Interface for local Ollama models — zero API cost."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost",
        port: int = 11434,
    ):
        self.model = model
        self.base_url = base_url
        self.port = port
        self.api_url = f"{base_url}:{port}/api"

    async def is_available(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/tags",
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        return [m["name"] for m in data.get("models", [])]
                    return []
        except Exception:
            return []

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.api_url}/generate", json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Ollama error {resp.status}: {text}")
                data = await resp.json()
                return LLMResponse(
                    content=data.get("response", ""),
                    provider="ollama",
                    model=self.model,
                    tokens_used=data.get("eval_count"),
                    finish_reason="stop" if data.get("done") else None,
                    metadata={
                        "total_duration": data.get("total_duration"),
                        "load_duration": data.get("load_duration"),
                    },
                )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.api_url}/chat", json=payload) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Ollama error: {resp.status}")
                data = await resp.json()
                return LLMResponse(
                    content=data["message"].get("content", ""),
                    provider="ollama",
                    model=self.model,
                    tokens_used=data.get("eval_count"),
                    finish_reason="stop" if data.get("done") else None,
                )


class OpenAIInterface(BaseLLMInterface):
    """Interface for OpenAI API (GPT-4o, GPT-4, etc.)."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var or pass --api-key"
            )
        import openai
        self.client = openai.AsyncOpenAI(api_key=self.api_key, base_url=base_url)

    async def generate(self, prompt, system=None, temperature=0.7, max_tokens=None, **kw):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            provider="openai",
            model=self.model,
            tokens_used=response.usage.total_tokens if response.usage else None,
            finish_reason=choice.finish_reason,
        )

    async def chat(self, messages, temperature=0.7, max_tokens=None, **kw):
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            provider="openai",
            model=self.model,
            tokens_used=response.usage.total_tokens if response.usage else None,
            finish_reason=choice.finish_reason,
        )


class AnthropicInterface(BaseLLMInterface):
    """Interface for Anthropic Claude API."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY env var")
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=self.api_key)

    async def generate(self, prompt, system=None, temperature=0.7, max_tokens=None, **kw):
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or 4096,
            temperature=temperature,
            system=system or "You are a helpful coding assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return LLMResponse(
            content=response.content[0].text if response.content else "",
            provider="anthropic",
            model=self.model,
            tokens_used=(
                response.usage.input_tokens + response.usage.output_tokens
                if response.usage
                else None
            ),
            finish_reason=response.stop_reason,
        )

    async def chat(self, messages, temperature=0.7, max_tokens=None, **kw):
        # Extract system message if present
        system_msg = "You are a helpful coding assistant."
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or 4096,
            temperature=temperature,
            system=system_msg,
            messages=chat_messages,
        )
        return LLMResponse(
            content=response.content[0].text if response.content else "",
            provider="anthropic",
            model=self.model,
        )


def create_llm(provider: str = "ollama", model: Optional[str] = None, **kwargs) -> BaseLLMInterface:
    """Factory to create the right LLM interface."""
    if provider == "ollama":
        return OllamaInterface(
            model=model or "llama3.2",
            base_url=kwargs.get("base_url", "http://localhost"),
            port=kwargs.get("port", 11434),
        )
    elif provider == "openai":
        return OpenAIInterface(model=model or "gpt-4o", api_key=kwargs.get("api_key"))
    elif provider == "anthropic":
        return AnthropicInterface(model=model or "claude-sonnet-4-20250514", api_key=kwargs.get("api_key"))
    else:
        raise ValueError(f"Unknown provider: {provider}. Use: ollama, openai, anthropic")
