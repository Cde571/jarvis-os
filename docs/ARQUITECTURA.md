# Arquitectura V3 — JARVIS Air Interface

## Objetivo

Interfaz de PC controlada por gestos con UI holográfica de alta transparencia.

## Flujo principal

```
Cámara → MediaPipe → Buffer de Estabilidad → Gesto Estable → Acción UI/PC
```

## Módulos

| Módulo | Responsabilidad |
|---|---|
| `vision/hand_tracker.py` | Landmarks, gestos con buffer de estabilidad, distancias normalizadas |
| `ui/hologram_window.py` | UI holográfica con transparencia real, dwell-select, scroll, stats en vivo |
| `control/pc_actions.py` | Apps, búsquedas web, scroll, pyautogui |
| `control/ocr_reader.py` | OCR de pantalla con Tesseract |
| `core/ollama_client.py` | Integración IA local Ollama |
| `core/config.py` | Configuración central incluyendo dwell_frames y scroll_threshold_px |

## Gestos V3

| Gesto | Acción |
|---|---|
| Mano abierta | Activar sistema |
| Puño | Pausar sistema |
| Pinza (rápida) | Click inmediato |
| Hover 20 frames | Dwell-click automático (anillo de progreso) |
| Tres dedos (mano izquierda) | Scroll vertical |
| Dos manos abiertas | Activar menú |
| Dos puños | Pausar todo |
| Dos índice+medio | Toggle teclado aéreo |

## Visual V3 (nuevo)

- **Transparencia real**: `WA_TranslucentBackground` + ventana sin marco
- **Paneles vidrio**: opacidad ~10% (QColor 0,20,40,26)
- **Scan-line animado**: barre la pantalla cada tick
- **Puntero pulsante**: anillo cyan + magenta con dwell-arc dorado
- **Stats en vivo**: CPU/RAM via psutil (actualización cada 1s)
- **Dwell ring** en botones: arco de progreso visible

## Precisión V3 (nuevo)

- Gestos con buffer de estabilidad de 3 frames (sin flicker)
- Pinch normalizado por ancho de palma (invariante de escala)
- Thumb-up robusto con referencia al wrist
- Cooldown de pinch aumentado a 14 frames
- Dwell-click configurable (default 20 frames ≈ 0.6 s)

## Ruta de evolución

- V3: transparencia real, dwell, scroll gestual, stats en vivo ← ACTUAL
- V4: menú radial flotante, control de ventanas
- V5: IA/Ollama profunda + voz
- V6: Three.js 3D + WebXR
