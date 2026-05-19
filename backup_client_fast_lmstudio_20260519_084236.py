from __future__ import annotations

import os
import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.

    Se conserva el nombre OllamaClient para no romper imports.
    Internamente usa LM Studio Developer API:
    POST /api/v1/chat
    """

    def __init__(self):
        self.base_url = "http://127.0.0.1:1234"
        self.model = "nvidia/nemotron-3-nano-4b"
        self.timeout = 120
        self.api_token = os.environ.get("LM_API_TOKEN", "").strip()

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
        }

        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        return headers

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/v1/models", timeout=5)
            return response.status_code < 500
        except Exception:
            try:
                response = requests.get(f"{self.base_url}/v1/models", timeout=5)
                return response.status_code < 500
            except Exception:
                return False

    def ask(self, prompt: str) -> str:
        prompt = (prompt or "").strip()

        if not prompt:
            prompt = "Hola Jarvis, preséntate brevemente y dime qué puedes hacer."

        payload = {
            "model": self.model,
            "input": prompt,
            "system_prompt": (
                "Eres JARVIS, un asistente local en español. "
                "Responde de forma natural, clara, breve y útil. "
                "Tu personalidad es tecnológica, precisa, elegante y directa. "
                "No menciones que eres un modelo a menos que te lo pregunten."
            ),
            "context_length": 4096,
            "temperature": 0.65,
            "max_output_tokens": 450,
            "store": False,
        }

        return self._send_chat(payload)

    def ask_with_tools(self, prompt: str, enable_huggingface: bool = False, enable_browser: bool = False) -> str:
        """
        Consulta con integrations/MCP opcionales.
        Requiere que LM Studio tenga habilitados esos plugins/servidores.
        """
        integrations = []

        if enable_huggingface:
            integrations.append({
                "type": "ephemeral_mcp",
                "server_label": "huggingface",
                "server_url": "https://huggingface.co/mcp",
                "allowed_tools": ["model_search"],
            })

        if enable_browser:
            integrations.append({
                "type": "plugin",
                "id": "mcp/playwright",
                "allowed_tools": ["browser_navigate"],
            })

        payload = {
            "model": self.model,
            "input": prompt,
            "system_prompt": (
                "Eres JARVIS, un asistente local en español. "
                "Puedes usar herramientas si están disponibles. "
                "Responde de forma clara y breve."
            ),
            "integrations": integrations,
            "context_length": 8000,
            "temperature": 0,
            "max_output_tokens": 700,
            "store": False,
        }

        return self._send_chat(payload)

    def _send_chat(self, payload: dict) -> str:
        url = f"{self.base_url}/api/v1/chat"

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            return self._extract_output(data)

        except Exception as exc:
            return (
                "LM Studio Developer API no respondió correctamente.\n\n"
                "Verifica:\n"
                "1. LM Studio debe estar en Status: Running.\n"
                "2. Debe estar reachable en http://127.0.0.1:1234.\n"
                "3. El modelo debe estar cargado.\n"
                "4. Si activaste token, configura LM_API_TOKEN.\n\n"
                f"Detalle técnico: {exc}"
            )

    def _extract_output(self, data: dict) -> str:
        output = data.get("output", [])

        messages = []
        tool_logs = []

        for item in output:
            item_type = item.get("type")

            if item_type == "message":
                content = item.get("content", "")
                if content:
                    messages.append(content)

            elif item_type == "tool_call":
                tool = item.get("tool", "tool")
                tool_logs.append(f"[TOOL] {tool} ejecutado.")

            elif item_type == "invalid_tool_call":
                reason = item.get("reason", "tool call inválido")
                tool_logs.append(f"[TOOL ERROR] {reason}")

        final = ""

        if tool_logs:
            final += "\n".join(tool_logs) + "\n\n"

        if messages:
            final += "\n\n".join(messages)

        return final.strip() or "No recibí una respuesta textual de LM Studio."
