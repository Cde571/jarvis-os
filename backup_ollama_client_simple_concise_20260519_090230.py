from __future__ import annotations

import re
import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.
    Usa LM Studio + Nemotron 3 Nano 4B.
    Estrategia:
    - Obliga al modelo a responder con FINAL:
    - Extrae solo la respuesta final.
    - Evita razonamiento interno y respuestas vacías.
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

        raw = self._ask_chat_completions(prompt)
        clean = self._extract_final_answer(raw)

        if clean:
            return clean

        # Segundo intento más estricto.
        raw = self._ask_chat_completions(
            f"Contesta exactamente con el formato FINAL: y una respuesta breve. Pregunta: {prompt}"
        )
        clean = self._extract_final_answer(raw)

        if clean:
            return clean

        # Último respaldo: limpiar sin ser agresivo.
        fallback = self._soft_clean(raw)

        if fallback:
            return fallback

        return "No obtuve una respuesta clara. Reformula la pregunta en una frase."

    def _system_prompt(self) -> str:
        return (
            "Eres JARVIS, un asistente local en español. "
            "Tu respuesta SIEMPRE debe iniciar con 'FINAL:'. "
            "Después de FINAL: escribe solo la respuesta final. "
            "No muestres razonamiento interno. "
            "No escribas en inglés. "
            "No expliques el proceso. "
            "Responde en máximo 2 frases. "
            "Si preguntan por una empresa tecnológica, di qué es y para qué se usa. "
            "Ejemplo: FINAL: Sí, Intel es una empresa tecnológica conocida por procesadores, chips y soluciones para computadores y servidores."
        )

    def _ask_chat_completions(self, prompt: str) -> str:
        url = f"{self.base_url}/v1/chat/completions"

        user_prompt = (
            "Responde usando exactamente este formato:\n"
            "FINAL: <respuesta breve en español>\n\n"
            "Reglas:\n"
            "- Máximo 2 frases.\n"
            "- No razonamiento interno.\n"
            "- No inglés.\n"
            "- No repitas la respuesta.\n\n"
            f"Pregunta: {prompt}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "top_p": 0.7,
            "max_tokens": 110,
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
            return "FINAL: No pude conectar con LM Studio. Verifica que esté en Running y con el modelo cargado."

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

    def _extract_final_answer(self, text: str) -> str:
        text = (text or "").strip()

        if not text:
            return ""

        # Quitar bloques de pensamiento.
        text = re.sub(r"(?is)<think>.*?</think>", "", text)
        text = re.sub(r"(?is)```.*?```", "", text)

        # Caso ideal: FINAL:
        match = re.search(r"(?is)\bFINAL\s*:\s*(.+)", text)

        if match:
            answer = match.group(1).strip()
        else:
            answer = text.strip()

        # Si todavía trae razonamiento antes de la respuesta, tomar desde una frase útil.
        answer = self._remove_reasoning_fragments(answer)

        # Quitar duplicados y limitar.
        answer = self._deduplicate_sentences(answer)
        answer = self._limit_sentences(answer, 2)

        return answer.strip()

    def _remove_reasoning_fragments(self, text: str) -> str:
        text = (text or "").strip()

        if not text:
            return ""

        # Separar por líneas y frases.
        chunks = re.split(r"\n+|(?<=[.!?])\s+", text)
        chunks = [c.strip() for c in chunks if c.strip()]

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
            "internal reasoning",
            "the prompt",
            "keep short",
        ]

        good = []

        for chunk in chunks:
            low = chunk.lower()

            if any(bad in low for bad in bad_contains):
                continue

            if "FINAL:" in chunk:
                chunk = chunk.split("FINAL:", 1)[-1].strip()

            good.append(chunk)

        if not good:
            # Respaldo: usar últimos 2 fragmentos, porque la respuesta final suele quedar al final.
            good = chunks[-2:]

        return " ".join(good).strip()

    def _soft_clean(self, text: str) -> str:
        text = (text or "").strip()

        if not text:
            return ""

        text = re.sub(r"(?is)<think>.*?</think>", "", text)
        text = re.sub(r"(?is)```.*?```", "", text)

        lines = [l.strip() for l in text.splitlines() if l.strip()]

        if not lines:
            return ""

        # Tomar la última línea que no parezca razonamiento.
        for line in reversed(lines):
            low = line.lower()

            if any(x in low for x in ["we need", "the user", "i should", "let me", "okay", "wait"]):
                continue

            return self._limit_sentences(self._deduplicate_sentences(line), 2)

        return self._limit_sentences(lines[-1], 2)

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
