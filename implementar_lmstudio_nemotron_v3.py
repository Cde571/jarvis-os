from pathlib import Path
import re
from datetime import datetime

root = Path(".")
client_file = root / "src" / "jarvis_air" / "core" / "ollama_client.py"
config_file = root / "src" / "jarvis_air" / "core" / "config.py"
ui_file = root / "src" / "jarvis_air" / "ui" / "hologram_window.py"
voice_file = root / "src" / "jarvis_air" / "voice_bridge.py"

if not client_file.exists():
    raise RuntimeError("No encontré src/jarvis_air/core/ollama_client.py")

if not ui_file.exists():
    raise RuntimeError("No encontré src/jarvis_air/ui/hologram_window.py")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = root / f"backup_lmstudio_nemotron_{stamp}"
backup_dir.mkdir(parents=True, exist_ok=True)

for f in [client_file, config_file, ui_file, voice_file]:
    if f.exists():
        dest = backup_dir / f
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

print(f"Backup creado en: {backup_dir}")


# ============================================================
# 1. Reemplazar cliente IA antiguo por LM Studio/Nemotron
# ============================================================

client_file.write_text(r'''from __future__ import annotations

import requests


class OllamaClient:
    """
    Cliente IA principal de JARVIS.

    IMPORTANTE:
    Se conserva el nombre OllamaClient solo para no romper imports existentes.
    Internamente ya NO usa Ollama como IA principal.
    Ahora usa LM Studio + Nemotron 3 Nano 4B.
    """

    def __init__(self):
        self.base_url = "http://127.0.0.1:1234"
        self.model = "nvidia/nemotron-3-nano-4b"
        self.timeout = 90

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            return response.status_code < 500
        except Exception:
            return False

    def ask(self, prompt: str) -> str:
        prompt = (prompt or "").strip()

        if not prompt:
            prompt = "Hola Jarvis, preséntate brevemente y dime qué puedes hacer."

        url = f"{self.base_url}/v1/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres JARVIS, un asistente local en español. "
                        "Responde de forma natural, clara, breve y útil. "
                        "Tu personalidad es tecnológica, precisa, elegante y directa. "
                        "No menciones que eres un modelo a menos que te lo pregunten."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.65,
            "max_tokens": 450,
            "stream": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        except Exception as exc:
            return (
                "LM Studio / Nemotron no respondió correctamente.\n\n"
                "Verifica:\n"
                "1. LM Studio debe estar en Status: Running.\n"
                "2. Debe decir Reachable at: http://127.0.0.1:1234.\n"
                "3. El modelo nvidia/nemotron-3-nano-4b debe estar cargado.\n"
                "4. No abras /v1/chat/completions en el navegador; ese endpoint usa POST.\n\n"
                f"Detalle técnico: {exc}"
            )
''', encoding="utf-8")

print("Cliente IA reemplazado por LM Studio/Nemotron.")


# ============================================================
# 2. Config opcional: marcar LM Studio como backend
# ============================================================

if config_file.exists():
    cfg = config_file.read_text(encoding="utf-8", errors="replace")

    if "lmstudio_url" not in cfg:
        cfg += '''

# IA local principal
lmstudio_url = "http://127.0.0.1:1234/v1/chat/completions"
lmstudio_model = "nvidia/nemotron-3-nano-4b"
ai_backend = "lmstudio"
'''

    cfg = cfg.replace("qwen2.5:3b", "nvidia/nemotron-3-nano-4b")
    cfg = cfg.replace("llama3.2:3b", "nvidia/nemotron-3-nano-4b")
    cfg = cfg.replace("http://localhost:11434/api/generate", "http://127.0.0.1:1234/v1/chat/completions")
    cfg = cfg.replace("http://127.0.0.1:11434/api/generate", "http://127.0.0.1:1234/v1/chat/completions")

    config_file.write_text(cfg, encoding="utf-8")
    print("config.py actualizado.")


# ============================================================
# 3. Actualizar interfaz: quitar textos de Ollama y usar Nemotron
# ============================================================

ui = ui_file.read_text(encoding="utf-8", errors="replace")

# Cambiar textos visibles
ui = ui.replace("Ollama", "LM Studio")
ui = ui.replace("OLLAMA", "LM STUDIO")
ui = ui.replace("qwen2.5:3b", "nvidia/nemotron-3-nano-4b")
ui = ui.replace("llama3.2:3b", "nvidia/nemotron-3-nano-4b")
ui = ui.replace("[IA] Consultando Ollama...", "[IA] Consultando LM Studio / Nemotron...")
ui = ui.replace("Ollama optional", "LM Studio Nemotron")
ui = ui.replace("AI CHAT", "NEMOTRON")

# Reemplazar función _ask_ollama, manteniendo nombre para no romper botones
ask_method = '''    def _ask_ollama(self):
        prompt = self.current_text or "Hola Jarvis, responde brevemente qué puedes hacer con esta interfaz holográfica."
        self._log("[IA] Consultando LM Studio / Nemotron...")

        try:
            answer = self.ollama.ask(prompt)
            self.log.append(answer[:2500])
        except Exception as exc:
            self._log(f"[IA ERROR] {exc}")

'''

ui = re.sub(
    r"    def _ask_ollama\(self\):.*?(?=\n    # ── Gestos|\n    def |\Z)",
    ask_method,
    ui,
    flags=re.DOTALL
)

# Quick Launch: asegurar botón Nemotron y quitar nombre antiguo si queda
ui = ui.replace('("NEMOTRON", self._ask_ollama)', '("NEMOTRON", self._ask_ollama)')
ui = ui.replace('("AI CHAT", self._ask_ollama)', '("NEMOTRON", self._ask_ollama)')

# Paneles estáticos: hacerlos más claros y reales, sin tocar diseño
ui = ui.replace(
    '''self.ai_panel = self._make_panel("AI CAPABILITIES", [
            "NATURAL LANGUAGE", "VISUAL PROCESSING",
            "CONTEXT AWARENESS", "AIR INPUT READY",
        ])''',
    '''self.ai_panel = self._make_panel("AI / NEMOTRON", [
            "LM STUDIO       READY",
            "MODEL           NEMOTRON 4B",
            "ENDPOINT        127.0.0.1:1234",
            "AIR INPUT       READY",
        ])'''
)

ui = ui.replace(
    '''modules = self._make_panel("ACTIVE MODULES", [
            "HOLOGRAPHIC UI     ON",
            "DUAL HAND TRACKER  ON",
            "AIR KEYBOARD       ON",
            "DWELL SELECTION    ON",
            "SCROLL GESTURE     ON",
            "SECURITY PROTOCOL  ON",
        ])''',
    '''modules = self._make_panel("MODULE STATUS", [
            "NEMOTRON          READY",
            "VOICE CONTROL     READY",
            "OCR               READY",
            "PC ACTIONS        READY",
            "PINCH CLICK       READY",
            "SCROLL            READY",
        ])'''
)

ui = ui.replace(
    '''voice = self._make_panel("VOICE COMMAND", [
            "Listening...  STANDBY",
            "Waveform module ready",
            "LM Studio optional",
        ])''',
    '''voice = self._make_panel("VOICE / AI", [
            "NEMOTRON       LOCAL",
            "LM STUDIO      RUNNING",
            "VOICE READY    OPTIONAL",
        ])'''
)

ui_file.write_text(ui, encoding="utf-8")
print("hologram_window.py actualizado para Nemotron.")


# ============================================================
# 4. Crear voice_bridge.py usando LM Studio, eliminando IA antigua
# ============================================================

voice_file.write_text(r'''from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests


HOST = "127.0.0.1"
PORT = 8765

LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "nvidia/nemotron-3-nano-4b"


HTML = r"""
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>JARVIS Voice AI - LM Studio Nemotron</title>
<style>
    body {
        margin: 0;
        min-height: 100vh;
        background:
            radial-gradient(circle at 20% 20%, rgba(0,234,255,.22), transparent 30%),
            radial-gradient(circle at 80% 80%, rgba(255,47,167,.18), transparent 35%),
            #030914;
        color: #eaffff;
        font-family: Segoe UI, Arial, sans-serif;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .panel {
        width: min(860px, 92vw);
        border: 1px solid rgba(0,234,255,.55);
        background: rgba(0, 20, 40, .72);
        box-shadow: 0 0 35px rgba(0,234,255,.18);
        padding: 28px;
    }

    h1 {
        margin: 0 0 8px;
        letter-spacing: 4px;
        font-size: 28px;
    }

    .sub {
        color: rgba(234,255,255,.75);
        margin-bottom: 22px;
    }

    button {
        background: rgba(0,234,255,.16);
        border: 1px solid rgba(0,234,255,.65);
        color: #eaffff;
        padding: 12px 18px;
        font-weight: 800;
        letter-spacing: 1px;
        cursor: pointer;
        margin-right: 10px;
    }

    button:hover {
        border-color: rgba(255,47,167,.9);
        background: rgba(255,47,167,.18);
    }

    textarea {
        width: 100%;
        height: 110px;
        margin-top: 16px;
        background: rgba(0,10,20,.75);
        color: #eaffff;
        border: 1px solid rgba(0,234,255,.35);
        padding: 12px;
        resize: vertical;
    }

    .answer {
        margin-top: 18px;
        padding: 16px;
        min-height: 120px;
        background: rgba(0,10,20,.55);
        border: 1px solid rgba(0,234,255,.30);
        white-space: pre-wrap;
        line-height: 1.45;
    }

    .status {
        margin-top: 12px;
        color: #00eaff;
        font-size: 14px;
    }
</style>
</head>
<body>
<div class="panel">
    <h1>JARVIS VOICE AI</h1>
    <div class="sub">Backend local: LM Studio · Modelo: Nemotron 3 Nano 4B · Endpoint: 127.0.0.1:1234</div>

    <button onclick="listen()">HABLAR CON JARVIS</button>
    <button onclick="sendText()">ENVIAR TEXTO</button>
    <button onclick="speak(lastAnswer)">REPETIR VOZ</button>

    <textarea id="prompt" placeholder="Escribe o dicta tu comando..."></textarea>

    <div class="status" id="status">Listo.</div>
    <div class="answer" id="answer">Respuesta de JARVIS...</div>
</div>

<script>
let lastAnswer = "";

function setStatus(text) {
    document.getElementById("status").textContent = text;
}

async function sendText() {
    const prompt = document.getElementById("prompt").value.trim();

    if (!prompt) {
        setStatus("Escribe o dicta algo primero.");
        return;
    }

    setStatus("Consultando Nemotron en LM Studio...");

    const res = await fetch("/ask", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({prompt})
    });

    const data = await res.json();
    lastAnswer = data.answer || "Sin respuesta.";

    document.getElementById("answer").textContent = lastAnswer;
    setStatus("Respuesta recibida.");
    speak(lastAnswer);
}

function speak(text) {
    if (!text) return;

    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "es-ES";
    utter.rate = 1.0;
    utter.pitch = 1.0;
    speechSynthesis.cancel();
    speechSynthesis.speak(utter);
}

function listen() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        setStatus("Este navegador no soporta reconocimiento de voz. Usa Chrome o Edge.");
        return;
    }

    const rec = new SpeechRecognition();
    rec.lang = "es-ES";
    rec.interimResults = false;
    rec.continuous = false;

    rec.onstart = () => setStatus("Escuchando...");
    rec.onerror = (e) => setStatus("Error de micrófono: " + e.error);

    rec.onresult = (event) => {
        const text = event.results[0][0].transcript;
        document.getElementById("prompt").value = text;
        setStatus("Texto detectado: " + text);
        sendText();
    };

    rec.start();
}
</script>
</body>
</html>
"""


def ask_lmstudio(prompt: str) -> str:
    prompt = (prompt or "").strip()

    if not prompt:
        prompt = "Hola Jarvis, preséntate brevemente."

    payload = {
        "model": LMSTUDIO_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres JARVIS, un asistente local en español. "
                    "Responde de forma natural, clara, breve y útil. "
                    "Tu personalidad es tecnológica, precisa, elegante y directa."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.65,
        "max_tokens": 450,
        "stream": False,
    }

    try:
        response = requests.post(LMSTUDIO_URL, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return (
            "No pude conectar con LM Studio / Nemotron. "
            "Verifica que LM Studio esté en Status: Running y que el puerto sea 1234. "
            f"Detalle: {exc}"
        )


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, content_type: str = "text/html; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(HTML.encode("utf-8"))

    def do_POST(self):
        if self.path != "/ask":
            self._send(json.dumps({"error": "endpoint no válido"}).encode("utf-8"), "application/json")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")

        try:
            data = json.loads(raw)
        except Exception:
            data = {}

        prompt = data.get("prompt", "")
        answer = ask_lmstudio(prompt)

        self._send(json.dumps({"answer": answer}, ensure_ascii=False).encode("utf-8"), "application/json")

    def log_message(self, fmt, *args):
        return


class VoiceServer:
    def __init__(self):
        self.server = ThreadingHTTPServer((HOST, PORT), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        try:
            self.server.shutdown()
        except Exception:
            pass


_SERVER = None


def start_server(open_browser: bool = True):
    global _SERVER

    if _SERVER is None:
        _SERVER = VoiceServer()
        _SERVER.start()

    if open_browser:
        webbrowser.open(f"http://{HOST}:{PORT}")

    return _SERVER


if __name__ == "__main__":
    start_server(open_browser=True)
    print(f"JARVIS Voice AI activo en http://{HOST}:{PORT}")
    input("Presiona Enter para cerrar... ")
''', encoding="utf-8")

print("voice_bridge.py creado con LM Studio/Nemotron.")
print("IMPLEMENTACIÓN COMPLETA")
