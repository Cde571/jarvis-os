from pathlib import Path
import re
from datetime import datetime

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"
pc_file = root / "src" / "jarvis_air" / "control" / "pc_actions.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = root / f"backup_restore_air_click_{stamp}.py"
backup.write_text(ui_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

ui = ui_file.read_text(encoding="utf-8", errors="replace")

# ============================================================
# 1. Asegurar imports necesarios
# ============================================================

if "QApplication" not in ui:
    ui = ui.replace(
        "from PyQt6.QtWidgets import (",
        "from PyQt6.QtWidgets import (\n    QApplication,"
    )

if "QPushButton" not in ui:
    ui = ui.replace(
        "from PyQt6.QtWidgets import (",
        "from PyQt6.QtWidgets import (\n    QPushButton,"
    )

if "import time" not in ui:
    if "import math" in ui:
        ui = ui.replace("import math\n", "import math\nimport time\n")
    else:
        ui = "import time\n" + ui

# ============================================================
# 2. Asegurar cooldown de air click
# ============================================================

if "_AIR_CLICK_COOLDOWN_S" not in ui:
    if "_PINCH_COOLDOWN_S" in ui:
        ui = ui.replace(
            "_PINCH_COOLDOWN_S = 1.0",
            "_PINCH_COOLDOWN_S = 1.0\n_AIR_CLICK_COOLDOWN_S = 0.85"
        )
    else:
        ui = ui.replace(
            "BG_FILL",
            "_PINCH_COOLDOWN_S = 1.0\n_AIR_CLICK_COOLDOWN_S = 0.85\n\nBG_FILL",
            1
        )

if "self._last_air_click_time = 0.0" not in ui:
    if "self._last_pinch_click_time = 0.0" in ui:
        ui = ui.replace(
            "self._last_pinch_click_time = 0.0",
            "self._last_pinch_click_time = 0.0\n        self._last_air_click_time = 0.0"
        )
    elif "self._pinch_down = False" in ui:
        ui = ui.replace(
            "self._pinch_down = False",
            "self._pinch_down = False\n        self._last_air_click_time = 0.0"
        )
    else:
        ui = ui.replace(
            "self._build_ui()",
            "self._last_air_click_time = 0.0\n        self._build_ui()"
        )

# ============================================================
# 3. Crear método _air_click si no existe
# ============================================================

air_click_method = '''    def _air_click(self, hand):
        """
        Click universal con pinza.
        1. Si el puntero está encima de un QPushButton de JARVIS, ejecuta ese botón.
        2. Si no hay botón interno, intenta click externo con PCActions.click_at().
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

        # Primero buscar botón interno bajo el puntero
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

        # Si no hay botón interno, click externo opcional
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
    markers = [
        "    def _update_dwell",
        "    def _handle_gesture",
        "    def _tick",
        "    def closeEvent",
    ]

    pos = -1

    for marker in markers:
        pos = ui.find(marker)

        if pos != -1:
            break

    if pos == -1:
        raise RuntimeError("No pude ubicar dónde insertar _air_click")

    ui = ui[:pos] + air_click_method + "\n" + ui[pos:]
else:
    # Reemplazar versión rota si existe.
    ui = re.sub(
        r"    def _air_click\(self.*?\):.*?(?=\n    def |\n    # |\Z)",
        air_click_method,
        ui,
        flags=re.DOTALL
    )

ui_file.write_text(ui, encoding="utf-8")

# ============================================================
# 4. Asegurar PCActions.click_at si falta
# ============================================================

if pc_file.exists():
    pc = pc_file.read_text(encoding="utf-8", errors="replace")

    if "def click_at(self, x: int, y: int)" not in pc:
        click_at_method = '''    def click_at(self, x: int, y: int):
        if pyautogui is None:
            return ActionResult(False, "Pinza detectada — sin botón bajo el puntero")
        try:
            pyautogui.click(x, y)
            return ActionResult(True, f"Click ejecutado en ({x}, {y})")
        except Exception as exc:
            return ActionResult(False, f"No pude hacer click externo: {exc}")

'''

        match = re.search(
            r"    def click\(self\).*?(?=\n    def |\Z)",
            pc,
            flags=re.DOTALL
        )

        if match:
            pc = pc[:match.end()] + "\n" + click_at_method + pc[match.end():]
        else:
            pc += "\n\n" + click_at_method

        pc_file.write_text(pc, encoding="utf-8")

print("PATCH OK")
print("- _air_click restaurado")
print("- click interno sobre botones restaurado")
print("- fallback click_at restaurado")
print("- cooldown air click agregado")
print(f"Backup: {backup}")
