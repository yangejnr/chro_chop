# Raspberry Pi 4B YOLOv8 Setup

## Important Wiring Note

Corrected wiring note:

- XIAO `D1` -> Raspberry Pi `GPIO24`
- XIAO `D2` -> Raspberry Pi `GPIO23`

Those are two separate Pi GPIO lines, so the corrected mapping avoids the earlier conflict. If you only need YOLO inference from the camera stream, these GPIO signal wires are still not required; use Wi-Fi from the XIAO access point instead. Keep a common ground only if you later add a deliberate wired signalling interface.

Do not connect XIAO 3.3 V logic pins to Raspberry Pi 5 V pins.

## Recommended Architecture

1. XIAO ESP32S3 Sense runs the camera firmware from `crop_chop_xiao_camera_test`.
2. XIAO creates Wi-Fi AP `CropChop-Camera-Test`.
3. Pi 4B connects to that Wi-Fi.
4. Pi reads `http://192.168.4.1/stream`.
5. Pi runs YOLOv8 inference locally.

## Install On The Pi

Copy this folder to the Pi, then run:

```bash
cd crop_chop_pi_yolov8
bash scripts/install_yolov8_pi.sh
```

The installer creates a local virtual environment in `.venv` and loads `yolov8n.pt` as a smoke test.

## Run YOLOv8 On The XIAO Stream

After the XIAO firmware is uploaded and the Pi is connected to `CropChop-Camera-Test`:

```bash
cd crop_chop_pi_yolov8
.venv/bin/python scripts/yolov8_xiao_stream.py --source http://192.168.4.1/stream --model yolov8n.pt --imgsz 320 --conf 0.25
```

For SSH/headless operation:

```bash
.venv/bin/python scripts/yolov8_xiao_stream.py --source http://192.168.4.1/stream --no-display --duration 30 --save-json runs/xiao_yolov8.jsonl
```

To save annotated video:

```bash
.venv/bin/python scripts/yolov8_xiao_stream.py --source http://192.168.4.1/stream --no-display --duration 30 --save-video runs/xiao_yolov8.mp4 --save-json runs/xiao_yolov8.jsonl
```

## Performance Guidance

- Start with `yolov8n.pt`; Pi 4B is limited for real-time PyTorch inference.
- Start with `--imgsz 320`; increase only after measuring FPS and thermals.
- Use active cooling on the Pi.
- Do not claim detection performance until FPS, latency and detection outputs are recorded from an actual run.

## Official References

- Ultralytics Raspberry Pi guide: `https://github.com/ultralytics/ultralytics/blob/main/docs/en/guides/raspberry-pi.md`
- Ultralytics Python usage: `https://docs.ultralytics.com/usage/python/`
