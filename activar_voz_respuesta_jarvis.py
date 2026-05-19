from pathlib import Path
import re

file = Path("src/jarvis_air/ui/ai_mini_panel.py")

if not file.exists():
    raise RuntimeError("No encontré src/jarvis_air/ui/ai_mini_panel.py")

text = file.read_text(encoding="utf-8", errors="replace")

# ============================================================
# 1. Agregar bandera para voz automática
# ============================================================

if "self.auto_voice = True" not in text:
    text = text.replace(
        'self.last_answer = ""',
        'self.last_answer = ""\n        self.auto_voice = True',
        1
    )

# ============================================================
# 2. Mejorar speak_text para que no congele la interfaz
# ============================================================

new_speak = '''    def speak_text(self, text: str):
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

                # Intentar seleccionar una voz en español si existe.
                try:
                    voices = engine.getProperty("voices")
                    for voice in voices:
                        name = (voice.name or "").lower()
                        lang = str(getattr(voice, "languages", "")).lower()

                        if "spanish" in name or "español" in name or "es-" in lang or "es_" in lang:
                            engine.setProperty("voice", voice.id)
                            break
                except Exception:
                    pass

                engine.say(text[:1000])
                engine.runAndWait()

            except Exception as exc:
                self.response_error.emit(f"VOICE ERROR: {exc}")

        self.status.setText("Estado: respondiendo por voz...")
        threading.Thread(target=worker, daemon=True).start()

'''

text = re.sub(
    r"    def speak_text\(self, text: str\):.*?(?=\n    def |\Z)",
    new_speak,
    text,
    flags=re.DOTALL
)

# ============================================================
# 3. Hacer que finish_response lea automáticamente la respuesta
# ============================================================

if "if getattr(self, \"auto_voice\", True):" not in text:
    text = text.replace(
        '''        try:
            self.parent_window._log("[NEMOTRON] Respuesta recibida dentro de la mini interfaz.")
        except Exception:
            pass
''',
        '''        try:
            self.parent_window._log("[NEMOTRON] Respuesta recibida dentro de la mini interfaz.")
        except Exception:
            pass

        # Responder automáticamente por voz.
        if getattr(self, "auto_voice", True):
            self.speak_text(response)
''',
        1
    )

file.write_text(text, encoding="utf-8")

print("PATCH OK")
print("- Voz automática activada")
print("- speak_text mejorado")
print("- Se intenta usar voz en español si Windows la tiene")
