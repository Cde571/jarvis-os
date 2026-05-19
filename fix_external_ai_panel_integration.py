from pathlib import Path
import re

ui_file = Path("src/jarvis_air/ui/hologram_window.py")
text = ui_file.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()

# Remover cualquier AIMiniPanel roto entre class AIMiniPanel y class HologramWindow
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

if start is not None and start < end:
    lines = lines[:start] + lines[end:]

text = "\n".join(lines) + "\n"

# Agregar import del panel externo
import_line = "from .ai_mini_panel import AIMiniPanel\n"

if "from .ai_mini_panel import AIMiniPanel" not in text:
    marker = "from ..core.ollama_client import OllamaClient"
    if marker in text:
        text = text.replace(marker, marker + "\n" + import_line.strip(), 1)
    else:
        # Insertar antes de class HologramWindow
        pos = text.find("class HologramWindow")
        text = text[:pos] + import_line + "\n" + text[pos:]

# Asegurar atributo ai_mini_panel
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

# Asegurar método _open_ai_panel
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

# NEMOTRON abre mini panel
text = text.replace('("NEMOTRON", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
text = text.replace('("AI CHAT", self._ask_ollama)', '("NEMOTRON", self._open_ai_panel)')
text = text.replace('HoloButton("NEMOTRON", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')
text = text.replace('HoloButton("AI CHAT", self._ask_ollama', 'HoloButton("NEMOTRON", self._open_ai_panel')

ui_file.write_text(text, encoding="utf-8")

print("hologram_window.py limpiado e integrado con ai_mini_panel.py")
