from __future__ import annotations

import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.

    El nombre OllamaClient se conserva para no romper imports.
    Internamente usa LM Studio + Nemotron 3 Nano 4B.
    Endpoint rápido para conversación normal:
    POST /v1/chat/completions
    """

    def __init__(self):
        self.base_url = "http://127.0.0.1:1234"
        self.model = "nvidia/nemotron-3-nano-4b"
        self.timeout = 45

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=4)
            return response.status_code < 500
        except Exception:
            return False

    def ask(self, prompt: str) -> str:
        prompt = (prompt or "").strip()

        if not prompt:
            prompt = "Preséntate brevemente como JARVIS."

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres JARVIS, un asistente local en español. "
                        "Responde directo, claro y útil. "
                        "Evita respuestas largas si el usuario no las pide. "
                        "No menciones detalles técnicos salvo que te pregunten."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.55,
            "max_tokens": 220,
            "stream": False,
        }

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        except Exception as exc:
            return (
                "No pude obtener respuesta de LM Studio / Nemotron. "
                "Verifica que LM Studio esté en Status: Running, puerto 1234, "
                "y que el modelo nvidia/nemotron-3-nano-4b esté cargado. "
                f"Detalle: {exc}"
            )
