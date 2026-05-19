from __future__ import annotations

import os
import platform
import subprocess
import webbrowser
from dataclasses import dataclass
from typing import Callable, Dict

try:
    import pyautogui
except Exception:
    pyautogui = None

@dataclass
class ActionResult:
    ok: bool
    message: str

class PCActions:
    def __init__(self):
        self.system = platform.system().lower()
        self.safe_mode = True
        self.apps: Dict[str, Callable[[], ActionResult]] = {
            "chrome": lambda: self.open_app("chrome"),
            "edge": lambda: self.open_app("msedge"),
            "notepad": lambda: self.open_app("notepad"),
            "calculator": lambda: self.open_app("calc"),
            "explorer": lambda: self.open_app("explorer"),
            "vscode": lambda: self.open_app("code"),
        }

    def set_safe_mode(self, enabled: bool):
        self.safe_mode = enabled

    def open_app(self, command: str) -> ActionResult:
        try:
            if self.system == "windows":
                subprocess.Popen(command, shell=True)
            elif self.system == "darwin":
                subprocess.Popen(["open", "-a", command])
            else:
                subprocess.Popen(command.split())
            return ActionResult(True, f"Aplicación solicitada: {command}")
        except Exception as exc:
            return ActionResult(False, f"No pude abrir {command}: {exc}")

    def search_web(self, query: str) -> ActionResult:
        if not query.strip():
            return ActionResult(False, "La búsqueda está vacía.")
        webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
        return ActionResult(True, f"Buscando: {query}")

    def click(self) -> ActionResult:
        if pyautogui is None:
            return ActionResult(False, "pyautogui no está instalado.")
        pyautogui.click()
        return ActionResult(True, "Clic ejecutado")

    def click_at(self, x: int, y: int):
        if pyautogui is None:
            return ActionResult(False, "Pinza detectada — sin botón bajo el puntero")
        try:
            pyautogui.click(x, y)
            return ActionResult(True, f"Click ejecutado en ({x}, {y})")
        except Exception as exc:
            return ActionResult(False, f"No pude hacer click externo: {exc}")


    def move_cursor(self, x: int, y: int) -> ActionResult:
        if pyautogui is None:
            return ActionResult(False, "pyautogui no está instalado.")
        pyautogui.moveTo(x, y)
        return ActionResult(True, "Cursor movido")

    def scroll(self, amount: int) -> ActionResult:
        if pyautogui is None:
            return ActionResult(False, "pyautogui no está instalado.")
        pyautogui.scroll(amount)
        return ActionResult(True, f"Scroll {amount}")

    def hotkey(self, *keys: str) -> ActionResult:
        if pyautogui is None:
            return ActionResult(False, "pyautogui no está instalado.")
        pyautogui.hotkey(*keys)
        return ActionResult(True, "+".join(keys))
