#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"

echo "Crop Chop Pi YOLOv8 install"
echo "Project: ${PROJECT_DIR}"

if ! grep -qi "raspberry pi" /proc/device-tree/model 2>/dev/null; then
  echo "Warning: this does not look like a Raspberry Pi. Continuing anyway."
fi

sudo apt update
sudo apt install -y python3 python3-venv python3-pip libatlas-base-dev libopenblas-dev libjpeg-dev zlib1g-dev

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip wheel setuptools
"${VENV_DIR}/bin/python" -m pip install -r "${PROJECT_DIR}/requirements.txt"

"${VENV_DIR}/bin/python" - <<'PY'
from ultralytics import YOLO

model = YOLO("yolov8n.pt")
print("Loaded YOLOv8 model:", model.model_name if hasattr(model, "model_name") else "yolov8n.pt")
PY

echo
echo "Install complete."
echo "Activate with: source ${VENV_DIR}/bin/activate"
echo "Smoke test with: ${VENV_DIR}/bin/python ${PROJECT_DIR}/scripts/yolov8_xiao_stream.py --source http://192.168.4.1/stream --no-display --duration 10"
