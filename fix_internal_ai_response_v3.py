from pathlib import Path
import re
from datetime import datetime

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = root / f"backup_fix_internal_ai_panel_{stamp}.py"
backup.write_text(ui_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

ui = ui_file.read_text(encoding="utf-8", errors="replace")

# ============================================================
# 1. Imports necesarios
# ============================================================

if "import threading" not in ui:
    if "import time" in ui:
        ui = ui.replace("import time\n", "import time\nimport threading\n")
    elif "import math" in ui:
        ui = ui.replace("import math\n", "import math\nimport time\nimport threading\n")
    else:
        ui = "import time\nimport threading\n" + ui

if "from PyQt6.QtWidgets import (" in ui:
    for widget in ["QDialog", "QTextEdit", "QLineEdit", "QVBoxLayout", "QHBoxLayout", "QLabel", "QPushButton"]:
        if widget not in ui:
            ui = ui.replace(
                "from PyQt6.QtWidgets import (",
                f"from PyQt6.QtWidgets import (\n    {widget},"
            )
else:
    ui = "from PyQt6.QtWidgets import QDialog, QTextEdit, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel, QPushButton\n" + ui

# ============================================================
# 2. Reemplazar AIMiniPanel por versión funcional interna
# ============================================================

new_panel = r'''class AIMiniPanel(QDialog):
    """
    Mini interfaz interna para hablar con Nemotron dentro de JARVIS.
    Usa el mismo cliente IA que ya funciona con LM Studio.
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
            "JARVIS listo dentro de la aplicación.\n\n"
            "Escribe una pregunta y presiona ENVIAR A NEMOTRON.\n"
            "La respuesta debe aparecer aquí mismo, sin abrir navegador.\n\n"
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
                QTimer.singleShot(0, lambda: self.append_answer(f"\n[VOICE ERROR] {exc}"))

        self.status.setText("Estado: reproduciendo voz...")
        threading.Thread(target=worker, daemon=True).start()

    def listen_in_app(self):
        self.status.setText("Estado: preparando micrófono...")
        self.append_answer("\n[MIC] Escuchando desde JARVIS...")

        def worker():
            try:
                import speech_recognition as sr

                recognizer = sr.Recognizer()

                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    QTimer.singleShot(0, lambda: self.status.setText("Estado: escuchando... habla ahora."))
                    audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)

                text = recognizer.recognize_google(audio, language="es-ES")

                def update_prompt():
                    self.prompt.setText(text)
                    self.append_answer(f"\nTÚ / VOZ: {text}")
                    self.status.setText("Estado: voz detectada. Consultando Nemotron...")
                    self.ask_text()

                QTimer.singleShot(0, update_prompt)

            except Exception as exc:
                def show_error():
                    self.status.setText("Estado: error de micrófono.")
                    self.append_answer(
                        "\n[MIC ERROR] No pude escuchar dentro de la app.\n"
                        "Puedes escribir manualmente y presionar ENVIAR A NEMOTRON.\n"
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
            self.append_answer("\n[AVISO] No hay texto para enviar.")
            return

        self.status.setText("Estado: consultando LM Studio / Nemotron...")
        self.append_answer(f"\nTÚ: {text}\nJARVIS: pensando...")

        self.btn_send.setEnabled(False)

        def worker():
            try:
                response = self.parent_window.ollama.ask(text)
            except Exception as exc:
                response = f"[ERROR IA] {exc}"

            def update_ui():
                self.last_answer = response
                self.append_answer("\nJARVIS:\n" + response + "\n")
                self.status.setText("Estado: respuesta recibida.")
                self.btn_send.setEnabled(True)

                try:
                    self.parent_window._log("[NEMOTRON] Respuesta recibida dentro de la mini interfaz.")
                except Exception:
                    pass

            QTimer.singleShot(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

'''

pattern = re.compile(
    r"(?ms)^class AIMiniPanel\(QDialog\):.*?(?=^class HologramWindow)"
)

if pattern.search(ui):
    ui = pattern.sub(new_panel.rstrip() + "\n\n", ui)
else:
    pos = ui.find("class HologramWindow")
    if pos == -1:
        raise RuntimeError("No encontré class HologramWindow")
    ui = ui[:pos] + new_panel + "\n\n" + ui[pos:]

# ============================================================
# 3. Asegurar que HologramWindow tenga panel y método de apertura
# ============================================================

if "self.ai_mini_panel = None" not in ui:
    if "self.ollama = OllamaClient()" in ui:
        ui = ui.replace(
            "self.ollama = OllamaClient()",
            "self.ollama = OllamaClient()\n        self.ai_mini_panel = None"
        )
    else:
        ui = ui.replace(
            "self._build_ui()",
            "self.ai_mini_panel = None\n        self._build_ui()",
            1
        )

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

if "def _open_ai_panel(self):" in ui:
    ui = re.sub(
        r"    def _open_ai_panel\(self\):.*?(?=\n    def |\n    # |\Z)",
        open_ai_panel,
        ui,
        flags=re.DOTALL
    )
else:
    markers = ["    def _ask_ollama", "    def _handle_gesture", "    def _tick"]
    insert_pos = -1

    for marker in markers:
        insert_pos = ui.find(marker)
        if insert_pos != -1:
            break

    if insert_pos == -1:
        raise RuntimeError("No pude insertar _open_ai_panel")

    ui = ui[:insert_pos] + open_ai_panel + "\n" + ui[insert_pos:]

# ============================================================
# 4. Botón NEMOTRON abre mini interfaz, no navegador
# ============================================================

ui = ui.replace('("NEMOTRON", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
ui = ui.replace('("AI CHAT", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
ui = ui.replace('HoloButton("NEMOTRON", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')
ui = ui.replace('HoloButton("AI CHAT", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')

ui_file.write_text(ui, encoding="utf-8")

print("PATCH OK")
print("- AIMiniPanel interno reemplazado")
print("- ENVIAR A NEMOTRON responde dentro de la app")
print("- No abre navegador para responder")
print("- Botón NEMOTRON abre mini interfaz interna")
print(f"Backup: {backup}")
