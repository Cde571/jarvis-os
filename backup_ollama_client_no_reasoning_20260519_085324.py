from __future__ import annotations

import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.

    Conserva el nombre OllamaClient para no romper imports.
    Usa LM Studio + Nemotron 3 Nano 4B.
    Primero usa /v1/chat/completions porque es más rápido.
    Si falla, intenta /api/v1/chat.
    """

    def __init__(self):
        self.base_url = "http://127.0.0.1:1234"
        self.model = "nvidia/nemotron-3-nano-4b"
        self.timeout = 60

    def is_available(self) -> bool:
        for endpoint in ["/v1/models", "/api/v1/models"]:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code < 500:
                    return True
            except Exception:
                pass

        return False

    def ask(self, prompt: str) -> str:
        prompt = (prompt or "").strip()

        if not prompt:
            prompt = "Preséntate brevemente como JARVIS."

        # 1. Endpoint rápido OpenAI-compatible.
        answer = self._ask_chat_completions(prompt)

        if self._valid_answer(answer):
            return answer

        # 2. Fallback endpoint Developer API.
        answer = self._ask_api_v1_chat(prompt)

        if self._valid_answer(answer):
            return answer

        return (
            "Nemotron respondió vacío o en un formato no reconocido. "
            "Prueba de nuevo con una pregunta más directa o reinicia el servidor de LM Studio."
        )

    def _system_prompt(self) -> str:
        return (
            "Eres JARVIS, un asistente local en español. "
            "Responde claro, directo y útil. "
            "Evita respuestas largas si el usuario no las pide. "
            "No menciones detalles técnicos salvo que te pregunten."
        )

    def _ask_chat_completions(self, prompt: str) -> str:
        url = f"{self.base_url}/v1/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt(),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.55,
            "max_tokens": 260,
            "stream": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            choices = data.get("choices", [])

            if not choices:
                return ""

            message = choices[0].get("message", {})
            content = message.get("content", "")

            return self._content_to_text(content)

        except Exception as exc:
            return ""

    def _ask_api_v1_chat(self, prompt: str) -> str:
        url = f"{self.base_url}/api/v1/chat"

        payload = {
            "model": self.model,
            "input": prompt,
            "system_prompt": self._system_prompt(),
            "context_length": 4096,
            "temperature": 0.55,
            "max_output_tokens": 260,
            "store": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return self._extract_any_text(data)

        except Exception:
            return ""

    def _valid_answer(self, text: str) -> bool:
        text = (text or "").strip()

        if not text:
            return False

        bad = [
            "No recibí una respuesta textual",
            "No recibí una respuesta",
            "None",
            "null",
        ]

        return not any(b.lower() in text.lower() for b in bad)

    def _content_to_text(self, content) -> str:
        if content is None:
            return ""

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts = []

            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if "text" in item:
                        parts.append(str(item["text"]))
                    elif "content" in item:
                        parts.append(str(item["content"]))
                    elif "value" in item:
                        parts.append(str(item["value"]))

            return "\n".join(parts).strip()

        if isinstance(content, dict):
            for key in ["text", "content", "value", "output_text"]:
                if key in content:
                    return str(content[key]).strip()

        return str(content).strip()

    def _extract_any_text(self, data: dict) -> str:
        if not isinstance(data, dict):
            return ""

        # Formatos simples
        for key in ["text", "content", "message", "response", "answer", "output_text"]:
            value = data.get(key)

            text = self._content_to_text(value)

            if text:
                return text

        # Formato OpenAI-compatible dentro del fallback
        choices = data.get("choices", [])

        if choices:
            try:
                content = choices[0].get("message", {}).get("content", "")
                text = self._content_to_text(content)

                if text:
                    return text
            except Exception:
                pass

        # Formato LM Studio Developer API
        output = data.get("output", [])

        if isinstance(output, str):
            return output.strip()

        if isinstance(output, list):
            parts = []

            for item in output:
                if isinstance(item, str):
                    parts.append(item)
                    continue

                if not isinstance(item, dict):
                    continue

                item_type = item.get("type", "")

                if item_type in ["message", "output_text", "text"]:
                    for key in ["content", "text", "value", "output_text"]:
                        if key in item:
                            text = self._content_to_text(item[key])

                            if text:
                                parts.append(text)

                # Algunos formatos guardan bloques internos
                if "content" in item:
                    text = self._content_to_text(item["content"])

                    if text:
                        parts.append(text)

            final = "\n".join(parts).strip()

            if final:
                return final

        return ""
