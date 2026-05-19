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
    ollama_url: str = "http://127.0.0.1:1234/v1/chat/completions"
    ollama_model: str = "nvidia/nemotron-3-nano-4b"

SETTINGS = Settings()


# IA local principal
lmstudio_url = "http://127.0.0.1:1234/v1/chat/completions"
lmstudio_model = "nvidia/nemotron-3-nano-4b"
ai_backend = "lmstudio"
