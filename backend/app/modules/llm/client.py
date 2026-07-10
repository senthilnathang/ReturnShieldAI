from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from backend.app.core.config import settings

logger = logging.getLogger("returnshield.llm")

_DEFAULT_HEADERS_SITE = "https://github.com/ReturnShieldAI"


class LLMClient:
    """Thin client over an OpenAI-compatible chat completions API (OpenRouter).

    OpenRouter exposes the same ``/chat/completions`` contract as OpenAI, so the
    same client works for any provider routed through it. The client is a
    no-op when the LLM is disabled (``settings.llm_available`` is False).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        vision_model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.vision_model = vision_model or getattr(settings, "llm_vision_model", self.model)
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens
        self.timeout = timeout if timeout is not None else settings.llm_timeout_seconds
        self.enabled = enabled if enabled is not None else settings.llm_available

    @property
    def is_enabled(self) -> bool:
        return bool(self.enabled and self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": _DEFAULT_HEADERS_SITE,
            "X-Title": settings.app_name,
        }

    def _post(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("LLM request failed (%s): %s", exc.response.status_code, exc.response.text[:300])
        except Exception as exc:
            logger.warning("LLM request error: %s", exc)
        return None

    def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str | None:
        """Call the chat completions endpoint and return the assistant text.

        Returns ``None`` when the client is disabled or the call fails, so
        callers can transparently fall back to heuristic behaviour.
        """
        if not self.is_enabled:
            return None

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        data = self._post(payload)
        if not data:
            return None
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("LLM response missing assistant content: %s", exc)
            return None

    def chat_json(self, *, system: str, user: str) -> dict[str, Any] | None:
        """Call the chat endpoint expecting a JSON object response.

        Returns the parsed dict, or ``None`` when disabled / on failure / when
        the response is not valid JSON.
        """
        content = self.chat(
            system=system,
            user=user,
            response_format={"type": "json_object"},
        )
        if not content:
            return None
        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("LLM returned non-JSON response: %s", exc)
            return None

    def chat_vision_json(
        self,
        *,
        system: str,
        user: str,
        image_data_url: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any] | None:
        """Call a vision-capable chat model and expect a JSON response."""
        if not self.is_enabled:
            return None

        payload: dict[str, Any] = {
            "model": self.vision_model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        data = self._post(payload)
        if not data:
            return None
        try:
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError, KeyError, IndexError) as exc:
            logger.warning("Vision LLM returned invalid JSON: %s", exc)
            return None


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return a process-wide :class:`LLMClient` built from settings."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
