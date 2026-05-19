Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
if (!(Test-Path ".venv")) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m src.jarvis_air.app
