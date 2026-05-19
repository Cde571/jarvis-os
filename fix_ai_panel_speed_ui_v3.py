from pathlib import Path
from datetime import datetime
import re

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"
client_file = root / "src" / "jarvis_air" / "core" / "ollama_client.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

if not client_file.exists():
    raise RuntimeError("No encontré ollama_client.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_ui = root / f"backup_ui_fast_ai_panel_{stamp}.py"
backup_client = root / f"backup_client_fast_lmstudio_{stamp}.py"

backup_ui.write_text(ui_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
backup_client.write_text(client_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

# ============================================================
# 1. Cliente rápido: LM Studio /v1/chat/completions
# ============================================================

client_file.write_text(r'''from __future__ import annotations

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
''', encoding="utf-8")


# ============================================================
# 2. Reemplazar AIMiniPanel por versión más clara
# ============================================================

text = ui_file.read_text(encoding="utf-8", errors="replace")

# imports
if "import threading" not in text:
    if "import time" in text:
        text = text.replace("import time\n", "import time\nimport threading\n", 1)
    elif "import math" in text:
        text = text.replace("import math\n", "import math\nimport time\nimport threading\n", 1)
    else:
        text = "import time\nimport threading\n" + text

if "pyqtSignal" not in text:
    text = text.replace(
        "from PyQt6.QtCore import ",
        "from PyQt6.QtCore import pyqtSignal, ",
        1
    )

needed_widgets = [
    "QDialog", "QTextEdit", "QLineEdit", "QVBoxLayout",
    "QHBoxLayout", "QLabel", "QPushButton", "QFrame"
]

if "from PyQt6.QtWidgets import (" in text:
    for widget in needed_widgets:
        if widget not in text:
            text = text.replace(
                "from PyQt6.QtWidgets import (",
                f"from PyQt6.QtWidgets import (\n    {widget},",
                1
            )

lines = text.splitlines()

start = None
end = None

for i, line in enumerate(lines):
    if line.startswith("class AIMiniPanel"):
        start = i
        break

for i, line in enumerate(lines):
    if line.startswith("class HologramWindow"):
        end = i
        break

if end is None:
    raise RuntimeError("No encontré class HologramWindow")

new_panel = '''class AIMiniPanel(QDialog):
    """
    Mini ventana interna de IA para JARVIS.
    Diseño más limpio, respuesta rápida y área de chat más clara.
    """

    response_ready = pyqtSignal(str)
    response_error = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)

        self.parent_window = parent
        self.last_answer = ""

        self.setWindowTitle("JARVIS · NEMOTRON AI")
        self.setModal(False)
        self.resize(840, 640)
        self.setMinimumSize(760, 560)

        self.setStyleSheet("""
            QDialog {
                background-color: rgba(2, 10, 20, 248);
                border: 1px solid rgba(0, 234, 255, 190);
            }

            QLabel {
                color: rgb(230, 255, 255);
                font-family: Segoe UI;
            }

            QFrame#HeaderBox {
                background-color: rgba(0, 30, 50, 210);
                border: 1px solid rgba(0, 234, 255, 90);
            }

            QTextEdit {
                background-color: rgba(0, 15, 28, 245);
                color: rgb(235, 255, 255);
                border: 1px solid rgba(0, 234, 255, 120);
                padding: 12px;
                font-family: Consolas;
                font-size: 14px;
                selection-background-color: rgba(0, 234, 255, 80);
            }

            QLineEdit {
                background-color: rgba(0, 20, 38, 245);
                color: rgb(235, 255, 255);
                border: 1px solid rgba(0, 234, 255, 130);
                padding: 11px;
                font-family: Consolas;
                font-size: 15px;
            }

            QPushButton {
                background-color: rgba(0, 75, 110, 230);
                color: rgb(245, 255, 255);
                border: 1px solid rgba(0, 234, 255, 160);
                padding: 10px 14px;
                font-weight: 900;
                letter-spacing: 1px;
                min-height: 34px;
            }

            QPushButton:hover {
                background-color: rgba(0, 125, 170, 235);
                border: 1px solid rgba(255, 47, 167, 230);
            }

            QPushButton:disabled {
                background-color: rgba(30, 45, 55, 180);
                color: rgba(220, 220, 220, 120);
                border: 1px solid rgba(120, 120, 120, 90);
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QFrame()
        header.setObjectName("HeaderBox")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(4)

        self.title = QLabel("JARVIS · NEMOTRON AI")
        self.title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 900;
                letter-spacing: 5px;
                color: rgb(0, 234, 255);
            }
        """)
        header_layout.addWidget(self.title)

        self.status = QLabel("Estado: listo · LM Studio conectado · Nemotron 3 Nano 4B")
        self.status.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: rgba(230, 255, 255, 200);
            }
        """)
        header_layout.addWidget(self.status)

        root.addWidget(header)

        self.prompt = QLineEdit()
        self.prompt.setPlaceholderText("Escribe tu pregunta aquí y presiona Enter...")
        root.addWidget(self.prompt)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.btn_send = QPushButton("ENVIAR")
        self.btn_listen = QPushButton("HABLAR")
        self.btn_repeat = QPushButton("REPETIR VOZ")
        self.btn_clear = QPushButton("LIMPIAR")

        row.addWidget(self.btn_send)
        row.addWidget(self.btn_listen)
        row.addWidget(self.btn_repeat)
        row.addWidget(self.btn_clear)

        root.addLayout(row)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setText(
            "JARVIS listo.\\n\\n"
            "Escribe una pregunta y presiona ENVIAR.\\n"
            "La respuesta aparecerá aquí dentro de la app.\\n"
            "Para respuestas rápidas, usa preguntas cortas.\\n"
        )
        root.addWidget(self.chat, 1)

        self.response_ready.connect(self.finish_response)
        self.response_error.connect(self.show_error)

        self.btn_send.clicked.connect(self.ask_text)
        self.btn_listen.clicked.connect(self.listen_in_app)
        self.btn_repeat.clicked.connect(lambda: self.speak_text(self.last_answer))
        self.btn_clear.clicked.connect(self.clear_all)
        self.prompt.returnPressed.connect(self.ask_text)

    def clear_all(self):
        self.prompt.clear()
        self.chat.clear()
        self.last_answer = ""
        self.status.setText("Estado: limpio · listo para nuevo comando")
        self.chat.setText("JARVIS listo.\\n")

    def append_chat(self, text):
        self.chat.append(text)
        bar = self.chat.verticalScrollBar()
        bar.setValue(bar.maximum())

    def finish_response(self, response: str):
        response = (response or "").strip()

        if not response:
            response = "No recibí una respuesta textual de Nemotron."

        self.last_answer = response
        self.append_chat("\\nJARVIS:\\n" + response + "\\n")
        self.status.setText("Estado: respuesta recibida.")
        self.btn_send.setEnabled(True)

        try:
            self.parent_window._log("[NEMOTRON] Respuesta recibida dentro de la mini interfaz.")
        except Exception:
            pass

    def show_error(self, message: str):
        self.append_chat("\\n[ERROR]\\n" + str(message) + "\\n")
        self.status.setText("Estado: error.")
        self.btn_send.setEnabled(True)

    def ask_text(self):
        text = self.prompt.text().strip()

        if not text:
            text = getattr(self.parent_window, "current_text", "").strip()

        if not text:
            self.status.setText("Estado: escribe o dicta algo primero.")
            self.append_chat("\\n[AVISO] No hay texto para enviar.")
            return

        self.status.setText("Estado: consultando Nemotron...")
        self.append_chat("\\nTÚ:\\n" + text + "\\n\\nJARVIS: pensando...")

        self.btn_send.setEnabled(False)

        def worker():
            try:
                response = self.parent_window.ollama.ask(text)
                self.response_ready.emit(response)
            except Exception as exc:
                self.response_error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def speak_text(self, text: str):
        text = (text or "").strip()

        if not text:
            self.status.setText("Estado: no hay respuesta para repetir.")
            return

        def worker():
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", 170)
                engine.setProperty("volume", 0.95)
                engine.say(text[:1000])
                engine.runAndWait()
            except Exception as exc:
                self.response_error.emit(f"VOICE ERROR: {exc}")

        self.status.setText("Estado: reproduciendo voz...")
        threading.Thread(target=worker, daemon=True).start()

    def listen_in_app(self):
        self.status.setText("Estado: preparando micrófono...")
        self.append_chat("\\n[MIC] Escuchando...")

        def worker():
            try:
                import speech_recognition as sr

                recognizer = sr.Recognizer()

                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)

                detected_text = recognizer.recognize_google(audio, language="es-ES")

                def apply_text():
                    self.prompt.setText(detected_text)
                    self.append_chat("\\nTÚ / VOZ:\\n" + detected_text)
                    self.ask_text()

                QTimer.singleShot(0, apply_text)

            except Exception as exc:
                self.response_error.emit(
                    "No pude escuchar desde el micrófono. "
                    "Puedes escribir manualmente. "
                    f"Detalle: {exc}"
                )

        threading.Thread(target=worker, daemon=True).start()

'''

new_panel_lines = new_panel.splitlines()

if start is not None:
    lines = lines[:start] + new_panel_lines + [""] + lines[end:]
else:
    lines = lines[:end] + new_panel_lines + [""] + lines[end:]

text = "\n".join(lines) + "\n"

# Asegurar _open_ai_panel
open_ai_panel = '''    def _open_ai_panel(self):
        """
        Abre la mini interfaz IA interna.
        """
        try:
            if not hasattr(self, "ai_mini_panel"):
                self.ai_mini_panel = None

            if self.ai_mini_panel is None:
                self.ai_mini_panel = AIMiniPanel(self)

            self.ai_mini_panel.show()
            self.ai_mini_panel.raise_()
            self.ai_mini_panel.activateWindow()
            self._log("[IA] Mini interfaz Nemotron abierta dentro de JARVIS.")

        except Exception as exc:
            self._log(f"[IA PANEL ERROR] {exc}")

'''

if "def _open_ai_panel(self):" not in text:
    markers = ["    def _ask_ollama", "    def _handle_gesture", "    def _tick"]
    insert_pos = -1

    for marker in markers:
        insert_pos = text.find(marker)
        if insert_pos != -1:
            break

    if insert_pos == -1:
        raise RuntimeError("No pude insertar _open_ai_panel")

    text = text[:insert_pos] + open_ai_panel + "\n" + text[insert_pos:]

# Asegurar atributo
if "self.ai_mini_panel = None" not in text:
    if "self.ollama = OllamaClient()" in text:
        text = text.replace(
            "self.ollama = OllamaClient()",
            "self.ollama = OllamaClient()\n        self.ai_mini_panel = None",
            1
        )
    else:
        text = text.replace(
            "self._build_ui()",
            "self.ai_mini_panel = None\n        self._build_ui()",
            1
        )

# Botón NEMOTRON abre panel interno
text = text.replace('("NEMOTRON", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
text = text.replace('("AI CHAT", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
text = text.replace('HoloButton("NEMOTRON", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')
text = text.replace('HoloButton("AI CHAT", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')

ui_file.write_text(text, encoding="utf-8")

print("PATCH OK")
print("- Cliente LM Studio optimizado")
print("- Mini panel IA rediseñado")
print("- Respuesta vuelve por pyqtSignal")
print("- max_tokens reducido para responder más rápido")
print(f"Backup UI: {backup_ui}")
print(f"Backup client: {backup_client}")
