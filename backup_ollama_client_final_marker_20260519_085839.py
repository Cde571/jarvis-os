from __future__ import annotations

import re
import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.
    Usa LM Studio + Nemotron 3 Nano 4B.
    Modo: respuestas cortas, sin razonamiento interno y sin borrar respuestas útiles.
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

        # Segundo intento más directo si el primero vino vacío o contaminado.
        raw_answer = self._ask_chat_completions(
            f"Responde en una sola frase, sin razonamiento interno: {prompt}"
        )
        clean_answer = self._clean_answer(raw_answer)

        if clean_answer:
            return clean_answer

        return "No obtuve una respuesta clara. Intenta reformular la pregunta."

    def _system_prompt(self) -> str:
        return (
            "Eres JARVIS, un asistente local en español. "
            "Responde únicamente con la respuesta final. "
            "No muestres razonamiento interno, análisis, pasos mentales ni comentarios del proceso. "
            "Responde en máximo 2 frases. "
            "Si la pregunta es simple, responde en 1 frase. "
            "No repitas la misma idea. "
            "No escribas en inglés. "
            "Sé directo, claro y útil."
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
                    "content": (
                        "Responde SOLO la respuesta final en español. "
                        "Máximo 2 frases. "
                        "No incluyas razonamiento interno. "
                        "No repitas la respuesta.\n\n"
                        f"Pregunta: {prompt}"
                    ),
                },
            ],
            "temperature": 0.2,
            "top_p": 0.7,
            "max_tokens": 90,
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

        except Exception:
            return (
                "No pude conectar con LM Studio/Nemotron. "
                "Verifica que LM Studio esté en Running y que el modelo esté cargado."
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

        # Dividir en frases, no solo líneas. Esto evita borrar una línea completa
        # cuando trae razonamiento + respuesta final juntas.
        chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
        chunks = [c.strip() for c in chunks if c.strip()]

        if not chunks:
            return ""

        bad_contains = [
            "we need",
            "we should",
            "we can",
            "the user",
            "user asks",
            "i need",
            "i should",
            "let me",
            "okay",
            "wait",
            "respond as",
            "need to",
            "internal reasoning",
            "razonamiento interno",
            "the prompt",
            "keep short",
        ]

        good_chunks = []

        for chunk in chunks:
            low = chunk.lower()

            # Si el chunk es claramente razonamiento, lo ignoramos.
            if any(bad in low for bad in bad_contains):
                continue

            # Ignorar fragmentos demasiado metalingüísticos.
            if "responde" in low and ("user" in low or "prompt" in low):
                continue

            good_chunks.append(chunk)

        # Si el filtro borró todo, usar los últimos fragmentos del texto original,
        # porque normalmente ahí está la respuesta final.
        if not good_chunks:
            good_chunks = chunks[-2:]

        result = " ".join(good_chunks).strip()

        # Eliminar duplicados.
        result = self._deduplicate_sentences(result)

        # Limitar a 2 frases.
        result = self._limit_sentences(result, 2)

        # Si aún quedó demasiado largo, cortar de forma segura.
        if len(result) > 450:
            result = result[:450].rsplit(" ", 1)[0].strip() + "..."

        return result.strip()

    def _deduplicate_sentences(self, text: str) -> str:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
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
