from pathlib import Path
import re
from datetime import datetime

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"
voice_file = root / "src" / "jarvis_air" / "voice_bridge.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = root / f"backup_fix_voice_ai_method_{stamp}.py"
backup.write_text(ui_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

ui = ui_file.read_text(encoding="utf-8", errors="replace")

# ============================================================
# 1. Asegurar imports necesarios
# ============================================================

if "import webbrowser" not in ui:
    if "import time" in ui:
        ui = ui.replace("import time\n", "import time\nimport webbrowser\n")
    elif "import math" in ui:
        ui = ui.replace("import math\n", "import math\nimport webbrowser\n")
    else:
        ui = "import webbrowser\n" + ui

# Import opcional de voice_bridge
if "_HAS_VOICE_BRIDGE" not in ui:
    marker = "from ..core.ollama_client import OllamaClient"
    if marker in ui:
        ui = ui.replace(
            marker,
            marker + """

try:
    from ..voice_bridge import start_server as _start_voice_server
    _HAS_VOICE_BRIDGE = True
except Exception:
    _start_voice_server = None
    _HAS_VOICE_BRIDGE = False
"""
        )
    else:
        ui = ui.replace(
            "class AIMiniPanel",
            """try:
    from ..voice_bridge import start_server as _start_voice_server
    _HAS_VOICE_BRIDGE = True
except Exception:
    _start_voice_server = None
    _HAS_VOICE_BRIDGE = False


class AIMiniPanel"""
        )

# ============================================================
# 2. Asegurar atributo self._voice_server
# ============================================================

if "self._voice_server = None" not in ui:
    if "self.ai_mini_panel = None" in ui:
        ui = ui.replace(
            "self.ai_mini_panel = None",
            "self.ai_mini_panel = None\n        self._voice_server = None"
        )
    elif "self.ollama = OllamaClient()" in ui:
        ui = ui.replace(
            "self.ollama = OllamaClient()",
            "self.ollama = OllamaClient()\n        self._voice_server = None"
        )
    else:
        ui = ui.replace(
            "self._build_ui()",
            "self._voice_server = None\n        self._build_ui()"
        )

# ============================================================
# 3. Insertar método _open_voice_ai dentro de HologramWindow
# ============================================================

voice_method = '''    def _open_voice_ai(self):
        """
        Abre la interfaz de voz local de JARVIS.
        Usa voice_bridge.py si existe; si no, abre el navegador como fallback.
        """
        try:
            if _HAS_VOICE_BRIDGE and _start_voice_server is not None:
                if getattr(self, "_voice_server", None) is None:
                    self._voice_server = _start_voice_server(open_browser=True)
                    self._log("[VOICE AI] Servidor iniciado en http://127.0.0.1:8765")
                else:
                    webbrowser.open("http://127.0.0.1:8765")
                    self._log("[VOICE AI] Interfaz de voz reabierta.")
                return

            webbrowser.open("http://127.0.0.1:8765")
            self._log("[VOICE AI] Abriendo http://127.0.0.1:8765")

        except Exception as exc:
            self._log(f"[VOICE AI ERROR] {exc}")
            try:
                webbrowser.open("http://127.0.0.1:8765")
            except Exception:
                pass

'''

if "def _open_voice_ai(self):" not in ui:
    # Insertarlo antes de _open_ai_panel si existe, o antes de _ask_ollama
    markers = [
        "    def _open_ai_panel",
        "    def _ask_ollama",
        "    def _handle_gesture",
        "    def _tick",
    ]

    pos = -1
    for marker in markers:
        pos = ui.find(marker)
        if pos != -1:
            break

    if pos == -1:
        raise RuntimeError("No encontré dónde insertar _open_voice_ai")

    ui = ui[:pos] + voice_method + "\n" + ui[pos:]
else:
    ui = re.sub(
        r"    def _open_voice_ai\(self\):.*?(?=\n    def |\n    # |\Z)",
        voice_method,
        ui,
        flags=re.DOTALL
    )

# ============================================================
# 4. Mejorar texto del panel IA si quedó "abriendo Voice AI" fijo
# ============================================================

ui = ui.replace(
    'self.status.setText("Estado: abriendo Voice AI...")',
    'self.status.setText("Estado: abriendo Voice AI local...")'
)

# ============================================================
# 5. Asegurar que el botón NEMOTRON abra el panel, no consulta directa
# ============================================================

ui = ui.replace('("NEMOTRON", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
ui = ui.replace('("AI CHAT", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
ui = ui.replace('HoloButton("NEMOTRON", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')
ui = ui.replace('HoloButton("AI CHAT", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')

ui_file.write_text(ui, encoding="utf-8")

print("PATCH OK")
print("- _open_voice_ai agregado a HologramWindow")
print("- Voice AI usa voice_bridge.py si existe")
print("- Fallback abre http://127.0.0.1:8765")
print("- Botón NEMOTRON conserva mini interfaz")
print(f"Backup: {backup}")
