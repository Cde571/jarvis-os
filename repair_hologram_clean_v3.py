from pathlib import Path
import re
import py_compile
import shutil
from datetime import datetime

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"
pc_file = root / "src" / "jarvis_air" / "control" / "pc_actions.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
broken_backup = root / f"backup_broken_before_clean_repair_{stamp}.py"
broken_backup.write_text(ui_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

print(f"Backup del archivo roto: {broken_backup}")

# ============================================================
# 1. Buscar backup válido que compile
# ============================================================

candidates = []

for pattern in [
    "backup_fix_import_lmstudio_*.py",
    "backup_disable_dwell_click_*.py",
    "backup_fix_scroll_none_*.py",
    "backup_handle_gesture_safe_*.py",
    "backup_voice_inside_app_*.py",
    "backup_restore_air_click_*.py",
    "backup_fix_aiminipanel_string_*.py",
    "backup_*.py",
]:
    candidates.extend(root.glob(pattern))

# Ordenar: más recientes primero
candidates = sorted(set(candidates), key=lambda p: p.stat().st_mtime, reverse=True)

valid_backup = None

for candidate in candidates:
    try:
        py_compile.compile(str(candidate), doraise=True)
        valid_backup = candidate
        break
    except Exception:
        continue

if valid_backup is not None:
    shutil.copyfile(valid_backup, ui_file)
    print(f"Restaurado desde backup válido: {valid_backup}")
else:
    print("No encontré backup válido. Intentaré reparar el archivo actual directamente.")

# Leer archivo restaurado o actual
ui = ui_file.read_text(encoding="utf-8", errors="replace")

# ============================================================
# 2. Limpiar posibles bloques huérfanos después de errores previos
# ============================================================

# Si quedaron líneas con indentación absurda antes de class/def, intentamos normalizar
# mediante reemplazo completo de AIMiniPanel y métodos clave.
ui = re.sub(
    r"(?ms)^class AIMiniPanel\(QDialog\):.*?(?=^class HologramWindow)",
    "",
    ui
)

# ============================================================
# 3. Imports seguros
# ============================================================

if "import time" not in ui:
    if "import math" in ui:
        ui = ui.replace("import math\n", "import math\nimport time\n")
    else:
        ui = "import time\n" + ui

if "import threading" not in ui:
    ui = ui.replace("import time\n", "import time\nimport threading\n")

if "import webbrowser" not in ui:
    ui = ui.replace("import time\n", "import time\nimport webbrowser\n")

# Asegurar widgets de PyQt
widgets_needed = ["QApplication", "QDialog", "QTextEdit", "QLineEdit", "QVBoxLayout", "QHBoxLayout", "QLabel", "QPushButton"]

if "from PyQt6.QtWidgets import (" in ui:
    for widget in widgets_needed:
        if widget not in ui:
            ui = ui.replace(
                "from PyQt6.QtWidgets import (",
                f"from PyQt6.QtWidgets import (\n    {widget},"
            )
else:
    ui = "from PyQt6.QtWidgets import QApplication, QDialog, QTextEdit, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel, QPushButton\n" + ui

# ============================================================
# 4. Insertar AIMiniPanel limpio antes de HologramWindow
# ============================================================

ai_panel = r'''class AIMiniPanel(QDialog):
    """
    Mini interfaz interna para hablar con Nemotron dentro de JARVIS.
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.parent_window = parent
        self.last_answer = ""

        self.setWindowTitle("JARVIS · NEMOTRON AI")
        self.setModal(False)
        self.resize(660, 560)

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
        self.prompt.setPlaceholderText("Escribe tu pregunta o usa HABLAR CON JARVIS...")
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
            "JARVIS listo dentro de la aplicación.\\n\\n"
            "Funciones disponibles:\\n"
            "1. Escribe una pregunta y presiona ENVIAR A NEMOTRON.\\n"
            "2. Presiona HABLAR CON JARVIS para dictar por micrófono.\\n"
            "3. Presiona REPETIR VOZ para escuchar la última respuesta.\\n\\n"
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
                QTimer.singleShot(0, lambda: self.answer.append(f"\\n[VOICE ERROR] {exc}"))

        self.status.setText("Estado: reproduciendo voz...")
        threading.Thread(target=worker, daemon=True).start()

    def listen_in_app(self):
        self.status.setText("Estado: preparando micrófono...")
        self.answer.append("\\n[MIC] Escuchando desde JARVIS...")

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
                    self.answer.append(f"\\nTÚ / VOZ: {text}")
                    self.status.setText("Estado: voz detectada. Consultando Nemotron...")
                    self.ask_text()

                QTimer.singleShot(0, update_prompt)

            except Exception as exc:
                def show_error():
                    self.status.setText("Estado: error de micrófono.")
                    self.answer.append(
                        "\\n[MIC ERROR] No pude escuchar dentro de la app.\\n"
                        "Soluciones:\\n"
                        "1. Verifica permiso del micrófono en Windows.\\n"
                        "2. Instala PyAudio correctamente.\\n"
                        "3. Usa texto manual si el micrófono falla.\\n"
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
            self.answer.append("\\n[AVISO] No hay texto para enviar.")
            return

        self.status.setText("Estado: consultando LM Studio / Nemotron...")
        self.answer.append(f"\\nTÚ: {text}\\nJARVIS: pensando...")

        def worker():
            try:
                response = self.parent_window.ollama.ask(text)
            except Exception as exc:
                response = f"[ERROR IA] {exc}"

            def update_ui():
                self.last_answer = response
                self.answer.append("\\n" + response + "\\n")
                self.status.setText("Estado: respuesta recibida.")

                try:
                    self.parent_window._log("[NEMOTRON] Respuesta recibida en mini interfaz.")
                except Exception:
                    pass

                self.speak_text(response)

            QTimer.singleShot(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

'''

pos = ui.find("class HologramWindow")

if pos == -1:
    raise RuntimeError("No encontré class HologramWindow")

ui = ui[:pos] + ai_panel + "\n\n" + ui[pos:]

# ============================================================
# 5. Asegurar atributo ai_mini_panel
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

# ============================================================
# 6. Asegurar _open_ai_panel
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

if "def _open_ai_panel(self):" not in ui:
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
# 7. Asegurar _air_click
# ============================================================

if "_AIR_CLICK_COOLDOWN_S" not in ui:
    if "_PINCH_COOLDOWN_S" in ui:
        ui = ui.replace("_PINCH_COOLDOWN_S = 1.0", "_PINCH_COOLDOWN_S = 1.0\n_AIR_CLICK_COOLDOWN_S = 0.85")
    else:
        ui = "_PINCH_COOLDOWN_S = 1.0\n_AIR_CLICK_COOLDOWN_S = 0.85\n" + ui

if "self._last_air_click_time = 0.0" not in ui:
    if "self._last_pinch_click_time = 0.0" in ui:
        ui = ui.replace("self._last_pinch_click_time = 0.0", "self._last_pinch_click_time = 0.0\n        self._last_air_click_time = 0.0")
    else:
        ui = ui.replace("self._build_ui()", "self._last_air_click_time = 0.0\n        self._build_ui()", 1)

air_click = '''    def _air_click(self, hand):
        """
        Click universal con pinza.
        """
        now_click = time.monotonic()

        if now_click - getattr(self, "_last_air_click_time", 0.0) < _AIR_CLICK_COOLDOWN_S:
            return

        self._last_air_click_time = now_click

        try:
            global_point = self.mapToGlobal(self.pointer)
        except Exception as exc:
            self._log(f"[AIR CLICK ERROR] No pude mapear puntero: {exc}")
            return

        try:
            widget = QApplication.widgetAt(global_point)
        except Exception:
            widget = None

        current = widget

        while current is not None:
            if isinstance(current, QPushButton) and current.isVisible() and current.isEnabled():
                try:
                    text = current.text()
                except Exception:
                    text = "BOTÓN"

                self._log(f"[AIR CLICK] {text}")

                try:
                    current.click()
                except Exception as exc:
                    self._log(f"[AIR CLICK ERROR] No pude ejecutar botón: {exc}")

                return

            try:
                current = current.parentWidget()
            except Exception:
                current = None

        label = getattr(hand, "hand_label", "UNKNOWN")

        try:
            if hasattr(self.actions, "click_at"):
                result = self.actions.click_at(global_point.x(), global_point.y())
            elif hasattr(self.actions, "click"):
                result = self.actions.click()
            else:
                self._log("[AIR CLICK] Pinza detectada — sin botón bajo el puntero")
                return

            if getattr(result, "ok", False):
                self._log(f"[AIR CLICK] Click externo con mano {label}")
            else:
                msg = getattr(result, "message", "Pinza detectada — sin botón bajo el puntero")
                self._log(f"[AIR CLICK] {msg}")

        except Exception as exc:
            self._log(f"[AIR CLICK ERROR] {exc}")

'''

if "def _air_click(self" not in ui:
    marker = "    def _handle_gesture"
    insert_pos = ui.find(marker)

    if insert_pos == -1:
        marker = "    def _tick"
        insert_pos = ui.find(marker)

    if insert_pos == -1:
        raise RuntimeError("No pude insertar _air_click")

    ui = ui[:insert_pos] + air_click + "\n" + ui[insert_pos:]

# ============================================================
# 8. Botón NEMOTRON abre mini panel
# ============================================================

ui = ui.replace('("NEMOTRON", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
ui = ui.replace('("AI CHAT", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
ui = ui.replace('HoloButton("NEMOTRON", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')
ui = ui.replace('HoloButton("AI CHAT", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')

ui_file.write_text(ui, encoding="utf-8")

# ============================================================
# 9. Asegurar click_at en PCActions
# ============================================================

if pc_file.exists():
    pc = pc_file.read_text(encoding="utf-8", errors="replace")

    if "def click_at(self, x: int, y: int)" not in pc:
        method = '''    def click_at(self, x: int, y: int):
        if pyautogui is None:
            return ActionResult(False, "Pinza detectada — sin botón bajo el puntero")
        try:
            pyautogui.click(x, y)
            return ActionResult(True, f"Click ejecutado en ({x}, {y})")
        except Exception as exc:
            return ActionResult(False, f"No pude hacer click externo: {exc}")

'''

        match = re.search(r"    def click\(self\).*?(?=\n    def |\Z)", pc, flags=re.DOTALL)

        if match:
            pc = pc[:match.end()] + "\n" + method + pc[match.end():]
        else:
            pc += "\n\n" + method

        pc_file.write_text(pc, encoding="utf-8")

print("REPARACION LIMPIA OK")
print("- Se restauró un backup válido si existía")
print("- AIMiniPanel limpio insertado")
print("- _open_ai_panel asegurado")
print("- _air_click asegurado")
print("- NEMOTRON abre mini panel")
print("- Archivo roto respaldado en:", broken_backup)
