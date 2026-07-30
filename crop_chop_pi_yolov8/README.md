# Crop Chop Pi YOLOv8

Raspberry Pi 4B-side YOLOv8 inference setup for the Crop Chop XIAO ESP32S3 Sense camera stream.

This does not modify or test motors, servos, ESCs or cutting hardware.

## Quick Start On Pi

```bash
cd crop_chop_pi_yolov8
bash scripts/install_yolov8_pi.sh
.venv/bin/python scripts/yolov8_xiao_stream.py --source http://192.168.4.1/stream --model yolov8n.pt --imgsz 320
```

Read `docs/pi_yolov8_setup.md` before wiring anything to the Pi GPIO header.
