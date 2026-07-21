"""Local LLM client: Ollama HTTP API with injectable mock for tests."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


@dataclass
class OllamaConfig:
    host: str = "http://127.0.0.1:11434"
    model: str = "llama3.2:3b"
    temperature: float = 0.2
    timeout: float = 120.0

    @classmethod
    def from_env(cls) -> "OllamaConfig":
        return cls(
            host=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/"),
            model=os.environ.get("NEOTRADE_OLLAMA_MODEL", "llama3.2:3b"),
            temperature=float(os.environ.get("NEOTRADE_OLLAMA_TEMP", "0.2")),
            timeout=float(os.environ.get("NEOTRADE_OLLAMA_TIMEOUT", "120")),
        )


class OllamaClient:
    def __init__(self, config: OllamaConfig | None = None) -> None:
        self.config = config or OllamaConfig.from_env()

    def complete(self, system: str, user: str) -> str:
        url = f"{self.config.host}/api/chat"
        payload = {
            "model": self.config.model,
            "stream": False,
            "options": {"temperature": self.config.temperature},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama unreachable at {self.config.host} ({exc.reason}). "
                "Install/start Ollama and pull a small model, e.g. "
                "`ollama pull llama3.2:3b`."
            ) from exc
        msg = body.get("message") or {}
        content = msg.get("content")
        if not content:
            raise RuntimeError(f"empty Ollama response: {body!r}")
        return str(content).strip()

    def ping(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.config.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except (OSError, urllib.error.URLError, TimeoutError, ValueError):
            return False


class MockLLM:
    """Deterministic stub for unit tests (no network)."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        key = "analyst" if "performance" in system.lower() or "analyst" in system.lower() else "trader"
        if key in self.responses:
            return self.responses[key]
        if "performance" in system.lower() or "analyst" in system.lower():
            return (
                "STANCE: cautious\n"
                "SUMMARY: Diversify and keep cash buffer; signal edge is modest.\n"
                "CHECKS: sleeve balance; open orders; avoid over-concentration.\n"
                "SCORE: 6/10"
            )
        return (
            "THESIS: Favor high-proba growth names within sleeve caps.\n"
            "TOP_PICKS: ARM, TSM, AMD\n"
            "AVOID: low-proba holds without catalyst\n"
            "RISKS: weekend gap; weak model accuracy; sector crowding\n"
            "ACTION: follow paper-plan buys; do not increase size beyond risk limits"
        )


def default_llm() -> LLMClient:
    return OllamaClient()
