from __future__ import annotations

import re
import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.
    Usa LM Studio + Nemotron 3 Nano 4B.
    Limpia razonamiento interno y respuestas duplicadas.
    """

    def __init__(self):
        self.base_url = "http://127.0.0.1:1234"
        self.model = "nvidia/nemotron-3-nano-4b"
        self.timeout = 60

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            return response.status_code < 500
        except Exception:
            return False

    def ask(self, prompt: str) -> str:
        prompt = (prompt or "").strip()

        if not prompt:
            prompt = "Preséntate brevemente como JARVIS."

        raw_answer = self._ask_chat_completions(prompt)
        clean_answer = self._clean_answer(raw_answer)

        if clean_answer:
            return clean_answer

        return "Nemotron no devolvió una respuesta clara. Intenta de nuevo con una pregunta más directa."

    def _system_prompt(self) -> str:
        return (
            "Eres JARVIS, un asistente local en español. "
            "Responde SOLO con la respuesta final. "
            "Prohibido mostrar razonamiento interno. "
            "Prohibido escribir análisis, planes, pasos mentales o comentarios como: "
            "'We need', 'The user asks', 'I should', 'Let me', 'Okay', 'Wait'. "
            "No expliques cómo construyes la respuesta. "
            "Responde en español, de forma clara, breve y útil. "
            "Si el usuario hace una pregunta simple, responde en máximo dos frases."
        )

    def _ask_chat_completions(self, prompt: str) -> str:
        url = f"{self.base_url}/v1/chat/completions"

        user_prompt = (
            "Responde solamente la respuesta final en español. "
            "No incluyas razonamiento ni análisis interno.\n\n"
            f"Pregunta: {prompt}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt(),
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": 0.25,
            "max_tokens": 140,
            "stream": False,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            choices = data.get("choices", [])

            if not choices:
                return ""

            message = choices[0].get("message", {})
            content = message.get("content", "")

            return self._content_to_text(content)

        except Exception as exc:
            return (
                "No pude obtener respuesta de LM Studio / Nemotron. "
                "Verifica que LM Studio esté en Status: Running, puerto 1234, "
                "y que el modelo nvidia/nemotron-3-nano-4b esté cargado. "
                f"Detalle: {exc}"
            )

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
                    for key in ["text", "content", "value", "output_text"]:
                        if key in item:
                            parts.append(str(item[key]))
                            break

            return "\n".join(parts).strip()

        if isinstance(content, dict):
            for key in ["text", "content", "value", "output_text"]:
                if key in content:
                    return str(content[key]).strip()

        return str(content).strip()

    def _clean_answer(self, text: str) -> str:
        """
        Limpieza fuerte:
        - elimina razonamiento en inglés;
        - elimina líneas tipo chain-of-thought;
        - elimina duplicados;
        - conserva la respuesta final en español.
        """
        text = (text or "").strip()

        if not text:
            return ""

        # Quitar etiquetas o bloques de pensamiento.
        text = re.sub(r"(?is)<think>.*?</think>", "", text)
        text = re.sub(r"(?is)```.*?```", "", text)

        raw_lines = [line.strip() for line in text.splitlines() if line.strip()]

        if not raw_lines:
            return ""

        bad_patterns = [
            r"^we need\b",
            r"^we should\b",
            r"^we can\b",
            r"^we must\b",
            r"^the user\b",
            r"^user asks\b",
            r"^i need\b",
            r"^i should\b",
            r"^i can\b",
            r"^let me\b",
            r"^okay\b",
            r"^ok[, ]",
            r"^wait\b",
            r"^check\b",
            r"^keep short\b",
            r"^respond as\b",
            r"^need to\b",
            r"^maybe\b",
            r"^alright\b",
            r"^so\b",
            r"^yes,",
        ]

        cleaned_lines = []

        for line in raw_lines:
            low = line.lower().strip()

            # Eliminar líneas claramente de razonamiento interno.
            if any(re.search(pattern, low) for pattern in bad_patterns):
                continue

            if "the user" in low:
                continue

            if "the prompt" in low:
                continue

            if "responde breve" in low and ("user" in low or "prompt" in low):
                continue

            if "internal" in low and "reason" in low:
                continue

            cleaned_lines.append(line)

        if not cleaned_lines:
            cleaned_lines = raw_lines[-2:]

        # Unir líneas.
        result = "\n".join(cleaned_lines).strip()

        # Si quedó texto en inglés antes de una respuesta en español,
        # intentar tomar desde la primera línea que parece respuesta final en español.
        lines = [line.strip() for line in result.splitlines() if line.strip()]

        spanish_markers = [
            "sí,",
            "si,",
            "claro",
            "por supuesto",
            "nvidia",
            "hola",
            "puedo",
            "soy",
            "la ",
            "el ",
            "una ",
            "un ",
            "en ",
        ]

        start_idx = None

        for idx, line in enumerate(lines):
            low = line.lower()
            if any(low.startswith(marker) for marker in spanish_markers):
                start_idx = idx
                break

        if start_idx is not None:
            lines = lines[start_idx:]

        # Eliminar duplicados exactos.
        unique_lines = []
        seen = set()

        for line in lines:
            key = line.strip().lower()

            if key in seen:
                continue

            seen.add(key)
            unique_lines.append(line)

        result = "\n".join(unique_lines).strip()

        # Eliminar frases duplicadas dentro del mismo párrafo.
        result = self._deduplicate_sentences(result)

        return result.strip()

    def _deduplicate_sentences(self, text: str) -> str:
        # Divide por signos de fin de oración manteniendo frase simple.
        parts = re.split(r"(?<=[.!?¿])\s+", text)

        final = []
        seen = set()

        for part in parts:
            clean = part.strip()

            if not clean:
                continue

            key = clean.lower()

            if key in seen:
                continue

            seen.add(key)
            final.append(clean)

        return " ".join(final).strip()
