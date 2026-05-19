from pathlib import Path
import re
from datetime import datetime

root = Path(".")
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"

if not ui_file.exists():
    raise RuntimeError("No encontré hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = root / f"backup_handle_gesture_safe_{stamp}.py"
backup.write_text(ui_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

ui = ui_file.read_text(encoding="utf-8", errors="replace")

# ============================================================
# 1. Asegurar import time
# ============================================================

if "import time" not in ui:
    if "import math" in ui:
        ui = ui.replace("import math\n", "import math\nimport time\n")
    else:
        ui = "import time\n" + ui

# ============================================================
# 2. Asegurar atributos en __init__
# ============================================================

if "self._last_scroll_y = None" not in ui:
    if "self._last_pinch_click_time = 0.0" in ui:
        ui = ui.replace(
            "self._last_pinch_click_time = 0.0",
            "self._last_pinch_click_time = 0.0\n        self._last_scroll_y = None"
        )
    elif "self.last_pinch_frame = 0" in ui:
        ui = ui.replace(
            "self.last_pinch_frame = 0",
            "self.last_pinch_frame = 0\n        self._last_scroll_y = None"
        )
    else:
        ui = ui.replace(
            "self._build_ui()",
            "self._last_scroll_y = None\n        self._build_ui()"
        )

if "self._pinch_down = False" not in ui:
    ui = ui.replace(
        "self._last_scroll_y = None",
        "self._last_scroll_y = None\n        self._pinch_down = False"
    )

if "self._last_pinch_click_time = 0.0" not in ui:
    ui = ui.replace(
        "self._pinch_down = False",
        "self._pinch_down = False\n        self._last_pinch_click_time = 0.0"
    )

if "_PINCH_COOLDOWN_S" not in ui:
    # Insertar constante después de imports/config o al inicio seguro.
    marker = "BG_FILL"
    pos = ui.find(marker)
    if pos != -1:
        end = ui.find("\n", pos)
        ui = ui[:end+1] + "\n_PINCH_COOLDOWN_S = 1.0\n" + ui[end+1:]
    else:
        ui = "_PINCH_COOLDOWN_S = 1.0\n" + ui

# ============================================================
# 3. Reemplazar COMPLETO _handle_gesture
# ============================================================

new_handle = '''    def _handle_gesture(self, state: MultiHandState):
        """
        Manejo robusto de gestos.
        Corrige el crash:
        TypeError: unsupported operand type(s) for -: 'NoneType' and 'int'
        """
        if not getattr(state, "found", False):
            self._pinch_down = False
            self._last_scroll_y = None

            try:
                self._panel_set_line(self.gesture_panel, 0, "MANOS        0")
                self._panel_set_line(self.gesture_panel, 1, "RIGHT        NO_HAND")
                self._panel_set_line(self.gesture_panel, 2, "LEFT         NO_HAND")
                self._panel_set_line(self.gesture_panel, 3, "COMBO        NO_HAND")
                self._panel_set_line(self.gesture_panel, 4, "DWELL        0%")
            except Exception:
                pass

            return

        combo = getattr(state, "combo_gesture", "UNKNOWN")
        hands = getattr(state, "hands", []) or []
        main = getattr(state, "main", None)

        # Activar con dos manos abiertas
        if combo == "BOTH_OPEN_HANDS" and self.frame_id - self.last_combo_frame > 30:
            self.last_combo_frame = self.frame_id
            self.active = True
            self._log("[COMBO] Dos manos abiertas: interfaz activa")

        # Pausar con dos puños
        elif combo == "BOTH_FISTS" and self.frame_id - self.last_combo_frame > 30:
            self.last_combo_frame = self.frame_id
            self.active = False
            self._pinch_down = False
            self._last_scroll_y = None
            self._log("[COMBO] Dos puños: sistema pausado")

        # Teclado con dos dedos en ambas manos
        elif combo == "BOTH_TWO_FINGERS" and self.active and self.frame_id - self.last_combo_frame > 30:
            self.last_combo_frame = self.frame_id
            self.toggle_keyboard()

        # Activar con mano abierta
        if main is not None and getattr(main, "gesture", "") == "OPEN_HAND" and not self.active and self.frame_id % 20 == 0:
            self.active = True
            self._log("[GESTO] Mano abierta: sistema activo")

        # ====================================================
        # Scroll seguro con THREE_FINGERS
        # ====================================================

        scroll_hand = next((h for h in hands if getattr(h, "gesture", "") == "THREE_FINGERS"), None)

        if scroll_hand is not None and self.active:
            try:
                iy = int(scroll_hand.index_pos[1])
            except Exception:
                iy = None

            if iy is not None:
                # Primer frame: solo guardar posición. NO calcular delta.
                if self._last_scroll_y is None:
                    self._last_scroll_y = iy
                else:
                    delta = self._last_scroll_y - iy

                    if abs(delta) > 14:
                        try:
                            if hasattr(self.actions, "scroll"):
                                self.actions.scroll(int(delta / 5))
                            self._log(f"[SCROLL] delta={int(delta / 5)}")
                        except Exception as exc:
                            self._log(f"[SCROLL ERROR] {exc}")

                        self._last_scroll_y = iy
        else:
            self._last_scroll_y = None

        # ====================================================
        # Pinch click
        # ====================================================

        right = getattr(state, "right", None)
        left = getattr(state, "left", None)

        pinch_hand = None

        if right is not None and getattr(right, "gesture", "") == "PINCH":
            pinch_hand = right
        elif left is not None and getattr(left, "gesture", "") == "PINCH":
            pinch_hand = left
        else:
            pinch_hand = next((h for h in hands if getattr(h, "gesture", "") == "PINCH"), None)

        is_pinching = pinch_hand is not None and self.active

        if is_pinching and not self._pinch_down:
            self._pinch_down = True
            now = time.monotonic()

            if now - getattr(self, "_last_pinch_click_time", 0.0) >= _PINCH_COOLDOWN_S:
                self._last_pinch_click_time = now

                try:
                    if hasattr(self, "_last_frame_w") and hasattr(self, "_last_frame_h"):
                        self._map_pointer(pinch_hand, self._last_frame_w, self._last_frame_h)
                except Exception:
                    pass

                try:
                    self._air_click(pinch_hand)
                except Exception as exc:
                    self._log(f"[AIR CLICK ERROR] {exc}")

        elif not is_pinching:
            self._pinch_down = False

        # ====================================================
        # Panel en tiempo real
        # ====================================================

        try:
            self._panel_set_line(self.gesture_panel, 0, f"MANOS        {len(hands)}")
            self._panel_set_line(self.gesture_panel, 1, f"RIGHT        {right.gesture if right else 'NO_HAND'}")
            self._panel_set_line(self.gesture_panel, 2, f"LEFT         {left.gesture if left else 'NO_HAND'}")
            self._panel_set_line(self.gesture_panel, 3, f"COMBO        {combo}")
        except Exception:
            pass

'''

pattern = re.compile(
    r"(?ms)^    def _handle_gesture\(self,.*?\):.*?(?=^    def |\Z)"
)

if not pattern.search(ui):
    raise RuntimeError("No encontré def _handle_gesture para reemplazar")

ui = pattern.sub(new_handle.rstrip() + "\n\n", ui)

# ============================================================
# 4. Asegurar que _tick guarde dimensiones de frame
# ============================================================

if "self._last_frame_w = w" not in ui:
    ui = ui.replace(
'''        frame, state   = self.tracker.process(frame)
        h, w, _        = frame.shape''',
'''        frame, state   = self.tracker.process(frame)
        h, w, _        = frame.shape
        self._last_frame_w = w
        self._last_frame_h = h'''
    )

    ui = ui.replace(
'''        frame, state = self.tracker.process(frame)
        h, w, _ = frame.shape''',
'''        frame, state = self.tracker.process(frame)
        h, w, _ = frame.shape
        self._last_frame_w = w
        self._last_frame_h = h'''
    )

ui_file.write_text(ui, encoding="utf-8")

print("PATCH OK")
print("- _handle_gesture reemplazado completo")
print("- scroll THREE_FINGERS protegido contra None")
print("- pinch click conservado")
print("- panel de gestos conservado")
print(f"Backup: {backup}")
