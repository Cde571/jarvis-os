Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
python -m pip uninstall -y mediapipe numpy opencv-python opencv-contrib-python protobuf
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "import mediapipe as mp; print('MediaPipe:', mp.__version__); print('Tiene solutions:', hasattr(mp, 'solutions'))"
