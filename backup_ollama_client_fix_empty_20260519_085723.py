from __future__ import annotations

import re
import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.
    Usa LM Studio + Nemotron 3 Nano 4B.
    Modo: respuestas cortas, directas y sin razonamiento interno.
    """

    def __init__(self):
        self.base_url = "http://127.0.0.1:1234"
        self.model = "nvidia/nemotron-3-nano-4b"
        self.timeout = 45

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

        return "No obtuve una respuesta clara. Intenta preguntarlo de forma más directa."

    def _system_prompt(self) -> str:
        return (
            "Eres JARVIS, un asistente local en español. "
            "Responde SOLO con la respuesta final. "
            "No muestres razonamiento interno, análisis, pasos mentales ni explicación del proceso. "
            "Responde de forma muy concisa: máximo 2 frases. "
            "Si la pregunta es simple, responde en 1 frase. "
            "Si el usuario pide explicación, usa máximo 3 viñetas cortas. "
            "No repitas la misma idea. "
            "No escribas en inglés. "
            "No uses frases como 'We need', 'The user asks', 'I should', 'Let me', 'Okay', 'Wait'. "
            "Sé directo, técnico cuando haga falta y útil."
        )

    def _ask_chat_completions(self, prompt: str) -> str:
        url = f"{self.base_url}/v1/chat/completions"

        user_prompt = (
            "Responde en español, máximo 2 frases. "
            "No incluyas razonamiento interno. "
            "No repitas la respuesta.\n\n"
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
            "temperature": 0.15,
            "top_p": 0.75,
            "max_tokens": 70,
            "stream": False,
            "stop": [
                "\nWe need",
                "\nThe user",
                "\nI need",
                "\nI should",
                "\nLet me",
                "\nOkay",
                "\nWait",
            ],
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
                "No pude conectar con LM Studio/Nemotron. "
                "Verifica que LM Studio esté en Running y el modelo cargado."
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
        text = (text or "").strip()

        if not text:
            return ""

        text = re.sub(r"(?is)<think>.*?</think>", "", text)
        text = re.sub(r"(?is)```.*?```", "", text)

        raw_lines = [line.strip() for line in text.splitlines() if line.strip()]

        bad_patterns = [
            r"^we need\b",
            r"^we should\b",
            r"^we can\b",
            r"^the user\b",
            r"^user asks\b",
            r"^i need\b",
            r"^i should\b",
            r"^let me\b",
            r"^okay\b",
            r"^ok[, ]",
            r"^wait\b",
            r"^check\b",
            r"^respond as\b",
            r"^need to\b",
            r"^maybe\b",
            r"^alright\b",
            r"^so\b",
        ]

        cleaned_lines = []

        for line in raw_lines:
            low = line.lower().strip()

            if any(re.search(pattern, low) for pattern in bad_patterns):
                continue

            if "the user" in low or "the prompt" in low:
                continue

            if "internal" in low and "reason" in low:
                continue

            cleaned_lines.append(line)

        if not cleaned_lines:
            return ""

        result = " ".join(cleaned_lines).strip()

        result = self._deduplicate_sentences(result)
        result = self._limit_sentences(result, max_sentences=2)

        return result.strip()

    def _deduplicate_sentences(self, text: str) -> str:
        parts = re.split(r"(?<=[.!?])\s+", text)

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

    def _limit_sentences(self, text: str, max_sentences: int = 2) -> str:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        parts = [p.strip() for p in parts if p.strip()]

        if not parts:
            return text.strip()

        return " ".join(parts[:max_sentences]).strip()
