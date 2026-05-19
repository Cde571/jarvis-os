from __future__ import annotations

import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.

    IMPORTANTE:
    Se conserva el nombre OllamaClient solo para no romper imports existentes.
    Internamente ya NO usa Ollama como IA principal.
    Ahora usa LM Studio + Nemotron 3 Nano 4B.
    """

    def __init__(self):
        self.base_url = "http://127.0.0.1:1234"
        self.model = "nvidia/nemotron-3-nano-4b"
        self.timeout = 90

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            return response.status_code < 500
        except Exception:
            return False

    def ask(self, prompt: str) -> str:
        prompt = (prompt or "").strip()

        if not prompt:
            prompt = "Hola Jarvis, preséntate brevemente y dime qué puedes hacer."

        url = f"{self.base_url}/v1/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres JARVIS, un asistente local en español. "
                        "Responde de forma natural, clara, breve y útil. "
                        "Tu personalidad es tecnológica, precisa, elegante y directa. "
                        "No menciones que eres un modelo a menos que te lo pregunten."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.65,
            "max_tokens": 450,
            "stream": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        except Exception as exc:
            return (
                "LM Studio / Nemotron no respondió correctamente.\n\n"
                "Verifica:\n"
                "1. LM Studio debe estar en Status: Running.\n"
                "2. Debe decir Reachable at: http://127.0.0.1:1234.\n"
                "3. El modelo nvidia/nemotron-3-nano-4b debe estar cargado.\n"
                "4. No abras /v1/chat/completions en el navegador; ese endpoint usa POST.\n\n"
                f"Detalle técnico: {exc}"
            )
