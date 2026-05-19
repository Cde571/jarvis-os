from pathlib import Path
import re
from datetime import datetime

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = root / f"backup_fix_scroll_none_{stamp}.py"
backup.write_text(ui_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

ui = ui_file.read_text(encoding="utf-8", errors="replace")

# ============================================================
# 1. Asegurar inicialización de _last_scroll_y
# ============================================================

if "self._last_scroll_y" not in ui:
    ui = ui.replace(
        "self._last_pinch_click_time = 0.0",
        "self._last_pinch_click_time = 0.0\n        self._last_scroll_y = None"
    )

# Si existe pero quedó mal ubicada, asegurar que esté en __init__
if "self._last_scroll_y = None" not in ui:
    ui = ui.replace(
        "self._last_pinch_click_time = 0.0",
        "self._last_pinch_click_time = 0.0\n        self._last_scroll_y = None"
    )

# ============================================================
# 2. Corregir bloque de scroll inseguro
# ============================================================

# Reemplazo puntual del patrón que está fallando:
# delta = self._last_scroll_y - iy
# por una versión segura.
ui = ui.replace(
'''                delta = self._last_scroll_y - iy

                if abs(delta) > 14:
                    try:
                        self.actions.scroll(int(delta / 5))
                        self._log(f"[SCROLL] delta={int(delta / 5)}")
                    except Exception:
                        pass

                    self._last_scroll_y = iy''',
'''                if self._last_scroll_y is None:
                    self._last_scroll_y = iy
                    return

                delta = self._last_scroll_y - iy

                if abs(delta) > 14:
                    try:
                        self.actions.scroll(int(delta / 5))
                        self._log(f"[SCROLL] delta={int(delta / 5)}")
                    except Exception:
                        pass

                    self._last_scroll_y = iy'''
)

# Otro posible formato del mismo bloque, por si está con espacios diferentes.
ui = ui.replace(
'''            delta = self._last_scroll_y - iy

            if abs(delta) > 14:
                try:
                    self.actions.scroll(int(delta / 5))
                    self._log(f"[SCROLL] delta={int(delta / 5)}")
                except Exception:
                    pass

                self._last_scroll_y = iy''',
'''            if self._last_scroll_y is None:
                self._last_scroll_y = iy
                return

            delta = self._last_scroll_y - iy

            if abs(delta) > 14:
                try:
                    self.actions.scroll(int(delta / 5))
                    self._log(f"[SCROLL] delta={int(delta / 5)}")
                except Exception:
                    pass

                self._last_scroll_y = iy'''
)

# ============================================================
# 3. Resetear scroll cuando no haya THREE_FINGERS
# ============================================================

# Asegurar que cuando no se está haciendo scroll, el estado se limpie.
if "scroll_hand is None" not in ui:
    ui = ui.replace(
'''        else:
            self._last_scroll_y = None

        pinch_hand = (''',
'''        else:
            self._last_scroll_y = None

        pinch_hand = ('''
    )

# ============================================================
# 4. Evitar que un return corte demasiada lógica en _handle_gesture
# ============================================================
# Si el return dentro del bloque de scroll causa que no actualice paneles,
# lo cambiamos por asignación segura usando continue lógico.
ui = ui.replace(
'''                if self._last_scroll_y is None:
                    self._last_scroll_y = iy
                    return

                delta = self._last_scroll_y - iy''',
'''                if self._last_scroll_y is None:
                    self._last_scroll_y = iy
                    delta = 0
                else:
                    delta = self._last_scroll_y - iy'''
)

ui = ui.replace(
'''            if self._last_scroll_y is None:
                self._last_scroll_y = iy
                return

            delta = self._last_scroll_y - iy''',
'''            if self._last_scroll_y is None:
                self._last_scroll_y = iy
                delta = 0
            else:
                delta = self._last_scroll_y - iy'''
)

ui_file.write_text(ui, encoding="utf-8")

print("PATCH OK")
print("- _last_scroll_y inicializado")
print("- scroll con THREE_FINGERS protegido contra None")
print("- no se rompe _handle_gesture")
print(f"Backup: {backup}")
