from dataclasses import dataclass

@dataclass
class Settings:
    camera_index: int = 0
    mirror_camera: bool = True
    enable_pc_control: bool = False   # Activar desde la UI por seguridad
    enable_ocr: bool = False
    pinch_cooldown_frames: int = 14   # Aumentado para menos clicks accidentales
    gesture_stable_frames: int = 3    # Buffer de estabilidad del gesto
    pointer_smoothing: float = 0.30   # Más suavizado (era 0.35)
    dwell_frames: int = 20            # Frames de hover para dwell-click
    scroll_threshold_px: int = 8      # Mínimo movimiento en Y para scroll
    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "qwen2.5:3b"

SETTINGS = Settings()
