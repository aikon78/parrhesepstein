"""
Client Anthropic centralizzato + retry.
"""
import time
from types import SimpleNamespace

import requests
from anthropic import Anthropic
from app.extensions import db_settings, app_settings_collection


def get_ai_provider():
    """Provider attivo: 'claude' (default) oppure 'mistral'."""
    doc = app_settings_collection.find_one({"_id": "global"}) or {}
    provider = (doc.get("provider") or "claude").strip().lower()
    return provider if provider in {"claude", "mistral"} else "claude"


def get_claude_api_key(provider=None):
    """Recupera la chiave API del provider attivo dal database."""
    service = provider or get_ai_provider()
    key_data = db_settings["api_keys"].find_one({"service": service})
    if key_data and "key" in key_data:
        return key_data["key"]
    return None


def get_anthropic_base_url(provider=None):
    """Recupera il base_url personalizzato dal database per il provider attivo."""
    service = provider or get_ai_provider()
    key_data = db_settings["api_keys"].find_one({"service": service})
    if key_data and key_data.get("base_url"):
        return key_data["base_url"]
    return None


def _normalize_message_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(str(block.get("text")))
                elif block.get("text"):
                    parts.append(str(block.get("text")))
            elif block is not None:
                parts.append(str(block))
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


class _MistralMessagesCompat:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.mistral.ai").rstrip("/")

    def create(self, **kwargs):
        model = kwargs.get("model")
        if not model:
            raise ValueError("Model non specificato per Mistral")

        messages = []
        system = kwargs.get("system")
        if system:
            messages.append({
                "role": "system",
                "content": _normalize_message_content(system),
            })

        for msg in kwargs.get("messages", []):
            messages.append({
                "role": msg.get("role", "user"),
                "content": _normalize_message_content(msg.get("content", "")),
            })

        payload = {
            "model": model,
            "messages": messages,
        }
        if kwargs.get("max_tokens"):
            payload["max_tokens"] = kwargs.get("max_tokens")
        if kwargs.get("temperature") is not None:
            payload["temperature"] = kwargs.get("temperature")

        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )

        if response.status_code >= 400:
            raise ValueError(f"Mistral API error {response.status_code}: {response.text[:500]}")

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            text = "\n".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
        else:
            text = str(content)

        return SimpleNamespace(content=[SimpleNamespace(text=text)], raw=data)


class _MistralClientCompat:
    def __init__(self, api_key, base_url=None):
        self.messages = _MistralMessagesCompat(api_key, base_url)


def create_ai_client(api_key, base_url=None, provider=None):
    provider_name = (provider or get_ai_provider() or "claude").lower()
    if provider_name == "mistral":
        return _MistralClientCompat(api_key=api_key, base_url=base_url)
    if base_url:
        return Anthropic(api_key=api_key, base_url=base_url)
    return Anthropic(api_key=api_key)


def get_anthropic_client():
    """Crea il client del provider attivo con la chiave salvata nel database."""
    provider = get_ai_provider()
    api_key = get_claude_api_key(provider=provider)
    if not api_key:
        raise ValueError(f"Chiave API {provider.capitalize()} non trovata nel database.")
    base_url = get_anthropic_base_url(provider=provider)
    return create_ai_client(api_key=api_key, base_url=base_url, provider=provider)


def call_claude_with_retry(client, max_retries=3, **kwargs):
    """Chiama l'API Claude con retry automatico per errori 500"""
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.messages.create(**kwargs)
            return response
        except Exception as e:
            last_error = e
            error_str = str(e)
            if (
                "500" in error_str
                or "Internal server error" in error_str
                or "429" in error_str
                or "rate" in error_str.lower()
            ):
                wait_time = (attempt + 1) * 2
                print(f"[CLAUDE] Errore 500, retry {attempt + 1}/{max_retries} tra {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e
    raise last_error
