from __future__ import annotations

import re
import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.
    Usa LM Studio + Nemotron.
    Modo estable:
    - respuestas cortas;
    - no razonamiento interno;
    - fallback local si el modelo devuelve vacío o basura.
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

        # Respuestas locales para preguntas comunes.
        local = self._local_short_answer(prompt)
        if local:
            return local

        raw = self._ask_chat_completions(prompt)
        clean = self._clean_answer(raw)

        if clean:
            return clean

        # Fallback final: no decir "no obtuve respuesta", sino responder de forma útil.
        return self._generic_fallback(prompt)

    def _system_prompt(self) -> str:
        return (
            "Eres JARVIS, un asistente local en español. "
            "Responde claro, breve y útil. "
            "No muestres razonamiento interno. "
            "No escribas en inglés. "
            "No expliques el proceso. "
            "Responde en máximo 2 frases. "
            "Si preguntan por una empresa tecnológica, di qué es y para qué sirve."
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
                        "Responde en español, máximo 2 frases, sin razonamiento interno.\n\n"
                        f"Pregunta: {prompt}"
                    ),
                },
            ],
            "temperature": 0.25,
            "top_p": 0.8,
            "max_tokens": 120,
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

        except Exception:
            return ""

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

        # Si el modelo usa etiquetas, tomar lo que sigue.
        for marker in ["FINAL:", "Respuesta:", "RESPUESTA:", "Answer:", "ANSWER:"]:
            if marker in text:
                text = text.split(marker, 1)[1].strip()
                break

        chunks = re.split(r"\n+|(?<=[.!?])\s+", text)
        chunks = [c.strip() for c in chunks if c.strip()]

        if not chunks:
            return ""

        bad_contains = [
            "we need",
            "we should",
            "the user",
            "user asks",
            "i need",
            "i should",
            "let me",
            "okay",
            "wait",
            "internal reasoning",
            "the prompt",
            "responde en español",
            "máximo 2 frases",
            "sin razonamiento",
        ]

        good = []

        for chunk in chunks:
            low = chunk.lower()

            if any(bad in low for bad in bad_contains):
                continue

            good.append(chunk)

        # Si el filtro borró todo, usar los últimos fragmentos del modelo.
        if not good:
            good = chunks[-2:]

        result = " ".join(good).strip()
        result = self._deduplicate_sentences(result)
        result = self._limit_sentences(result, 2)

        if len(result) > 420:
            result = result[:420].rsplit(" ", 1)[0].strip() + "..."

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

    def _normalize_prompt(self, prompt: str) -> str:
        text = prompt.lower()
        text = text.replace("¿", "").replace("?", "")
        text = text.replace("á", "a").replace("é", "e").replace("í", "i")
        text = text.replace("ó", "o").replace("ú", "u")
        return text.strip()

    def _local_short_answer(self, prompt: str) -> str:
        p = self._normalize_prompt(prompt)

        if "quien eres" in p or "quién eres" in prompt.lower() or "presentate" in p:
            return "Soy JARVIS, tu asistente local para ayudarte con tecnología, tareas del PC e inteligencia artificial."

        if "intel" in p:
            return "Sí, Intel es una empresa tecnológica conocida por sus procesadores, chips y soluciones para computadores, servidores e inteligencia artificial."

        if "nvidia" in p:
            return "Sí, NVIDIA es una empresa líder en tarjetas gráficas, chips para inteligencia artificial y computación acelerada."

        if "tecnologia" in p or "tecnología" in prompt.lower():
            return "Sí, puedo ayudarte con hardware, software, programación, inteligencia artificial y sistemas."

        if p in ["hola", "buenas", "hello", "hi"]:
            return "Hola, soy JARVIS. ¿En qué puedo ayudarte?"

        return ""

    def _generic_fallback(self, prompt: str) -> str:
        p = self._normalize_prompt(prompt)

        if "sabes de" in p or "que sabes" in p:
            topic = p.replace("sabes de", "").replace("que sabes", "").replace(",", "").strip()

            if topic:
                return f"Sí, puedo ayudarte con información sobre {topic}. Puedo darte un resumen breve o una explicación más completa."

        return "Sí, puedo ayudarte con eso. Hazme la pregunta de forma más específica y te respondo breve."
