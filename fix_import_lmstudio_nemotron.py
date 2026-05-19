from pathlib import Path
import re
from datetime import datetime

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"
client_file = root / "src" / "jarvis_air" / "core" / "ollama_client.py"
voice_file = root / "src" / "jarvis_air" / "voice_bridge.py"
app_file = root / "src" / "jarvis_air" / "app.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = root / f"backup_fix_import_lmstudio_{stamp}"
backup_dir.mkdir(parents=True, exist_ok=True)

for f in [ui_file, client_file, voice_file, app_file]:
    if f.exists():
        dest = backup_dir / f
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

print(f"Backup creado en: {backup_dir}")

# ============================================================
# 1. Corregir hologram_window.py
# ============================================================

ui = ui_file.read_text(encoding="utf-8", errors="replace")

# El error principal: import inválido por reemplazo agresivo.
ui = ui.replace(
    "from ..core.ollama_client import LM StudioClient",
    "from ..core.ollama_client import OllamaClient"
)

ui = ui.replace(
    "from ..core.ollama_client import LMStudioClient",
    "from ..core.ollama_client import OllamaClient"
)

ui = ui.replace(
    "from ..core.ollama_client import NemotronClient",
    "from ..core.ollama_client import OllamaClient"
)

# Si se reemplazó el nombre de clase dentro del código, lo devolvemos.
ui = ui.replace("LM StudioClient()", "OllamaClient()")
ui = ui.replace("LMStudioClient()", "OllamaClient()")
ui = ui.replace("NemotronClient()", "OllamaClient()")

# Evitar variables con espacios si quedaron por reemplazo textual.
ui = ui.replace("LM StudioClient", "OllamaClient")
ui = ui.replace("self.LM Studio", "self.ollama")
ui = ui.replace("self.lm studio", "self.ollama")

# Mantener textos visibles bonitos, pero no tocar identificadores Python.
ui = ui.replace("[IA] Consultando LM Studio / Nemotron...", "[IA] Consultando LM Studio / Nemotron...")

# Si el atributo principal fue dañado, normalizarlo.
ui = re.sub(r"self\.ollama\s*=\s*OllamaClient\(\)", "self.ollama = OllamaClient()", ui)

# Si no existe la inicialización, agregarla cerca de acciones/tracker.
if "self.ollama = OllamaClient()" not in ui:
    if "self.actions" in ui:
        ui = re.sub(
            r"(self\.actions\s*=.*?\n)",
            r"\1        self.ollama = OllamaClient()\n",
            ui,
            count=1
        )
    else:
        ui = ui.replace(
            "self._build_ui()",
            "self.ollama = OllamaClient()\n        self._build_ui()"
        )

# Reforzar _ask_ollama para usar el cliente actual.
ask_method = '''    def _ask_ollama(self):
        prompt = self.current_text or "Hola Jarvis, responde brevemente qué puedes hacer con esta interfaz holográfica."
        self._log("[IA] Consultando LM Studio / Nemotron...")

        try:
            answer = self.ollama.ask(prompt)
            self.log.append(answer[:2500])
        except Exception as exc:
            self._log(f"[IA ERROR] {exc}")

'''

if "def _ask_ollama(self):" in ui:
    ui = re.sub(
        r"    def _ask_ollama\(self\):.*?(?=\n    def |\n    # |\Z)",
        ask_method,
        ui,
        flags=re.DOTALL
    )
else:
    marker = "    def _handle_gesture"
    pos = ui.find(marker)
    if pos == -1:
        marker = "    def _tick"
        pos = ui.find(marker)
    if pos != -1:
        ui = ui[:pos] + ask_method + "\n" + ui[pos:]

# Botón: si AI CHAT fue cambiado a NEMOTRON, está bien. Si no, lo cambiamos.
ui = ui.replace('("AI CHAT", self._ask_ollama)', '("NEMOTRON", self._ask_ollama)')

ui_file.write_text(ui, encoding="utf-8")

print("hologram_window.py corregido.")


# ============================================================
# 2. Asegurar cliente LM Studio/Nemotron correcto
# ============================================================

client_file.write_text(r'''from __future__ import annotations

import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.

    El nombre OllamaClient se conserva para no romper imports existentes.
    Internamente usa LM Studio + Nemotron 3 Nano 4B.
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
                "LM Studio / Nemotron no respondió correctamente. "
                "Verifica que LM Studio esté en Status: Running, puerto 1234, "
                "y modelo nvidia/nemotron-3-nano-4b cargado. "
                f"Detalle técnico: {exc}"
            )
''', encoding="utf-8")

print("ollama_client.py asegurado con LM Studio/Nemotron.")


# ============================================================
# 3. Verificar que app.py no cargue V4/hotfix externos
# ============================================================

if app_file.exists():
    app = app_file.read_text(encoding="utf-8", errors="replace")

    # Recomendado para esta V3: solo HologramWindow.
    app_file.write_text(r'''from __future__ import annotations

import os
import sys

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"
os.environ["ABSL_LOGGING_MIN_LOG_LEVEL"] = "3"

from PyQt6.QtWidgets import QApplication

from src.jarvis_air.ui.hologram_window import HologramWindow


def main():
    app = QApplication(sys.argv)

    win = HologramWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
''', encoding="utf-8")

    print("app.py dejado solo con HologramWindow V3.")

print("PATCH DE CORRECCIÓN COMPLETADO")
