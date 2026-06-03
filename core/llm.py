"""
app/core/llm.py
LLM client — reads config/models.yaml, routes tasks to the right model on Groq.

All providers expose an OpenAI-compatible API, so one client handles everything.

Usage:
    from app.core.llm import LLMClient

    client = LLMClient()
    response = client.complete(
        task="extraction",
        messages=[{"role": "user", "content": "..."}],
    )
    text = response.choices[0].message.content
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Config loading
# ──────────────────────────────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "models.yaml"
_config_cache: dict | None = None


def _load_config() -> dict:
    global _config_cache
    if _config_cache is None:
        with open(_CONFIG_PATH) as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def get_model_config(task: str) -> dict:
    """Return the model config dict for a given task name."""
    cfg = _load_config()
    models = cfg.get("models", {})
    if task not in models:
        raise ValueError(
            f"Unknown task '{task}'. Available: {list(models.keys())}"
        )
    return models[task]


def get_provider_config(provider: str) -> dict:
    """Return the provider config dict (base_url, api_key_env)."""
    cfg = _load_config()
    providers = cfg.get("providers", {})
    if provider not in providers:
        raise ValueError(
            f"Unknown provider '{provider}'. Available: {list(providers.keys())}"
        )
    return providers[provider]


def get_defaults() -> dict:
    return _load_config().get("defaults", {})


# ──────────────────────────────────────────────────────────────────────────────
# LLM client
# ──────────────────────────────────────────────────────────────────────────────

class LLMClient:
    """
    OpenAI-compatible LLM client backed by any provider in models.yaml.

    Uses the `openai` SDK (which works with any OpenAI-compatible endpoint).
    Install: pip install openai

    Every call is automatically retried up to retry_max times with
    exponential backoff on 429 (rate limit) and 5xx errors.
    """

    def __init__(self, config_path: Path | None = None):
        if config_path:
            global _config_cache, _CONFIG_PATH
            _CONFIG_PATH = config_path
            _config_cache = None

        self._defaults = get_defaults()

    def complete(
        self,
        task: str,
        messages: list[dict],
        response_format: dict | None = None,
        **override_kwargs,
    ) -> Any:
        """
        Call the LLM for a given task.

        Args:
            task: one of the task names in models.yaml
                  (extraction, dedup_novelty, entity_resolution,
                   pattern_detection, alert_generation, agent_reasoning)
            messages: OpenAI-format message list
            response_format: e.g. {"type": "json_object"} for structured output
            **override_kwargs: override any model param (temperature, max_tokens...)

        Returns:
            OpenAI ChatCompletion response object.
        """
        from openai import OpenAI, RateLimitError, APIStatusError

        model_cfg = get_model_config(task)
        provider_cfg = get_provider_config(model_cfg["provider"])

        api_key = os.environ.get(provider_cfg["api_key_env"], "")
        if not api_key:
            raise EnvironmentError(
                f"Missing env var '{provider_cfg['api_key_env']}' "
                f"for provider '{model_cfg['provider']}'"
            )

        client = OpenAI(
            api_key=api_key,
            base_url=provider_cfg["base_url"],
        )

        call_kwargs: dict = {
            "model": model_cfg["model"],
            "messages": messages,
            "max_tokens": model_cfg.get("max_tokens", 500),
            "temperature": model_cfg.get("temperature", 0.1),
        }
        if response_format:
            call_kwargs["response_format"] = response_format
        call_kwargs.update(override_kwargs)

        retry_max = self._defaults.get("retry_max", 3)
        backoff_base = self._defaults.get("backoff_base_seconds", 5)

        last_exc = None
        for attempt in range(retry_max):
            try:
                response = client.chat.completions.create(**call_kwargs)
                logger.debug(
                    "LLM call OK — task=%s model=%s tokens_used=%s",
                    task,
                    call_kwargs["model"],
                    response.usage.total_tokens if response.usage else "?",
                )
                return response

            except RateLimitError as e:
                wait = backoff_base * (2 ** attempt)
                logger.warning(
                    "Rate limit on attempt %d/%d, waiting %ds: %s",
                    attempt + 1, retry_max, wait, e,
                )
                time.sleep(wait)
                last_exc = e

            except APIStatusError as e:
                if e.status_code >= 500:
                    wait = backoff_base * (2 ** attempt)
                    logger.warning(
                        "Server error %d on attempt %d/%d, waiting %ds",
                        e.status_code, attempt + 1, retry_max, wait,
                    )
                    time.sleep(wait)
                    last_exc = e
                else:
                    raise  # 4xx errors are not retried

        raise RuntimeError(
            f"LLM call failed after {retry_max} attempts for task '{task}'"
        ) from last_exc
