from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Tuple

import cv2
import numpy as np

try:
    import mediapipe as mp
except Exception:
    mp = None

Point = Tuple[int, int]

# Estabilidad: cuántos frames consecutivos debe mantenerse un gesto para emitirlo.
_STABILITY_FRAMES = 3


@dataclass
class HandState:
    found: bool
    gesture: str = "NO_HAND"
    index_pos: Point = (0, 0)
    thumb_pos: Point = (0, 0)
    pinch: bool = False
    landmarks: Optional[List[Point]] = None
    hand_label: str = "UNKNOWN"      # Left / Right / UNKNOWN
    score: float = 0.0
    hand_count: int = 0


@dataclass
class MultiHandState:
    found: bool = False
    hands: List[HandState] = field(default_factory=list)
    main: HandState = field(default_factory=lambda: HandState(found=False))
    left: Optional[HandState] = None
    right: Optional[HandState] = None
    combo_gesture: str = "NO_HAND"


class HandTracker:
    """Rastreador de manos con MediaPipe.

    Mejoras de precisión sobre V2:
    - Buffer de estabilidad: un gesto se emite solo si se mantiene
      _STABILITY_FRAMES frames consecutivos (elimina flicker).
    - Distancias normalizadas por ancho de palma para invariancia de escala.
    - Detección de pulgar mejorada usando vector palma-wrist.
    - Pinch con umbral adaptativo basado en tamaño de mano.
    - Reconocimiento de THUMB_UP robusto.
    """

    def __init__(
        self,
        max_num_hands: int = 2,
        detection_confidence: float = 0.65,
        tracking_confidence: float = 0.65,
    ):
        self.available  = mp is not None and hasattr(mp, "solutions")
        self.mp_hands   = None
        self.hands      = None
        self.mp_draw    = None

        # Buffer por ID de mano (0 / 1)
        self._gesture_buf: List[Deque[str]] = [
            deque(maxlen=_STABILITY_FRAMES),
            deque(maxlen=_STABILITY_FRAMES),
        ]

        if self.available:
            self.mp_hands = mp.solutions.hands
            self.hands    = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=max_num_hands,
                min_detection_confidence=detection_confidence,
                min_tracking_confidence=tracking_confidence,
                model_complexity=1,
            )
            self.mp_draw = mp.solutions.drawing_utils

    # ── Utilidades geométricas ────────────────────────────────────────────────

    @staticmethod
    def _dist(a: Point, b: Point) -> float:
        return float(np.linalg.norm(
            np.array(a, dtype=np.float32) - np.array(b, dtype=np.float32)
        ))

    @staticmethod
    def _finger_is_up(pts: List[Point], tip: int, pip: int,
                      wrist: Point) -> bool:
        """El dedo está levantado si la punta está más lejos de la muñeca
        que la articulación PIP en el eje Y (o distancia directa)."""
        dist_tip = HandTracker._dist(pts[tip], wrist)
        dist_pip = HandTracker._dist(pts[pip], wrist)
        return dist_tip > dist_pip

    def _palm_width(self, pts: List[Point]) -> float:
        """Distancia entre nudillos meñique e índice — referencia de escala."""
        return max(1.0, self._dist(pts[5], pts[17]))

    def _thumb_is_up(self, pts: List[Point]) -> bool:
        """Pulgar levantado: punta más lejos de wrist que nudillo y
        índice doblado (para no confundir con PINCH o OPEN_HAND)."""
        wrist = pts[0]
        d_tip = self._dist(pts[4], wrist)
        d_mcp = self._dist(pts[2], wrist)
        # Índice doblado
        index_down = not self._finger_is_up(pts, 8, 6, wrist)
        return d_tip > d_mcp * 1.15 and index_down

    # ── Reconocimiento de gesto ───────────────────────────────────────────────

    def recognize_gesture(self, pts: List[Point]) -> Tuple[str, bool]:
        wrist = pts[0]
        pw    = self._palm_width(pts)

        index_up  = self._finger_is_up(pts, 8,  6,  wrist)
        middle_up = self._finger_is_up(pts, 12, 10, wrist)
        ring_up   = self._finger_is_up(pts, 16, 14, wrist)
        pinky_up  = self._finger_is_up(pts, 20, 18, wrist)

        # Pinch: distancia pulgar-índice normalizada por ancho de palma
        pinch_dist = self._dist(pts[4], pts[8])
        pinch      = pinch_dist < pw * 0.38       # umbral más estricto que V2

        up_count = sum([index_up, middle_up, ring_up, pinky_up])

        if pinch:
            return "PINCH", True
        if up_count >= 4:
            return "OPEN_HAND", False
        if up_count == 0:
            return "FIST", False
        if index_up and not middle_up and not ring_up and not pinky_up:
            return "POINT", False
        if index_up and middle_up and not ring_up and not pinky_up:
            return "TWO_FINGERS", False
        if index_up and middle_up and ring_up and not pinky_up:
            return "THREE_FINGERS", False
        if self._thumb_is_up(pts):
            return "THUMB_UP", False
        return "UNKNOWN", False

    def _stable_gesture(self, idx: int, raw: str) -> str:
        """Devuelve el gesto solo cuando se repite _STABILITY_FRAMES veces."""
        buf = self._gesture_buf[idx]
        buf.append(raw)
        if len(buf) == _STABILITY_FRAMES and len(set(buf)) == 1:
            return raw
        # Mientras no hay estabilidad, devuelve el último gesto emitido
        # (el primero del buffer si hay datos, UNKNOWN en arranque)
        return buf[0] if buf else "UNKNOWN"

    # ── Proceso de frame ──────────────────────────────────────────────────────

    def process(self, frame_bgr):
        if not self.available:
            return frame_bgr, MultiHandState(
                found=False, combo_gesture="MEDIAPIPE_NOT_AVAILABLE"
            )

        h, w, _ = frame_bgr.shape
        rgb     = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result  = self.hands.process(rgb)
        states: List[HandState] = []

        if result.multi_hand_landmarks:
            for i, hand_lm in enumerate(result.multi_hand_landmarks):
                # Extraer landmarks en píxeles
                pts: List[Point] = [
                    (int(lm.x * w), int(lm.y * h))
                    for lm in hand_lm.landmark
                ]

                raw_gesture, pinch = self.recognize_gesture(pts)
                gesture = self._stable_gesture(i, raw_gesture)

                hand_label = "UNKNOWN"
                score      = 0.0
                if result.multi_handedness and i < len(result.multi_handedness):
                    cls        = result.multi_handedness[i].classification[0]
                    hand_label = cls.label
                    score      = float(cls.score)

                state = HandState(
                    found      = True,
                    gesture    = gesture,
                    index_pos  = pts[8],
                    thumb_pos  = pts[4],
                    pinch      = pinch,
                    landmarks  = pts,
                    hand_label = hand_label,
                    score      = score,
                )
                states.append(state)

                # ── Colores visuales por mano ──────────────────────────────
                if hand_label == "Left":
                    lc = (0,  210, 255)   # BGR: naranja-cian
                    cc = (255, 190, 60)
                else:
                    lc = (255, 85, 255)   # BGR: magenta
                    cc = (60, 230, 255)

                self.mp_draw.draw_landmarks(
                    frame_bgr,
                    hand_lm,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_draw.DrawingSpec(color=lc, thickness=2, circle_radius=3),
                    self.mp_draw.DrawingSpec(color=cc, thickness=2),
                )

                # Punta de índice destacada
                ix, iy = pts[8]
                cv2.circle(frame_bgr, (ix, iy), 10, lc, 2)
                cv2.circle(frame_bgr, (ix, iy),  3, lc, -1)

                # Etiqueta encima de la mano
                label = f"{hand_label}: {gesture}"
                cv2.putText(frame_bgr, label, (ix + 14, iy - 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.56, lc, 2)

                # Línea pulgar-índice si hay pinch
                if pinch:
                    tx, ty = pts[4]
                    cv2.line(frame_bgr, (ix, iy), (tx, ty), (50, 200, 255), 2)
                    cv2.circle(frame_bgr,
                               ((ix + tx) // 2, (iy + ty) // 2), 7, (0, 200, 255), -1)

        if not states:
            return frame_bgr, MultiHandState(found=False, combo_gesture="NO_HAND")

        # ── Clasificación multi-mano ───────────────────────────────────────
        left  = next((s for s in states if s.hand_label == "Left"),  None)
        right = next((s for s in states if s.hand_label == "Right"), None)
        main  = right or states[0]

        gestures = [s.gesture for s in states]
        combo    = main.gesture

        if len(states) >= 2:
            if gestures.count("OPEN_HAND") >= 2:
                combo = "BOTH_OPEN_HANDS"
            elif gestures.count("FIST") >= 2:
                combo = "BOTH_FISTS"
            elif "PINCH" in gestures and "OPEN_HAND" in gestures:
                combo = "PINCH_AND_OPEN"
            elif gestures.count("TWO_FINGERS") >= 2:
                combo = "BOTH_TWO_FINGERS"
            elif gestures.count("THREE_FINGERS") >= 2:
                combo = "BOTH_THREE_FINGERS"
            elif "THREE_FINGERS" in gestures:
                combo = "SCROLL_MODE"
            elif "THUMB_UP" in gestures:
                combo = "COMMAND_MODE"

        for s in states:
            s.hand_count = len(states)

        return frame_bgr, MultiHandState(
            found         = True,
            hands         = states,
            main          = main,
            left          = left,
            right         = right,
            combo_gesture = combo,
        )
