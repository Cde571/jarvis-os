from __future__ import annotations

import threading

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QTextEdit,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)


class AIMiniPanel(QDialog):
    """
    Mini ventana interna de IA para JARVIS.
    - HABLAR solo dicta texto en la caja.
    - ENVIAR consulta Nemotron.
    - El input se limpia después de enviar.
    - La respuesta aparece dentro de la app.
    """

    response_ready = pyqtSignal(str)
    response_error = pyqtSignal(str)
    voice_ready = pyqtSignal(str)
    voice_error = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)

        self.parent_window = parent
        self.last_answer = ""
        self.is_listening = False
        self.is_asking = False

        self.setWindowTitle("JARVIS · NEMOTRON AI")
        self.setModal(False)
        self.resize(860, 660)
        self.setMinimumSize(780, 580)

        self.setStyleSheet("""
            QDialog {
                background-color: rgba(2, 10, 20, 248);
                border: 1px solid rgba(0, 234, 255, 190);
            }

            QLabel {
                color: rgb(230, 255, 255);
                font-family: Segoe UI;
            }

            QFrame#HeaderBox {
                background-color: rgba(0, 30, 50, 210);
                border: 1px solid rgba(0, 234, 255, 90);
            }

            QTextEdit {
                background-color: rgba(0, 15, 28, 245);
                color: rgb(235, 255, 255);
                border: 1px solid rgba(0, 234, 255, 120);
                padding: 12px;
                font-family: Consolas;
                font-size: 14px;
            }

            QLineEdit {
                background-color: rgba(0, 20, 38, 245);
                color: rgb(235, 255, 255);
                border: 1px solid rgba(0, 234, 255, 130);
                padding: 11px;
                font-family: Consolas;
                font-size: 15px;
            }

            QPushButton {
                background-color: rgba(0, 75, 110, 230);
                color: rgb(245, 255, 255);
                border: 1px solid rgba(0, 234, 255, 160);
                padding: 10px 14px;
                font-weight: 900;
                letter-spacing: 1px;
                min-height: 34px;
            }

            QPushButton:hover {
                background-color: rgba(0, 125, 170, 235);
                border: 1px solid rgba(255, 47, 167, 230);
            }

            QPushButton:disabled {
                background-color: rgba(30, 45, 55, 180);
                color: rgba(220, 220, 220, 120);
                border: 1px solid rgba(120, 120, 120, 90);
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QFrame()
        header.setObjectName("HeaderBox")

        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(4)

        self.title = QLabel("JARVIS · NEMOTRON AI")
        self.title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 900;
                letter-spacing: 5px;
                color: rgb(0, 234, 255);
            }
        """)
        header_layout.addWidget(self.title)

        self.status = QLabel("Estado: listo · HABLAR dicta texto · ENVIAR consulta Nemotron")
        self.status.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: rgba(230, 255, 255, 200);
            }
        """)
        header_layout.addWidget(self.status)

        root.addWidget(header)

        self.prompt = QLineEdit()
        self.prompt.setPlaceholderText("Escribe o dicta tu pregunta. Presiona ENVIAR para consultar...")
        root.addWidget(self.prompt)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.btn_send = QPushButton("ENVIAR")
        self.btn_listen = QPushButton("HABLAR")
        self.btn_repeat = QPushButton("REPETIR VOZ")
        self.btn_clear = QPushButton("LIMPIAR")

        row.addWidget(self.btn_send)
        row.addWidget(self.btn_listen)
        row.addWidget(self.btn_repeat)
        row.addWidget(self.btn_clear)

        root.addLayout(row)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setText(
            "JARVIS listo.\n\n"
            "Modo recomendado:\n"
            "1. Presiona HABLAR para dictar.\n"
            "2. Revisa o corrige el texto detectado.\n"
            "3. Presiona ENVIAR para consultar Nemotron.\n\n"
            "Nota: si la voz se detecta mal, corrige el texto antes de enviar.\n"
        )
        root.addWidget(self.chat, 1)

        self.response_ready.connect(self.finish_response)
        self.response_error.connect(self.show_error)
        self.voice_ready.connect(self.finish_voice)
        self.voice_error.connect(self.show_voice_error)

        self.btn_send.clicked.connect(self.ask_text)
        self.btn_listen.clicked.connect(self.listen_in_app)
        self.btn_repeat.clicked.connect(lambda: self.speak_text(self.last_answer))
        self.btn_clear.clicked.connect(self.clear_all)
        self.prompt.returnPressed.connect(self.ask_text)

    def clear_all(self):
        self.prompt.clear()
        self.chat.clear()
        self.last_answer = ""
        self.status.setText("Estado: limpio · listo para nuevo comando")
        self.chat.setText("JARVIS listo.\n")

    def append_chat(self, text: str):
        self.chat.append(text)
        bar = self.chat.verticalScrollBar()
        bar.setValue(bar.maximum())

    def finish_response(self, response: str):
        self.is_asking = False
        self.btn_send.setEnabled(True)

        response = (response or "").strip()
        if not response:
            response = "No recibí una respuesta textual de Nemotron."

        self.last_answer = response
        self.append_chat("\nJARVIS:\n" + response + "\n")
        self.status.setText("Estado: respuesta recibida.")

        try:
            self.parent_window._log("[NEMOTRON] Respuesta recibida dentro de la mini interfaz.")
        except Exception:
            pass

    def show_error(self, message: str):
        self.is_asking = False
        self.btn_send.setEnabled(True)
        self.append_chat("\n[ERROR]\n" + str(message) + "\n")
        self.status.setText("Estado: error.")

    def finish_voice(self, detected_text: str):
        self.is_listening = False
        self.btn_listen.setEnabled(True)

        detected_text = (detected_text or "").strip()

        if not detected_text:
            self.status.setText("Estado: no se detectó voz clara.")
            self.append_chat("\n[MIC] No se detectó texto claro.")
            return

        self.prompt.setText(detected_text)
        self.prompt.setFocus()
        self.prompt.selectAll()

        self.append_chat("\nTÚ / VOZ DETECTADA:\n" + detected_text)
        self.status.setText("Estado: voz detectada. Corrige si es necesario y presiona ENVIAR.")

    def show_voice_error(self, message: str):
        self.is_listening = False
        self.btn_listen.setEnabled(True)
        self.status.setText("Estado: error de micrófono.")
        self.append_chat("\n[MIC ERROR]\n" + str(message) + "\n")

    def ask_text(self):
        if self.is_asking:
            return

        text = self.prompt.text().strip()

        if not text:
            text = getattr(self.parent_window, "current_text", "").strip()

        if not text:
            self.status.setText("Estado: escribe o dicta algo primero.")
            self.append_chat("\n[AVISO] No hay texto para enviar.")
            return

        self.is_asking = True
        self.btn_send.setEnabled(False)

        self.status.setText("Estado: consultando Nemotron...")
        self.append_chat("\nTÚ:\n" + text + "\n\nJARVIS: pensando...")

        self.prompt.clear()

        def worker():
            try:
                response = self.parent_window.ollama.ask(text)
                self.response_ready.emit(response)
            except Exception as exc:
                self.response_error.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def speak_text(self, text: str):
        text = (text or "").strip()

        if not text:
            self.status.setText("Estado: no hay respuesta para repetir.")
            return

        def worker():
            try:
                import pyttsx3

                engine = pyttsx3.init()
                engine.setProperty("rate", 170)
                engine.setProperty("volume", 0.95)
                engine.say(text[:1000])
                engine.runAndWait()

            except Exception as exc:
                self.response_error.emit(f"VOICE ERROR: {exc}")

        self.status.setText("Estado: reproduciendo voz...")
        threading.Thread(target=worker, daemon=True).start()

    def listen_in_app(self):
        if self.is_listening:
            return

        self.is_listening = True
        self.btn_listen.setEnabled(False)

        self.status.setText("Estado: escuchando... habla claro y cerca del micrófono.")
        self.append_chat("\n[MIC] Escuchando...")

        def worker():
            try:
                import speech_recognition as sr

                recognizer = sr.Recognizer()
                recognizer.dynamic_energy_threshold = True
                recognizer.pause_threshold = 0.8
                recognizer.phrase_threshold = 0.25
                recognizer.non_speaking_duration = 0.4

                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.8)
                    audio = recognizer.listen(source, timeout=7, phrase_time_limit=10)

                try:
                    detected_text = recognizer.recognize_google(audio, language="es-CO")
                except Exception:
                    detected_text = recognizer.recognize_google(audio, language="es-ES")

                self.voice_ready.emit(detected_text)

            except Exception as exc:
                self.voice_error.emit(
                    "No pude reconocer la voz.\n"
                    "Recomendaciones:\n"
                    "1. Habla cerca del micrófono.\n"
                    "2. Espera medio segundo después de presionar HABLAR.\n"
                    "3. Evita ruido de fondo.\n"
                    "4. Si falla, escribe manualmente.\n"
                    f"Detalle técnico: {exc}"
                )

        threading.Thread(target=worker, daemon=True).start()
