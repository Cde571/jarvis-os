from __future__ import annotations

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
