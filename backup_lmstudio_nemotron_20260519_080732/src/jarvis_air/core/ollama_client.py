from __future__ import annotations

import json
import requests
from .config import SETTINGS

class OllamaClient:
    def ask(self, prompt: str) -> str:
        payload = {
            "model": SETTINGS.ollama_model,
            "prompt": prompt,
            "stream": False,
        }
        try:
            r = requests.post(SETTINGS.ollama_url, json=payload, timeout=20)
            r.raise_for_status()
            return r.json().get("response", "")
        except Exception as exc:
            return f"Ollama no respondió. Verifica que esté corriendo el modelo {SETTINGS.ollama_model}. Error: {exc}"
