from __future__ import annotations

import math
import time
import webbrowser
import threading
from collections import deque
from typing import Callable, List, Optional

import cv2

from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QSize, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap,
    QBrush, QLinearGradient, QRadialGradient, QPolygon, QConicalGradient,
    QFontMetrics
)
from PyQt6.QtWidgets import (
    QLineEdit,
    QDialog,
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QTextEdit, QFrame, QSizePolicy
)

from ..vision.hand_tracker import HandTracker, MultiHandState, HandState
from ..control.pc_actions import PCActions
from ..control.ocr_reader import ScreenReader
from ..core.ollama_client import OllamaClient

try:
    from ..voice_bridge import start_server as _start_voice_server
    _HAS_VOICE_BRIDGE = True
except Exception:
    _start_voice_server = None
    _HAS_VOICE_BRIDGE = False

from ..core.config import SETTINGS

# ─── Paleta holográfica ───────────────────────────────────────────────────────
CYAN        = QColor(0,   234, 255)
CYAN_DIM    = QColor(0,   234, 255, 55)
CYAN_GLOW   = QColor(0,   234, 255, 22)
MAGENTA     = QColor(255, 47,  167)
MAGENTA_DIM = QColor(255, 47,  167, 60)
WHITE_DIM   = QColor(255, 255, 255, 80)
PANEL_FILL  = QColor(0,   20,  40,  26)      # ~10% opacidad — vidrio holográfico
PANEL_BRD   = QColor(0,   234, 255, 55)
BG_FILL     = QColor(2,   7,   17,  195)     # ventana casi transparente

_PINCH_COOLDOWN_S = 1.0

# ─── Intentar psutil para stats en vivo ──────────────────────────────────────
try:
    import psutil as _psutil
    _HAS_PSUTIL = True
except Exception:
    _psutil = None
    _HAS_PSUTIL = False


# ─────────────────────────────────────────────────────────────────────────────
#  HoloButton  —  botón angular holográfico con dwell-ring
# ─────────────────────────────────────────────────────────────────────────────
class HoloButton(QPushButton):
    def __init__(self, text: str, action: Callable | None = None, compact: bool = False):
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36 if compact else 50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.hover_air  = False
        self.dwell_pct  = 0.0          # 0.0–1.0 progreso del dwell
        self._compact   = compact
        if action:
            self.clicked.connect(action)

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        return QSize(max(base.width(), 100), 38 if self._compact else 52)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r   = self.rect().adjusted(2, 2, -2, -2)
        cut = 12 if self._compact else 16

        # ── forma recortada ──────────────────────────────────────
        path = QPainterPath()
        path.moveTo(r.left() + cut, r.top())
        path.lineTo(r.right() - cut, r.top())
        path.lineTo(r.right(), r.top() + cut)
        path.lineTo(r.right(), r.bottom() - cut)
        path.lineTo(r.right() - cut, r.bottom())
        path.lineTo(r.left() + cut, r.bottom())
        path.lineTo(r.left(), r.bottom() - cut)
        path.lineTo(r.left(), r.top() + cut)
        path.closeSubpath()

        # ── fondo ────────────────────────────────────────────────
        grad = QLinearGradient(QPointF(r.topLeft()), QPointF(r.bottomRight()))
        if self.hover_air or self.underMouse():
            grad.setColorAt(0.0, QColor(0, 234, 255, 70))
            grad.setColorAt(1.0, QColor(255, 47, 167, 40))
            pen  = QPen(CYAN, 1.5)
            glow = QColor(0, 234, 255, 40)
        else:
            grad.setColorAt(0.0, QColor(0, 40,  80, 40))
            grad.setColorAt(1.0, QColor(0, 10,  22, 55))
            pen  = QPen(PANEL_BRD, 1)
            glow = QColor(0, 0, 0, 0)

        # ── glow exterior si hover ────────────────────────────────
        if self.hover_air or self.underMouse():
            outer = path.translated(0, 0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(glow))
            p.drawPath(outer)

        p.fillPath(path, QBrush(grad))
        p.setPen(pen)
        p.drawPath(path)

        # ── línea decorativa superior ─────────────────────────────
        p.setPen(QPen(WHITE_DIM, 1))
        p.drawLine(r.left() + cut + 2, r.top() + 3,
                   r.left() + cut + 28, r.top() + 3)

        # ── texto ────────────────────────────────────────────────
        p.setPen(QColor(220, 255, 255))
        f = QFont("Segoe UI", 8 if self._compact else 10, QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 115)
        p.setFont(f)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())

        # ── dwell ring ───────────────────────────────────────────
        if self.dwell_pct > 0.0:
            cx = r.center().x()
            cy = r.center().y()
            rad = min(r.width(), r.height()) // 2 - 4
            pen_ring = QPen(QColor(0, 234, 255, 220), 2.5)
            pen_ring.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen_ring)
            p.setBrush(Qt.BrushStyle.NoBrush)
            span = int(-self.dwell_pct * 360 * 16)
            p.drawArc(QRect(cx - rad, cy - rad, rad * 2, rad * 2), 90 * 16, span)


# ─────────────────────────────────────────────────────────────────────────────
#  HoloPanel  —  contenedor con esquinas recortadas y borde translúcido
# ─────────────────────────────────────────────────────────────────────────────
class HoloPanel(QFrame):
    def __init__(self, title: str = ""):
        super().__init__()
        self.title = title
        self.setObjectName("holoPanel")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r   = self.rect().adjusted(1, 1, -1, -1)
        cut = 20

        path = QPainterPath()
        path.moveTo(r.left() + cut, r.top())
        path.lineTo(r.right() - cut, r.top())
        path.lineTo(r.right(), r.top() + cut)
        path.lineTo(r.right(), r.bottom() - cut)
        path.lineTo(r.right() - cut, r.bottom())
        path.lineTo(r.left() + cut, r.bottom())
        path.lineTo(r.left(), r.bottom() - cut)
        path.lineTo(r.left(), r.top() + cut)
        path.closeSubpath()

        # Fondo vidrio holográfico
        grad = QLinearGradient(QPointF(r.topLeft()), QPointF(r.bottomRight()))
        grad.setColorAt(0,   QColor(0, 30, 60, 22))
        grad.setColorAt(0.5, QColor(0, 15, 35, 16))
        grad.setColorAt(1,   QColor(0,  5, 15, 28))
        p.fillPath(path, QBrush(grad))

        # Borde exterior tenue
        p.setPen(QPen(PANEL_BRD, 1))
        p.drawPath(path)

        # Acento interior top
        p.setPen(QPen(QColor(0, 234, 255, 30), 1))
        p.drawLine(r.left() + cut, r.top() + 5,
                   r.left() + cut + 60, r.top() + 5)
        p.drawLine(r.right() - cut - 60, r.bottom() - 5,
                   r.right() - cut, r.bottom() - 5)

        super().paintEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
#  HologramWindow  —  ventana principal con transparencia real
# ─────────────────────────────────────────────────────────────────────────────

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
        self.status.setText("Estado: abriendo Voice AI local...")
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


class HologramWindow(QWidget):

    # ── Constantes de dwell ───────────────────────────────────────────────────
    DWELL_FRAMES   = 20          # cuántos frames de hover → auto-click
    SCROLL_AMOUNT  = 3           # líneas por gesto de scroll

    def __init__(self):
        super().__init__()

        # Transparencia real de ventana
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("JARVIS Air Interface V3")
        self.resize(1520, 900)

        # Hardware
        self.actions = PCActions()
        self.ocr     = ScreenReader()
        self.ollama = OllamaClient()
        self.ai_mini_panel = None
        self._voice_server = None
        self.tracker = HandTracker(max_num_hands=2)
        self.cap     = cv2.VideoCapture(SETTINGS.camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  960)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)

        # Estado
        self.frame_id           = 0
        self.current_text       = ""
        self.active             = False
        self.keyboard_visible   = True
        self.menu_visible       = True
        self.last_pinch_frame   = 0
        self.last_combo_frame   = 0
        self.pointer            = QPoint(0, 0)
        self.pointer_label      = "RIGHT"
        self.pointer_confidence = 0.0
        self.air_widgets: List[QPushButton] = []

        # Suavizado de puntero
        self._smooth_x: Optional[float] = None
        self._smooth_y: Optional[float] = None

        # Dwell selection
        self._dwell_widget: Optional[QPushButton] = None
        self._dwell_frames: int = 0

        # Animación scan-line
        self._scan_y    = 0
        self._pulse_r   = 17
        self._pulse_dir = 1

        # Para arrastrar la ventana (sin barra de título)
        self._drag_pos: Optional[QPoint] = None

        self._build_ui()

        # Timer principal (≈33 fps)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(30)

        # Timer de stats en vivo
        self._stat_timer = QTimer(self)
        self._stat_timer.timeout.connect(self._update_stats)
        self._stat_timer.start(1000)

    # ── Drag ventana ──────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _e):
        self._drag_pos = None

    # ── Construcción de UI ───────────────────────────────────────────────────
    def _build_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget {
                background: transparent;
                color: #d8ffff;
                font-family: 'Segoe UI', Consolas, Arial;
            }
            QLabel  { color: #d8ffff; background: transparent; }
            QTextEdit {
                background: rgba(0, 12, 28, 0.55);
                border: 1px solid rgba(0, 234, 255, 0.22);
                color: #d8ffff;
                padding: 8px;
                selection-background-color: rgba(0, 234, 255, 0.40);
            }
            QScrollBar:vertical {
                background: rgba(0,234,255,0.06);
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,234,255,0.30);
                border-radius: 3px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # ── Barra superior ─────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(10)

        self.title_lbl = QLabel("J.A.R.V.I.S  AIR INTERFACE  V3")
        self.title_lbl.setStyleSheet(
            "font-size: 24px; font-weight: 900; color: #f0ffff; "
            "letter-spacing: 5px;"
        )
        self.badge = QLabel("● ONLINE · DUAL HAND · DWELL-SELECT")
        self.badge.setStyleSheet(
            "font-size: 11px; font-weight: 800; color: #00eaff; "
            "border: 1px solid rgba(0,234,255,.45); padding: 5px 10px;"
        )
        top.addWidget(self.title_lbl)
        top.addWidget(self.badge)
        top.addStretch(1)

        for t in ["OVERVIEW", "GESTURE CORE", "AIR KEYBOARD", "SYSTEM"]:
            b = HoloButton(t, compact=True)
            top.addWidget(b)
            self.air_widgets.append(b)

        # Botón cerrar
        btn_close = HoloButton("✕", self.close, compact=True)
        btn_close.setFixedWidth(38)
        top.addWidget(btn_close)
        root.addLayout(top)

        # ── Cuerpo ─────────────────────────────────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        # Columna izquierda
        left = QVBoxLayout(); left.setSpacing(8)
        body.addLayout(left, 2)
        self.system_panel = self._make_panel("SYSTEM STATUS", [
            "CPU USAGE     —", "MEMORY        —", "GPU LOAD      —",
            "NETWORK       ACTIVE", "CONTROL       GESTURE"
        ])
        left.addWidget(self.system_panel)
        self.analytics_panel = self._make_panel("CORE ANALYTICS", [
            "DATA STREAM   ACTIVE", "LATENCY       —", "TRACKING      REAL TIME",
            "DWELL         18 FRAMES"
        ])
        left.addWidget(self.analytics_panel)
        self.ai_panel = self._make_panel("AI CAPABILITIES", [
            "NATURAL LANGUAGE", "VISUAL PROCESSING", "CONTEXT AWARENESS",
            "AIR INPUT READY"
        ])
        left.addWidget(self.ai_panel)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(120)
        self.log.append("[BOOT] JARVIS V3 iniciado.")
        self.log.append("[CTRL] Mano derecha = puntero virtual.")
        self.log.append("[CTRL] Pinza = click inmediato.")
        self.log.append("[CTRL] Hover 20 frames = dwell-click automático.")
        self.log.append("[CTRL] Tres dedos arriba/abajo = scroll.")
        self.log.append("[COMBO] Dos manos abiertas = activar interfaz.")
        self.log.append("[COMBO] Dos puños = pausar sistema.")
        left.addWidget(self.log, 1)

        # Columna central
        center = QVBoxLayout(); center.setSpacing(10)
        body.addLayout(center, 5)

        cam_panel = HoloPanel("GESTURE CONTROL")
        cam_layout = QVBoxLayout(cam_panel)
        cam_layout.setContentsMargins(12, 12, 12, 12)

        hdr = QHBoxLayout()
        self.gesture_title = QLabel("GESTURE CONTROL")
        self.gesture_title.setStyleSheet(
            "font-size: 18px; color: #00eaff; font-weight: 900; letter-spacing: 2px;"
        )
        self.mode_label = QLabel("MODE: ADVANCED · SAFE · DWELL-ON")
        self.mode_label.setStyleSheet(
            "font-size: 11px; color: rgba(216,255,255,.70); font-weight: 700;"
        )
        hdr.addWidget(self.gesture_title)
        hdr.addStretch(1)
        hdr.addWidget(self.mode_label)
        cam_layout.addLayout(hdr)

        self.video = QLabel()
        self.video.setMinimumSize(820, 450)
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setStyleSheet(
            "background: rgba(0,10,22,0.55); border: 1px solid rgba(0,234,255,0.30);"
        )
        cam_layout.addWidget(self.video, 1)

        self.status = QLabel("Sistema en pausa. Dos manos abiertas = activar.")
        self.status.setStyleSheet(
            "font-size: 13px; color: #ffffff; padding: 8px; "
            "border: 1px solid rgba(0,234,255,0.28); "
            "background: rgba(0,100,140,0.10);"
        )
        cam_layout.addWidget(self.status)
        center.addWidget(cam_panel, 1)

        # Teclado aéreo
        self.keyboard_frame = HoloPanel("AIR KEYBOARD")
        kb = QVBoxLayout(self.keyboard_frame)
        kb.setContentsMargins(12, 12, 12, 12)
        kb.setSpacing(7)
        self.keyboard_text = QLabel("AIR KEYBOARD · Texto: ")
        self.keyboard_text.setStyleSheet(
            "font-size: 14px; font-weight: 900; color: #82ffff;"
        )
        kb.addWidget(self.keyboard_text)

        grid = QGridLayout(); grid.setSpacing(5)
        rows = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
        self.key_buttons: List[HoloButton] = []
        for ri, row in enumerate(rows):
            off = ri if ri > 0 else 0
            for ci, ch in enumerate(row):
                btn = HoloButton(ch, lambda _, x=ch: self._add_key(x), compact=True)
                self.key_buttons.append(btn)
                self.air_widgets.append(btn)
                grid.addWidget(btn, ri, ci + off)
        kb.addLayout(grid)

        cmd_row = QHBoxLayout(); cmd_row.setSpacing(7)
        for txt, fn in [
            ("123",      lambda: self._add_key("123")),
            ("SPACE",    lambda: self._add_key(" ")),
            ("BACK",     self._backspace),
            ("SEARCH",   self._search_current_text),
            ("CLOSE KB", self.toggle_keyboard),
        ]:
            b = HoloButton(txt, fn, compact=True)
            cmd_row.addWidget(b)
            self.air_widgets.append(b)
        kb.addLayout(cmd_row)
        center.addWidget(self.keyboard_frame)

        # Columna derecha
        right = QVBoxLayout(); right.setSpacing(8)
        body.addLayout(right, 2)

        self.gesture_panel = self._make_panel("GESTURE STATUS", [
            "MANOS        0",
            "RIGHT        NO_HAND",
            "LEFT         NO_HAND",
            "COMBO        NO_HAND",
            "DWELL        0 %",
        ])
        right.addWidget(self.gesture_panel)

        quick = HoloPanel("QUICK LAUNCH")
        ql = QGridLayout(quick)
        ql.setContentsMargins(12, 12, 12, 12)
        ql.setSpacing(7)
        quick_items = [
            ("SEARCH",  self.toggle_keyboard),
            ("APPS",    lambda: self._log("[UI] Panel de apps activo")),
            ("FILES",   lambda: self._run_action(lambda: self.actions.apps["explorer"]())),
            ("CHROME",  lambda: self._run_action(lambda: self.actions.apps["chrome"]())),
            ("CALC",    lambda: self._run_action(lambda: self.actions.apps["calculator"]())),
            ("CODE",    lambda: self._run_action(lambda: self.actions.apps["vscode"]())),
            ("OCR",     self._read_screen),
            ("NEMOTRON", self._open_ai_panel),
        ]
        for i, (txt, fn) in enumerate(quick_items):
            b = HoloButton(txt, fn, compact=True)
            ql.addWidget(b, i // 2, i % 2)
            self.air_widgets.append(b)
        right.addWidget(quick)

        modules = self._make_panel("MODULE STATUS", [
            "NEMOTRON          READY",
            "VOICE CONTROL     READY",
            "OCR               READY",
            "PC ACTIONS        READY",
            "PINCH CLICK       READY",
            "SCROLL            READY",
        ])
        right.addWidget(modules)

        voice = self._make_panel("VOICE / AI", [
            "NEMOTRON       LOCAL",
            "LM STUDIO      RUNNING",
            "VOICE READY    OPTIONAL",
        ])
        right.addWidget(voice)

        # ── Barra inferior ─────────────────────────────────────────────────
        bottom = QHBoxLayout(); bottom.setSpacing(8)
        for txt, fn in [
            ("SEARCH",   self.toggle_keyboard),
            ("APPS",     lambda: self._log("[UI] Usa Quick Launch")),
            ("FILES",    lambda: self._run_action(lambda: self.actions.apps["explorer"]())),
            ("ACTIVATE", self.toggle_active),
            ("MESSAGES", lambda: self._log("[INFO] Usa OCR para mensajes")),
            ("MEDIA",    lambda: self._log("[INFO] Módulo multimedia preparado")),
            ("SETTINGS", lambda: self._log("[INFO] Edita core/config.py")),
        ]:
            b = HoloButton(txt, fn)
            bottom.addWidget(b)
            self.air_widgets.append(b)
        root.addLayout(bottom)

    # ── Paneles de información ────────────────────────────────────────────────
    def _make_panel(self, title: str, lines: List[str]) -> HoloPanel:
        panel = HoloPanel(title)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)
        t = QLabel(title)
        t.setStyleSheet(
            "font-size: 13px; font-weight: 900; color: #f2ffff; letter-spacing: 1px;"
        )
        layout.addWidget(t)
        for line in lines:
            lbl = QLabel("· " + line)
            lbl.setObjectName("panelLine")
            lbl.setStyleSheet("font-size: 11px; color: rgba(216,255,255,.72);")
            layout.addWidget(lbl)
        return panel

    def _panel_set_line(self, panel: HoloPanel, idx: int, text: str):
        """Actualiza la línea idx (0-based) dentro del panel."""
        labels = panel.findChildren(QLabel)
        # labels[0] = título, labels[1..] = líneas
        target = idx + 1
        if target < len(labels):
            labels[target].setText("· " + text)

    # ── Stats en vivo ─────────────────────────────────────────────────────────
    def _update_stats(self):
        if not _HAS_PSUTIL:
            return
        cpu  = _psutil.cpu_percent(interval=None)
        mem  = _psutil.virtual_memory().percent
        self._panel_set_line(self.system_panel, 0, f"CPU USAGE     {cpu:.0f}%")
        self._panel_set_line(self.system_panel, 1, f"MEMORY        {mem:.0f}%")
        lat = self.timer.interval()
        self._panel_set_line(self.analytics_panel, 1, f"LATENCY       {lat} ms")

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _run_action(self, fn):
        res = fn()
        self._log(("[OK] " if res.ok else "[ERROR] ") + res.message)

    def _log(self, msg: str):
        self.log.append(msg)
        self.status.setText(msg)

    def _add_key(self, ch: str):
        self.current_text += ch.lower()
        self.keyboard_text.setText(f"AIR KEYBOARD · Texto: {self.current_text}")

    def _backspace(self):
        self.current_text = self.current_text[:-1]
        self.keyboard_text.setText(f"AIR KEYBOARD · Texto: {self.current_text}")

    def _search_current_text(self):
        self._run_action(lambda: self.actions.search_web(self.current_text))

    def toggle_keyboard(self):
        self.keyboard_visible = not self.keyboard_visible
        self.keyboard_frame.setVisible(self.keyboard_visible)
        self._log("[UI] Teclado " + ("activado" if self.keyboard_visible else "cerrado"))

    def toggle_active(self):
        self.active = not self.active
        self._log("[CORE] Sistema " + ("activo" if self.active else "en pausa"))

    def _read_screen(self):
        text = self.ocr.read_screen_text()
        preview = (text[:1000] if text
                   else "No se detectó texto. Instala Tesseract para OCR real.")
        self._log("[OCR] Texto visible leído.")
        self.log.append(preview)

    def _open_voice_ai(self):
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


    def _open_ai_panel(self):
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


    def _ask_ollama(self):
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


    # ── Gestos ────────────────────────────────────────────────────────────────
    def _handle_gesture(self, state: MultiHandState):
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

    def _select_by_air_pointer(self):
        global_pt = self.mapToGlobal(self.pointer)
        widget    = QApplication.widgetAt(global_pt)
        while widget is not None and not isinstance(widget, QPushButton):
            widget = widget.parentWidget()
        if isinstance(widget, QPushButton) and widget.isVisible() and widget.isEnabled():
            self._log(f"[AIR CLICK] {widget.text()}")
            widget.click()
        else:
            self._log("[AIR CLICK] Pinza detectada — sin botón bajo el puntero")

    # ── Dwell selection ───────────────────────────────────────────────────────
    def _update_dwell(self):
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


    # ── Hover air ────────────────────────────────────────────────────────────
    def _update_air_hover(self):
        gp      = self.mapToGlobal(self.pointer)
        hovered = QApplication.widgetAt(gp)
        for w in self.air_widgets:
            w.hover_air = False
        tmp = hovered
        while tmp is not None:
            if isinstance(tmp, HoloButton):
                tmp.hover_air = True
                break
            tmp = tmp.parentWidget()
        for w in self.air_widgets:
            w.update()

    # ── Mapeo de puntero ──────────────────────────────────────────────────────
    def _map_pointer(self, hand: HandState, frame_w: int, frame_h: int):
        x, y = hand.index_pos
        tx = int((x / max(1, frame_w)) * self.width())
        ty = int((y / max(1, frame_h)) * self.height())
        if self._smooth_x is None:
            self._smooth_x, self._smooth_y = float(tx), float(ty)
        a             = SETTINGS.pointer_smoothing
        self._smooth_x = self._smooth_x * (1 - a) + tx * a
        self._smooth_y = self._smooth_y * (1 - a) + ty * a
        self.pointer   = QPoint(
            max(0, min(self.width() - 1,  int(self._smooth_x))),
            max(0, min(self.height() - 1, int(self._smooth_y))),
        )
        self.pointer_label      = hand.hand_label
        self.pointer_confidence = hand.score
        self._update_air_hover()

    # ── Tick principal ────────────────────────────────────────────────────────
    def _tick(self):
        self.frame_id  += 1
        ok, frame       = self.cap.read()
        if not ok:
            self.video.setText("⚠  No se pudo abrir la cámara. Cambia camera_index en core/config.py")
            return

        if SETTINGS.mirror_camera:
            frame = cv2.flip(frame, 1)

        frame, state = self.tracker.process(frame)
        h, w, _      = frame.shape

        if state.found:
            self._map_pointer(state.main, w, h)
        self._handle_gesture(state)
        self._update_dwell()
        self._draw_hud(frame, state)

        rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        fh, fw, ch = rgb.shape
        qimg = QImage(rgb.data, fw, fh, ch * fw, QImage.Format.Format_RGB888)
        pix  = QPixmap.fromImage(qimg).scaled(
            self.video.width(), self.video.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video.setPixmap(pix)

        # Avanzar animaciones
        self._scan_y = (self._scan_y + 2) % self.height()
        self._pulse_r += self._pulse_dir
        if self._pulse_r >= 24 or self._pulse_r <= 14:
            self._pulse_dir = -self._pulse_dir

        self.update()

    # ── HUD sobre el frame de cámara ─────────────────────────────────────────
    def _draw_hud(self, frame, state: MultiHandState):
        h, w, _ = frame.shape
        # Colores en BGR
        cyan_bgr    = (255, 234,   0)   # cyan = R:0 G:234 B:255 → BGR(255,234,0)
        magenta_bgr = (167,  47, 255)
        green_bgr   = ( 50, 230,  80)
        white_bgr   = (220, 240, 255)

        # Grid de fondo
        for x in range(0, w, 60):
            cv2.line(frame, (x, 0), (x, h), (15, 38, 50), 1)
        for y in range(0, h, 60):
            cv2.line(frame, (0, y), (w, y), (15, 38, 50), 1)

        # Borde angular
        cv2.line(frame, (20, 20), (80, 20), cyan_bgr, 1)
        cv2.line(frame, (20, 20), (20, 80), cyan_bgr, 1)
        cv2.line(frame, (w - 20, 20), (w - 80, 20), cyan_bgr, 1)
        cv2.line(frame, (w - 20, 20), (w - 20, 80), cyan_bgr, 1)
        cv2.line(frame, (20, h - 20), (80, h - 20), cyan_bgr, 1)
        cv2.line(frame, (20, h - 20), (20, h - 80), cyan_bgr, 1)
        cv2.line(frame, (w - 20, h - 20), (w - 80, h - 20), cyan_bgr, 1)
        cv2.line(frame, (w - 20, h - 20), (w - 20, h - 80), cyan_bgr, 1)

        # Anillos centrales
        cv2.circle(frame, (w // 2, h // 2), 120, (80, 180, 220), 1)
        cv2.circle(frame, (w // 2, h // 2), 200, (40, 100, 140), 1)
        cv2.circle(frame, (w // 2, h // 2),   6, cyan_bgr, -1)

        # Texto HUD
        status_str = "ACTIVE" if self.active else "PAUSED"
        col_status = green_bgr if self.active else (80, 80, 200)
        cv2.putText(frame,
            f"HANDS: {len(state.hands)}   COMBO: {state.combo_gesture}",
            (30, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.62, cyan_bgr, 2)
        cv2.putText(frame,
            f"STATUS: {status_str}   PTR: {self.pointer_label}  "
            f"CONF: {self.pointer_confidence:.2f}",
            (30, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.56, col_status, 2)
        cv2.putText(frame,
            f"DWELL: {int(min(1.0, self._dwell_frames / max(1, self.DWELL_FRAMES)) * 100)}%"
            f"   SCROLL: {'ON' if state.left and state.left.gesture == 'THREE_FINGERS' else 'OFF'}",
            (30, 104), cv2.FONT_HERSHEY_SIMPLEX, 0.52, white_bgr, 1)

        # Marcadores de manos
        if state.found:
            for hand in state.hands:
                x, y = hand.index_pos
                col = magenta_bgr if hand.hand_label == "Right" else cyan_bgr
                cv2.circle(frame, (x, y), 12, col, 2)
                cv2.line(frame, (x - 20, y), (x + 20, y), col, 1)
                cv2.line(frame, (x, y - 20), (x, y + 20), col, 1)
                label = f"{hand.hand_label[0]}: {hand.gesture} ({hand.score:.2f})"
                cv2.putText(frame, label, (x + 14, y - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 2)

    # ── paintEvent principal — holografía + transparencia ────────────────────
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Fondo semi-transparente ──────────────────────────────────────────
        p.fillRect(self.rect(), QBrush(BG_FILL))

        # ── Grid holográfico muy tenue ────────────────────────────────────────
        p.setPen(QPen(CYAN_GLOW, 1))
        for x in range(0, w, 38):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 38):
            p.drawLine(0, y, w, y)

        # ── Scan-line animado ─────────────────────────────────────────────────
        scan_grad = QLinearGradient(QPointF(0, self._scan_y - 20),
                                    QPointF(0, self._scan_y + 20))
        scan_grad.setColorAt(0.0, QColor(0, 234, 255,  0))
        scan_grad.setColorAt(0.5, QColor(0, 234, 255, 22))
        scan_grad.setColorAt(1.0, QColor(0, 234, 255,  0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(scan_grad))
        p.drawRect(0, self._scan_y - 20, w, 40)

        # ── Detalles de esquina ───────────────────────────────────────────────
        p.setPen(QPen(QColor(255, 255, 255, 80), 1))
        p.drawLine(22, 50, 60, 18)
        p.drawLine(w - 22, 50, w - 60, 18)
        p.drawLine(22, h - 50, 60, h - 18)
        p.drawLine(w - 22, h - 50, w - 60, h - 18)

        # ── Borde exterior de ventana ─────────────────────────────────────────
        p.setPen(QPen(QColor(0, 234, 255, 45), 1))
        p.drawRect(self.rect().adjusted(1, 1, -1, -1))

        # ── Puntero aéreo ─────────────────────────────────────────────────────
        if self.active:
            x, y = self.pointer.x(), self.pointer.y()

            # Glow exterior
            r_outer = QRadialGradient(QPointF(x, y), 42)
            r_outer.setColorAt(0,   QColor(0, 234, 255, 28))
            r_outer.setColorAt(1,   QColor(0, 234, 255,  0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(r_outer))
            p.drawEllipse(QPoint(x, y), 42, 42)

            # Anillo exterior magenta pulsante
            p.setPen(QPen(QColor(255, 47, 167, 100), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPoint(x, y), self._pulse_r + 12, self._pulse_r + 12)

            # Anillo interior cyan
            p.setPen(QPen(CYAN, 2))
            p.setBrush(QBrush(QColor(0, 234, 255, 30)))
            p.drawEllipse(QPoint(x, y), self._pulse_r, self._pulse_r)

            # Cruz de mira
            p.setPen(QPen(QColor(0, 234, 255, 200), 1))
            p.drawLine(x - 32, y, x - self._pulse_r - 2, y)
            p.drawLine(x + self._pulse_r + 2, y, x + 32, y)
            p.drawLine(x, y - 32, x, y - self._pulse_r - 2)
            p.drawLine(x, y + self._pulse_r + 2, x, y + 32)

            # Puntos cardinales
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(CYAN))
            for dx, dy in [(0, -self._pulse_r), (0, self._pulse_r),
                           (-self._pulse_r, 0), (self._pulse_r, 0)]:
                p.drawEllipse(QPoint(x + dx, y + dy), 2, 2)

            # Etiqueta de confianza
            p.setPen(QPen(CYAN, 1))
            f = QFont("Segoe UI", 8, QFont.Weight.Bold)
            p.setFont(f)
            p.drawText(x + self._pulse_r + 5, y - 5,
                       f"{self.pointer_label}  {self.pointer_confidence:.0%}")

            # Dwell arc alrededor del puntero si está activo
            if self._dwell_frames > 0 and self._dwell_widget:
                pct  = min(1.0, self._dwell_frames / self.DWELL_FRAMES)
                span = int(-pct * 360 * 16)
                pen_dwell = QPen(QColor(255, 200, 0, 220), 2.5)
                pen_dwell.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen_dwell)
                p.setBrush(Qt.BrushStyle.NoBrush)
                rad = self._pulse_r + 8
                p.drawArc(QRect(x - rad, y - rad, rad * 2, rad * 2), 90 * 16, span)

    # ── Cierre limpio ────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self.cap:
            self.cap.release()
        super().closeEvent(event)
