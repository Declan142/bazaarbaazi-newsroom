#!/usr/bin/env python3
"""
Multi-provider LLM dispatcher for the newsroom pipeline.
Routes calls to OpenRouter / Cerebras / Foundry-style endpoints with fallbacks.

Env vars:
    OPENROUTER_API_KEY  (required for or:* routes)
    CEREBRAS_API_KEY    (required for cerebras:* routes)
    OR_REFERER          (optional, e.g. https://yoursite.com)
    OR_APP_TITLE        (optional, defaults to "Newsroom Pipeline")

Routes:
    or:<alias>          OpenRouter free or paid model by alias
    cerebras:<alias>    Cerebras inference

Add new providers by registering a `call_<provider>` function and a
`<provider>:` prefix in `dispatch()`.
"""
import os
import time
import random
from typing import Optional

import requests

OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
CEREBRAS_KEY = os.environ.get("CEREBRAS_API_KEY", "")
OR_REFERER = os.environ.get("OR_REFERER", "https://example.com")
OR_APP_TITLE = os.environ.get("OR_APP_TITLE", "Newsroom Pipeline")

OR_FREE_MODELS = {
    "qwen3-next-80b": "qwen/qwen3-next-80b-a3b-instruct:free",
    "hermes-3-405b": "nousresearch/hermes-3-llama-3.1-405b:free",
    "gpt-oss-120b": "openai/gpt-oss-120b:free",
    "gpt-oss-20b": "openai/gpt-oss-20b:free",
    "llama-3.3-70b": "meta-llama/llama-3.3-70b-instruct:free",
    "gemma-4-31b": "google/gemma-4-31b-it:free",
    "glm-4.5-air": "z-ai/glm-4.5-air:free",
}

OR_PAID_MODELS = {
    "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
    "deepseek-v3.2": "deepseek/deepseek-v3.2",
    "deepseek-r1": "deepseek/deepseek-r1",
}

CEREBRAS_MODELS = {
    "qwen-3-32b": "qwen-3-32b",
    "llama-3.3-70b": "llama-3.3-70b",
    "gpt-oss-120b": "gpt-oss-120b",
}

OR_ALL_MODELS = {**OR_FREE_MODELS, **OR_PAID_MODELS}


def call_openrouter(model_alias: str, messages: list, max_tokens: int = 32000,
                    temperature: float = 0.7, json_mode: bool = False,
                    timeout: int = 300, max_retries: int = 4) -> dict:
    if not OR_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set in environment.")
    if model_alias not in OR_ALL_MODELS:
        raise ValueError(
            f"Unknown OR alias: {model_alias}. "
            f"Free: {list(OR_FREE_MODELS.keys())}. Paid: {list(OR_PAID_MODELS.keys())}"
        )
    model_id = OR_ALL_MODELS[model_alias]
    body = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {
        "Authorization": f"Bearer {OR_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OR_REFERER,
        "X-Title": OR_APP_TITLE,
    }

    last_err = None
    for attempt in range(max_retries):
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=body, timeout=timeout,
            )
            if r.status_code in (429, 502, 503, 504):
                wait = (2 ** attempt) * 5 + random.uniform(0, 3)
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "usage": data.get("usage", {}),
                "model": model_id,
                "is_free": ":free" in model_id,
            }
        except requests.exceptions.RequestException as e:
            last_err = e
            time.sleep(2 ** attempt + random.uniform(0, 2))
    raise RuntimeError(f"OR call failed after {max_retries} attempts. Last: {last_err}")


def call_cerebras(model_alias: str, messages: list, max_tokens: int = 8000,
                  temperature: float = 0.7) -> dict:
    if not CEREBRAS_KEY:
        raise RuntimeError("CEREBRAS_API_KEY not set in environment.")
    if model_alias not in CEREBRAS_MODELS:
        raise ValueError(f"Unknown Cerebras model: {model_alias}")
    body = {
        "model": CEREBRAS_MODELS[model_alias],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    r = requests.post(
        "https://api.cerebras.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {CEREBRAS_KEY}", "Content-Type": "application/json"},
        json=body, timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    return {
        "content": data["choices"][0]["message"]["content"],
        "usage": data.get("usage", {}),
        "model": CEREBRAS_MODELS[model_alias],
    }


def dispatch(route: str, messages: list, **kwargs) -> dict:
    """Single entry point. Route format: '<provider>:<alias>'.
       Supported: or:* and cerebras:*. Extend by adding cases."""
    if route.startswith("or:"):
        return call_openrouter(route[3:], messages, **kwargs)
    if route.startswith("cerebras:"):
        return call_cerebras(route[9:], messages, **kwargs)
    raise ValueError(f"Unknown route: {route}")


def dispatch_with_fallback(routes: list, messages: list, **kwargs) -> dict:
    """Try each route in order. Returns first success. Raises if all fail."""
    last_err = None
    for r in routes:
        try:
            return dispatch(r, messages, **kwargs)
        except Exception as e:
            last_err = e
            time.sleep(random.uniform(2, 5))
    raise RuntimeError(f"All routes failed. Last error: {last_err}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: llm_dispatch.py <route> [prompt]")
        print(f"OR routes:       {list(OR_FREE_MODELS.keys())}")
        print(f"OR paid:         {list(OR_PAID_MODELS.keys())}")
        print(f"Cerebras routes: {list(CEREBRAS_MODELS.keys())}")
        sys.exit(0)
    route = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Say 'dispatcher online' in one line."
    result = dispatch(route, [{"role": "user", "content": prompt}], max_tokens=200)
    print(f"--- {result['model']} ---")
    print(result["content"])
    print(f"Usage: {result['usage']}")
