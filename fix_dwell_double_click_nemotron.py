from pathlib import Path
import re
from datetime import datetime

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = root / f"backup_disable_dwell_click_{stamp}.py"
backup.write_text(ui_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

ui = ui_file.read_text(encoding="utf-8", errors="replace")

# ============================================================
# 1. Desactivar click automático por dwell.
#    El dwell seguirá mostrando progreso visual, pero no ejecutará botones.
# ============================================================

new_update_dwell = '''    def _update_dwell(self):
        """
        Dwell visual solamente.
        Antes hacía click automático y duplicaba acciones como NEMOTRON.
        Ahora el click real queda solo con pinza índice + pulgar.
        """
        gp = self.mapToGlobal(self.pointer)
        widget = QApplication.widgetAt(gp)

        btn = None
        tmp = widget

        while tmp is not None:
            if isinstance(tmp, QPushButton) and tmp.isVisible() and tmp.isEnabled():
                btn = tmp
                break
            tmp = tmp.parentWidget()

        if btn is None:
            self.dwell_target = None
            self.dwell_frames = 0
            self._panel_set_line(self.gesture_panel, 4, "DWELL        0%")
            return

        if btn is not self.dwell_target:
            self.dwell_target = btn
            self.dwell_frames = 0

        self.dwell_frames = min(self.dwell_frames + 1, SETTINGS.dwell_frames)
        pct = int((self.dwell_frames / max(1, SETTINGS.dwell_frames)) * 100)

        # Solo indicador visual. No btn.click().
        self._panel_set_line(self.gesture_panel, 4, f"DWELL        {pct}%")

'''

if "def _update_dwell(self):" in ui:
    ui = re.sub(
        r"    def _update_dwell\(self\):.*?(?=\n    def |\n    # |\Z)",
        new_update_dwell,
        ui,
        flags=re.DOTALL
    )
else:
    marker = "    def _tick"
    pos = ui.find(marker)
    if pos == -1:
        raise RuntimeError("No encontré dónde insertar _update_dwell")
    ui = ui[:pos] + new_update_dwell + "\n" + ui[pos:]


# ============================================================
# 2. Reforzar cooldown de AIR CLICK para evitar múltiples pinzas seguidas.
# ============================================================

if "_AIR_CLICK_COOLDOWN_S" not in ui:
    ui = ui.replace(
        "_PINCH_COOLDOWN_S = 1.0",
        "_PINCH_COOLDOWN_S = 1.0\n_AIR_CLICK_COOLDOWN_S = 1.10"
    )

if "self._last_air_click_time" not in ui:
    ui = ui.replace(
        "self._last_pinch_click_time = 0.0",
        "self._last_pinch_click_time = 0.0\n        self._last_air_click_time = 0.0"
    )

# Si existe _air_click, le agregamos bloqueo adicional por tiempo.
if "def _air_click(self, hand:" in ui and "AIR CLICK COOLDOWN GUARD" not in ui:
    ui = ui.replace(
        "    def _air_click(self, hand: HandState):",
        '''    def _air_click(self, hand: HandState):
        # AIR CLICK COOLDOWN GUARD
        now_click = time.monotonic()
        if now_click - getattr(self, "_last_air_click_time", 0.0) < _AIR_CLICK_COOLDOWN_S:
            return
        self._last_air_click_time = now_click'''
    )

# ============================================================
# 3. Mejorar prompt por defecto de Nemotron para que no responda genérico.
# ============================================================

ui = ui.replace(
    'prompt = self.current_text or "Hola Jarvis, responde brevemente qué puedes hacer con esta interfaz holográfica."',
    'prompt = self.current_text or "Hola Jarvis, preséntate como asistente local y dime en 3 puntos qué funciones reales están disponibles ahora: gestos, teclado en aire, OCR, Voice AI, acciones de PC y Nemotron."'
)

ui_file.write_text(ui, encoding="utf-8")

print("PATCH OK")
print("- Dwell ya no hace click automático")
print("- Pinza queda como único click real")
print("- Cooldown adicional en AIR CLICK")
print("- Prompt por defecto de Nemotron mejorado")
print(f"Backup: {backup}")
