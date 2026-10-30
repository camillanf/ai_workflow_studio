import json
import logging
import urllib.error
import urllib.request
import os

from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class AIResponse:
    """Respuesta de un proveedor IA."""

    def __init__(self, text, provider, model, stub=False, raw_response=None):
        self.text = text
        self.provider = provider
        self.model = model
        self.stub = stub
        self.raw_response = raw_response


class AIProviderInterface:
    """Interfaz abstracta de proveedores IA.

    Los nodos no dependen de un proveedor concreto: se instancía a través
    de get_provider() a partir del registro aiws.ai_provider.
    """

    def generate(self, prompt, context=None, system_prompt=None):
        raise NotImplementedError


class StubAIProvider(AIProviderInterface):
    """Proveedor simulado (V1). No realiza llamadas de red."""

    def generate(self, prompt, context=None, system_prompt=None):
        return AIResponse(
            text="Respuesta simulada (stub) del nodo Agente IA.",
            provider="stub",
            model="stub",
            stub=True,
        )


class OpenAIProvider(AIProviderInterface):
    """Proveedor OpenAI-compatible (GPT-4, GPT-3.5, OpenCode, etc.)."""

    def __init__(self, api_key, model="gpt-4o-mini", endpoint="https://api.openai.com/v1"):
        self.api_key = api_key or ""
        self.model = model or "gpt-4o-mini"
        self.endpoint = (endpoint or "https://api.openai.com/v1").rstrip("/")

    def generate(self, prompt, context=None, system_prompt=None):
        url = f"{self.endpoint}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2000,
        }
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
                text = result["choices"][0]["message"]["content"]
                return AIResponse(
                    text=text,
                    provider="openai",
                    model=self.model,
                    stub=False,
                    raw_response=result,
                )
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            _logger.exception("OpenAI API error: %s", error_body)
            raise Exception(f"OpenAI API error ({e.code}): {error_body}")
        except Exception as e:
            _logger.exception("OpenAI request failed")
            raise Exception(f"OpenAI request failed: {e}")


class AnthropicProvider(AIProviderInterface):
    """Proveedor Anthropic (Claude)."""

    def __init__(self, api_key, model="claude-3-5-sonnet-latest", endpoint="https://api.anthropic.com/v1"):
        self.api_key = api_key or ""
        self.model = model or "claude-3-5-sonnet-latest"
        self.endpoint = (endpoint or "https://api.anthropic.com/v1").rstrip("/")

    def generate(self, prompt, context=None, system_prompt=None):
        url = f"{self.endpoint}/messages"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        data = {
            "model": self.model,
            "max_tokens": 2000,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }
        if system_prompt:
            data["system"] = system_prompt
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
                text = result["content"][0]["text"]
                return AIResponse(
                    text=text,
                    provider="anthropic",
                    model=self.model,
                    stub=False,
                    raw_response=result,
                )
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            _logger.exception("Anthropic API error: %s", error_body)
            raise Exception(f"Anthropic API error ({e.code}): {error_body}")
        except Exception as e:
            _logger.exception("Anthropic request failed")
            raise Exception(f"Anthropic request failed: {e}")


class OllamaProvider(AIProviderInterface):
    """Proveedor Ollama (local/self-hosted)."""

    def __init__(self, model="llama3", endpoint="http://localhost:11434"):
        self.model = model or "llama3"
        self.endpoint = (endpoint or "http://localhost:11434").rstrip("/")

    def generate(self, prompt, context=None, system_prompt=None):
        url = f"{self.endpoint}/api/generate"
        headers = {"Content-Type": "application/json"}
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            data["system"] = system_prompt
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                text = result.get("response", "")
                return AIResponse(
                    text=text,
                    provider="ollama",
                    model=self.model,
                    stub=False,
                    raw_response=result,
                )
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            _logger.exception("Ollama API error: %s", error_body)
            raise Exception(f"Ollama API error ({e.code}): {error_body}")
        except Exception as e:
            _logger.exception("Ollama request failed")
            raise Exception(f"Ollama request failed: {e}")


class GeminiProvider(AIProviderInterface):
    """Proveedor Google Gemini (Generative Language API)."""

    def __init__(self, api_key, model="gemini-1.5-flash", endpoint="https://generativelanguage.googleapis.com/v1beta"):
        self.api_key = api_key or ""
        self.model = model or "gemini-1.5-flash"
        self.endpoint = (endpoint or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

    def generate(self, prompt, context=None, system_prompt=None):
        url = f"{self.endpoint}/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
        }
        if system_prompt:
            data["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                return AIResponse(
                    text=text,
                    provider="gemini",
                    model=self.model,
                    stub=False,
                    raw_response=result,
                )
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            _logger.exception("Gemini API error: %s", error_body)
            raise Exception(f"Gemini API error ({e.code}): {error_body}")
        except Exception as e:
            _logger.exception("Gemini request failed")
            raise Exception(f"Gemini request failed: {e}")


_PROVIDERS = {
    "stub": StubAIProvider(),
}


def _build_provider(provider_rec):
    """Instancia el proveedor según el registro aiws.ai_provider."""
    provider_type = (provider_rec.provider or "").lower()
    api_key = provider_rec.get_decrypted_api_key() or ""
    model = provider_rec.model or ""
    endpoint = provider_rec.endpoint or ""

    if provider_type in ("openai", "opencode"):
        # OpenCode y otros servicios compatibles usan la API de OpenAI
        if provider_type == "opencode" and not endpoint:
            raise Exception("El proveedor OpenCode requiere un Endpoint compatible con OpenAI.")
        return OpenAIProvider(api_key=api_key, model=model, endpoint=endpoint)
    if provider_type in ("claude", "anthropic"):
        return AnthropicProvider(api_key=api_key, model=model, endpoint=endpoint)
    if provider_type == "gemini":
        return GeminiProvider(api_key=api_key, model=model, endpoint=endpoint)
    if provider_type == "ollama":
        return OllamaProvider(model=model, endpoint=endpoint)
    if provider_type == "other":
        # Proveedor genérico: si tiene endpoint, se trata como OpenAI-compatible.
        if endpoint:
            return OpenAIProvider(api_key=api_key, model=model, endpoint=endpoint)
        return _PROVIDERS["stub"]
    _logger.warning("Proveedor IA desconocido: %s, usando stub", provider_type)
    return _PROVIDERS["stub"]


def get_provider(env, provider_id=None, provider_ref=None):
    """Devuelve el proveedor IA a usar.

    Orden de selección:
    1. ``provider_id``: id exacto del registro aiws.ai_provider.
    2. ``provider_ref``: nombre o tipo de proveedor (primer activo que coincida).
    3. Primer proveedor activo por nombre.
    4. Stub si no hay ninguno o hay error de acceso.
    """
    Provider = env["aiws.ai_provider"]
    provider_rec = None

    try:
        Provider.check_access("read")
        if provider_id:
            provider_rec = Provider.browse(int(provider_id)).exists()
        elif provider_ref:
            ref = str(provider_ref).strip()
            provider_rec = Provider.search(
                [("active", "=", True), "|", ("name", "=", ref), ("provider", "=", ref)],
                limit=1,
            )
        if not provider_rec:
            provider_rec = Provider.search([("active", "=", True)], limit=1, order="name")
    except (AccessError, ValueError, TypeError):
        provider_rec = None

    if not provider_rec:
        return _PROVIDERS["stub"]

    try:
        return _build_provider(provider_rec)
    except Exception as e:  # noqa: BLE001
        _logger.exception("Error instanciando proveedor IA: %s", e)
        raise

