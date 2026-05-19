from pathlib import Path
from datetime import datetime
import re

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = root / f"backup_before_force_aiminipanel_replace_{stamp}.py"
backup.write_text(ui_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

text = ui_file.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()

# ============================================================
# 1. Encontrar bloque AIMiniPanel roto por líneas
# ============================================================

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

# ============================================================
# 2. AIMiniPanel limpio. Usamos \\n dentro de strings para evitar
#    strings rotos con saltos reales.
# ============================================================

new_panel = '''class AIMiniPanel(QDialog):
    """
    Mini interfaz interna para hablar con Nemotron dentro de JARVIS.
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.parent_window = parent
        self.last_answer = ""

        self.setWindowTitle("JARVIS · NEMOTRON AI")
        self.setModal(False)
        self.resize(700, 580)

        self.setStyleSheet("""
            QDialog {
                background-color: rgba(3, 12, 24, 245);
                border: 1px solid rgba(0, 234, 255, 180);
            }

            QLabel {
                color: rgb(230, 255, 255);
                font-family: Segoe UI;
            }

            QTextEdit, QLineEdit {
                background-color: rgba(0, 18, 34, 235);
                color: rgb(235, 255, 255);
                border: 1px solid rgba(0, 234, 255, 110);
                padding: 8px;
                font-family: Consolas;
                font-size: 13px;
            }

            QPushButton {
                background-color: rgba(0, 70, 105, 220);
                color: rgb(235, 255, 255);
                border: 1px solid rgba(0, 234, 255, 150);
                padding: 9px 12px;
                font-weight: 900;
                letter-spacing: 1px;
            }

            QPushButton:hover {
                background-color: rgba(0, 120, 160, 230);
                border: 1px solid rgba(255, 47, 167, 220);
            }

            QPushButton:pressed {
                background-color: rgba(255, 47, 167, 180);
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.title = QLabel("JARVIS · NEMOTRON AI")
        self.title.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: 900;
                letter-spacing: 4px;
                color: rgb(0, 234, 255);
            }
        """)
        root.addWidget(self.title)

        self.status = QLabel("Estado: listo · Backend: LM Studio · Modelo: Nemotron 3 Nano 4B")
        self.status.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: rgba(230, 255, 255, 190);
                padding-bottom: 4px;
            }
        """)
        root.addWidget(self.status)

        self.prompt = QLineEdit()
        self.prompt.setPlaceholderText("Escribe tu pregunta aquí...")
        root.addWidget(self.prompt)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.btn_send = QPushButton("ENVIAR A NEMOTRON")
        self.btn_listen = QPushButton("HABLAR CON JARVIS")
        self.btn_repeat = QPushButton("REPETIR VOZ")
        self.btn_clear = QPushButton("LIMPIAR")

        row.addWidget(self.btn_send)
        row.addWidget(self.btn_listen)
        row.addWidget(self.btn_repeat)
        row.addWidget(self.btn_clear)

        root.addLayout(row)

        self.answer = QTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setText(
            "JARVIS listo dentro de la aplicación.\\\\n\\\\n"
            "Escribe una pregunta y presiona ENVIAR A NEMOTRON.\\\\n"
            "La respuesta debe aparecer aquí mismo, sin abrir navegador.\\\\n\\\\n"
            "Backend: LM Studio / Nemotron local."
        )
        root.addWidget(self.answer, 1)

        self.btn_send.clicked.connect(self.ask_text)
        self.btn_listen.clicked.connect(self.listen_in_app)
        self.btn_repeat.clicked.connect(lambda: self.speak_text(self.last_answer))
        self.btn_clear.clicked.connect(self.clear_all)
        self.prompt.returnPressed.connect(self.ask_text)

    def clear_all(self):
        self.prompt.clear()
        self.answer.clear()
        self.last_answer = ""
        self.status.setText("Estado: limpio · listo para nuevo comando")

    def append_answer(self, text):
        self.answer.append(text)
        bar = self.answer.verticalScrollBar()
        bar.setValue(bar.maximum())

    def speak_text(self, text: str):
        text = (text or "").strip()

        if not text:
            self.status.setText("Estado: no hay respuesta para repetir.")
            return

        def worker():
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", 165)
                engine.setProperty("volume", 0.95)
                engine.say(text[:1200])
                engine.runAndWait()
            except Exception as exc:
                QTimer.singleShot(0, lambda: self.append_answer(f"\\\\n[VOICE ERROR] {exc}"))

        self.status.setText("Estado: reproduciendo voz...")
        threading.Thread(target=worker, daemon=True).start()

    def listen_in_app(self):
        self.status.setText("Estado: preparando micrófono...")
        self.append_answer("\\\\n[MIC] Escuchando desde JARVIS...")

        def worker():
            try:
                import speech_recognition as sr

                recognizer = sr.Recognizer()

                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    QTimer.singleShot(0, lambda: self.status.setText("Estado: escuchando... habla ahora."))
                    audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)

                detected_text = recognizer.recognize_google(audio, language="es-ES")

                def update_prompt():
                    self.prompt.setText(detected_text)
                    self.append_answer(f"\\\\nTÚ / VOZ: {detected_text}")
                    self.status.setText("Estado: voz detectada. Consultando Nemotron...")
                    self.ask_text()

                QTimer.singleShot(0, update_prompt)

            except Exception as exc:
                def show_error():
                    self.status.setText("Estado: error de micrófono.")
                    self.append_answer(
                        "\\\\n[MIC ERROR] No pude escuchar dentro de la app.\\\\n"
                        "Puedes escribir manualmente y presionar ENVIAR A NEMOTRON.\\\\n"
                        f"Detalle: {exc}"
                    )

                QTimer.singleShot(0, show_error)

        threading.Thread(target=worker, daemon=True).start()

    def ask_text(self):
        text = self.prompt.text().strip()

        if not text:
            text = getattr(self.parent_window, "current_text", "").strip()

        if not text:
            self.status.setText("Estado: escribe o dicta algo primero.")
            self.append_answer("\\\\n[AVISO] No hay texto para enviar.")
            return

        self.status.setText("Estado: consultando LM Studio / Nemotron...")
        self.append_answer(f"\\\\nTÚ: {text}\\\\nJARVIS: pensando...")

        self.btn_send.setEnabled(False)

        def worker():
            try:
                response = self.parent_window.ollama.ask(text)
            except Exception as exc:
                response = f"[ERROR IA] {exc}"

            def update_ui():
                self.last_answer = response
                self.append_answer("\\\\nJARVIS:\\\\n" + response + "\\\\n")
                self.status.setText("Estado: respuesta recibida.")
                self.btn_send.setEnabled(True)

                try:
                    self.parent_window._log("[NEMOTRON] Respuesta recibida dentro de la mini interfaz.")
                except Exception:
                    pass

            QTimer.singleShot(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

'''

new_panel_lines = new_panel.splitlines()

if start is not None:
    lines = lines[:start] + new_panel_lines + [""] + lines[end:]
else:
    lines = lines[:end] + new_panel_lines + [""] + lines[end:]

text = "\n".join(lines) + "\n"

# ============================================================
# 3. Asegurar imports necesarios
# ============================================================

if "import threading" not in text:
    if "import time" in text:
        text = text.replace("import time\n", "import time\nimport threading\n", 1)
    elif "import math" in text:
        text = text.replace("import math\n", "import math\nimport time\nimport threading\n", 1)
    else:
        text = "import time\nimport threading\n" + text

needed_widgets = [
    "QDialog", "QTextEdit", "QLineEdit", "QVBoxLayout",
    "QHBoxLayout", "QLabel", "QPushButton", "QApplication"
]

if "from PyQt6.QtWidgets import (" in text:
    for widget in needed_widgets:
        if widget not in text:
            text = text.replace(
                "from PyQt6.QtWidgets import (",
                f"from PyQt6.QtWidgets import (\n    {widget},",
                1
            )

# ============================================================
# 4. Asegurar _open_ai_panel dentro de HologramWindow
# ============================================================

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
    insert_markers = ["    def _ask_ollama", "    def _handle_gesture", "    def _tick"]
    insert_pos = -1

    for marker in insert_markers:
        insert_pos = text.find(marker)
        if insert_pos != -1:
            break

    if insert_pos == -1:
        raise RuntimeError("No pude insertar _open_ai_panel")

    text = text[:insert_pos] + open_ai_panel + "\n" + text[insert_pos:]

# ============================================================
# 5. Asegurar atributo ai_mini_panel
# ============================================================

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

# ============================================================
# 6. NEMOTRON abre panel interno
# ============================================================

text = text.replace('("NEMOTRON", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
text = text.replace('("AI CHAT", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
text = text.replace('HoloButton("NEMOTRON", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')
text = text.replace('HoloButton("AI CHAT", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')

ui_file.write_text(text, encoding="utf-8")

print("PATCH OK")
print("- AIMiniPanel roto eliminado por rango de líneas")
print("- AIMiniPanel limpio insertado")
print("- Strings multilinea corregidos")
print("- NEMOTRON abre mini panel interno")
print(f"Backup: {backup}")
