from __future__ import annotations

try:
    import mss
    from PIL import Image
    import pytesseract
except Exception:
    mss = None
    Image = None
    pytesseract = None

class ScreenReader:
    def read_screen_text(self) -> str:
        if mss is None or Image is None or pytesseract is None:
            return "OCR no disponible. Instala mss, pillow, pytesseract y Tesseract OCR en el sistema."
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            return pytesseract.image_to_string(img, lang="eng+spa").strip()
