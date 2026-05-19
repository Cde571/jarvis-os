<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/f370d55d-1b65-476f-985f-1c9ea97f7184" />



<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/05abe6bd-9d0f-4541-a5a9-0509a377322e" />




# JARVIS Air Interface V3 — Holographic UI

Interfaz holográfica de PC controlada por gestos con **transparencia real**, 
dwell-selection y scroll gestual.

## Novedades V3

- **Transparencia real**: ventana sin marco con fondo traslúcido (se ve el escritorio)
- **Scan-line animado**: efecto holográfico dinámico
- **Dwell-click**: hover 20 frames = click automático con anillo de progreso
- **Scroll gestual**: tres dedos de la mano izquierda = scroll vertical
- **Stats en vivo**: CPU y RAM actualizados cada segundo (requiere psutil)
- **Gestos más precisos**: buffer de estabilidad, pinch normalizado por palma
- **HUD mejorado**: confianza de tracking, porcentaje de dwell, estado de scroll

## Requisitos

```bash
pip install -r requirements.txt
```

> **MediaPipe**: `pip install mediapipe`  
> **Tesseract** (opcional, para OCR): https://github.com/tesseract-ocr/tesseract  
> **psutil** (recomendado): `pip install psutil`

## Ejecución

```bash
# Windows
scripts\run_windows.ps1

# Linux / macOS
bash scripts/run_linux.sh
```

## Gestos principales

| Gesto | Acción |
|---|---|
| ✋ Mano abierta | Activar sistema |
| ✊ Puño | Pausar sistema |
| 🤏 Pinza | Click inmediato |
| 👆 Hover 20 frames | Dwell-click automático |
| ☝️☝️ Tres dedos izq. | Scroll vertical |
| ✋✋ Dos manos abiertas | Activar menú |
| ✊✊ Dos puños | Pausar todo |

## Estructura

```
src/jarvis_air/
├── ui/hologram_window.py    ← UI principal (V3: transparencia + dwell + scroll)
├── vision/hand_tracker.py   ← Gestos con buffer de estabilidad
├── control/pc_actions.py    ← Acciones de PC
├── control/ocr_reader.py    ← OCR de pantalla
├── core/config.py           ← Configuración (dwell_frames, smoothing…)
└── core/ollama_client.py    ← IA local
```
