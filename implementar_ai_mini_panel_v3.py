from pathlib import Path
import re
from datetime import datetime

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = root / f"backup_ai_mini_panel_{stamp}.py"
backup.write_text(ui_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

ui = ui_file.read_text(encoding="utf-8", errors="replace")

# ============================================================
# 1. Asegurar imports necesarios
# ============================================================

if "from PyQt6.QtWidgets import" in ui:
    # Agregar widgets si no están
    needed = ["QDialog", "QTextEdit", "QLineEdit", "QVBoxLayout", "QHBoxLayout", "QLabel", "QPushButton"]
    for item in needed:
        if item not in ui:
            ui = ui.replace(
                "from PyQt6.QtWidgets import (",
                "from PyQt6.QtWidgets import (\n    " + item + ","
            )

# Si el import está en una sola línea, reforzar con bloque extra seguro
if "QDialog" not in ui:
    ui = ui.replace(
        "from PyQt6.QtCore import",
        "from PyQt6.QtWidgets import QDialog, QTextEdit, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel, QPushButton\nfrom PyQt6.QtCore import"
    )

# threading para no congelar interfaz al consultar IA
if "import threading" not in ui:
    if "import time" in ui:
        ui = ui.replace("import time\n", "import time\nimport threading\n")
    else:
        ui = ui.replace("import math\n", "import math\nimport time\nimport threading\n")

# ============================================================
# 2. Crear clase AIMiniPanel antes de HologramWindow
# ============================================================

if "class AIMiniPanel(QDialog):" not in ui:
    marker = "class HologramWindow"
    pos = ui.find(marker)

    if pos == -1:
        raise RuntimeError("No encontré class HologramWindow")

    mini_panel_code = r'''
class AIMiniPanel(QDialog):
    """
    Mini interfaz interna para hablar con Nemotron.
    No reemplaza el diseño principal; aparece encima como panel holográfico.
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.parent_window = parent
        self.setWindowTitle("JARVIS · NEMOTRON AI")
        self.setModal(False)
        self.resize(620, 520)

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
        self.prompt.setPlaceholderText("Escribe tu pregunta o comando para JARVIS...")
        root.addWidget(self.prompt)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.btn_send = QPushButton("ENVIAR A NEMOTRON")
        self.btn_voice = QPushButton("HABLAR CON IA")
        self.btn_open_voice = QPushButton("ABRIR VOICE AI")
        self.btn_clear = QPushButton("LIMPIAR")

        row.addWidget(self.btn_send)
        row.addWidget(self.btn_voice)
        row.addWidget(self.btn_open_voice)
        row.addWidget(self.btn_clear)

        root.addLayout(row)

        self.answer = QTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setText(
            "JARVIS listo.\n\n"
            "Puedes escribir una pregunta y presionar ENVIAR A NEMOTRON.\n"
            "También puedes usar HABLAR CON IA para abrir el modo de voz local."
        )
        root.addWidget(self.answer, 1)

        self.btn_send.clicked.connect(self.ask_text)
        self.btn_voice.clicked.connect(self.open_voice_ai)
        self.btn_open_voice.clicked.connect(self.open_voice_ai)
        self.btn_clear.clicked.connect(self.clear_all)
        self.prompt.returnPressed.connect(self.ask_text)

    def clear_all(self):
        self.prompt.clear()
        self.answer.clear()
        self.status.setText("Estado: limpio · listo para nuevo comando")

    def open_voice_ai(self):
        self.status.setText("Estado: abriendo Voice AI...")
        try:
            self.parent_window._open_voice_ai()
            self.answer.append("\n[VOICE AI] Interfaz de voz abierta en navegador local.")
        except Exception as exc:
            self.answer.append(f"\n[VOICE AI ERROR] {exc}")

    def ask_text(self):
        text = self.prompt.text().strip()

        if not text:
            text = getattr(self.parent_window, "current_text", "").strip()

        if not text:
            self.status.setText("Estado: escribe algo primero.")
            self.answer.append("\n[AVISO] No hay texto para enviar.")
            return

        self.status.setText("Estado: consultando LM Studio / Nemotron...")
        self.answer.append(f"\nTÚ: {text}\nJARVIS: pensando...")

        def worker():
            try:
                response = self.parent_window.ollama.ask(text)
            except Exception as exc:
                response = f"[ERROR IA] {exc}"

            def update_ui():
                self.answer.append("\n" + response + "\n")
                self.status.setText("Estado: respuesta recibida.")
                try:
                    self.parent_window._log("[NEMOTRON] Respuesta recibida en mini interfaz.")
                except Exception:
                    pass

            QTimer.singleShot(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

'''
    ui = ui[:pos] + mini_panel_code + "\n" + ui[pos:]

# ============================================================
# 3. Inicializar referencia al panel IA en __init__
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
            "self.ai_mini_panel = None\n        self._build_ui()"
        )

# ============================================================
# 4. Agregar método _open_ai_panel en HologramWindow
# ============================================================

open_ai_method = '''    def _open_ai_panel(self):
        """
        Abre mini interfaz interna para Nemotron.
        El botón IA ya no dispara consultas repetidas directamente.
        """
        try:
            if self.ai_mini_panel is None:
                self.ai_mini_panel = AIMiniPanel(self)

            self.ai_mini_panel.show()
            self.ai_mini_panel.raise_()
            self.ai_mini_panel.activateWindow()
            self._log("[IA] Mini interfaz Nemotron abierta.")

        except Exception as exc:
            self._log(f"[IA PANEL ERROR] {exc}")

'''

if "def _open_ai_panel(self):" not in ui:
    marker = "    def _ask_ollama"
    pos = ui.find(marker)

    if pos == -1:
        marker = "    def _handle_gesture"
        pos = ui.find(marker)

    if pos == -1:
        raise RuntimeError("No encontré dónde insertar _open_ai_panel")

    ui = ui[:pos] + open_ai_method + "\n" + ui[pos:]

# ============================================================
# 5. Cambiar el botón NEMOTRON para abrir mini interfaz
# ============================================================

# Reemplazos comunes de quick launch
ui = ui.replace('("NEMOTRON", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
ui = ui.replace('("AI CHAT", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
ui = ui.replace('("NEMOTRON",  self._ask_ollama)', '("NEMOTRON",  self._open_ai_panel)')
ui = ui.replace('("AI CHAT",  self._ask_ollama)', '("NEMOTRON",  self._open_ai_panel)')

# Si hay HoloButton directo con self._ask_ollama
ui = ui.replace('HoloButton("NEMOTRON", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')
ui = ui.replace('HoloButton("AI CHAT", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')

# ============================================================
# 6. Mantener _ask_ollama disponible, pero ya no como botón principal
# ============================================================

ask_method = '''    def _ask_ollama(self):
        """
        Consulta directa a Nemotron. Se conserva para uso interno.
        El botón principal debe abrir _open_ai_panel().
        """
        prompt = self.current_text or "Hola Jarvis, preséntate brevemente."
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

ui_file.write_text(ui, encoding="utf-8")

print("PATCH OK")
print("- Botón NEMOTRON abre mini interfaz interna")
print("- Mini interfaz tiene prompt, respuesta y botón de voz")
print("- HABLAR CON IA abre Voice AI local")
print("- Consulta directa a Nemotron se conserva internamente")
print(f"Backup: {backup}")
