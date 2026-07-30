# Crop Chop PC YOLO to UNO Bridge

This project moves the YOLO model back to the PC and uses an Arduino UNO for simple logic over USB serial.

The UNO does not run YOLO. The PC runs inference, converts the best detection into a compact serial command, and the UNO records the state and returns a logic decision.

No servos, ESCs, motors or cutting hardware are controlled by this code.

## Architecture

```text
Camera or stream -> PC YOLOv8 model -> USB serial -> Arduino UNO logic
```

Possible PC video sources:

- Laptop webcam: `--source 0`
- XIAO camera stream: `--source http://192.168.4.1/stream`
- Video file: `--source path/to/video.mp4`

## UNO Firmware

Open this sketch in Arduino IDE:

```text
uno_firmware/crop_chop_uno_logic/crop_chop_uno_logic.ino
```

Select:

- Board: `Arduino Uno`
- Port: the UNO USB serial port
- Baud: `115200`

Upload the sketch. The external LEDs indicate the current logic state:

- Red LED on pin `5`: steady ON for power/status, blinking during danger.
- Yellow LED on pin `6`: ON during danger.
- Green LED on pin `7`: ON during safe state.

The XIAO signal lines are monitored on UNO pins `9` and `8`.

Or upload with PlatformIO from this directory:

```bash
env PLATFORMIO_CORE_DIR=/home/henry/crop-chop/crop_chop_xiao_camera_test/.pio_core ../crop_chop_xiao_camera_test/.venv/bin/pio run --target upload --upload-port /dev/ttyACM0
```

Use `/dev/ttyUSB0` instead if the UNO clone appears as a USB-serial adapter.

## Current Wiring

| Connection | UNO pin |
| --- | ---: |
| XIAO `D1` | `9` |
| XIAO `D2` | `8` |
| Green LED | `7` |
| Yellow LED | `6` |
| Red LED | `5` |

Use current-limiting resistors for all LEDs, typically `220` to `330` ohms. XIAO GND and UNO GND must be connected if the XIAO signal wires are connected.

## PC Setup

From this directory on the PC:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

## Run With PC Webcam

```bash
.venv/bin/python pc_tools/yolo_uno_bridge.py --port /dev/ttyACM0 --source 0 --model yolov8n.pt --arm
```

## Run With XIAO Camera Stream

First connect the PC Wi-Fi to `CropChop-Camera-Test`, then run:

```bash
.venv/bin/python pc_tools/yolo_uno_bridge.py --port /dev/ttyACM0 --source http://192.168.4.1/stream --model yolov8n.pt --imgsz 320 --arm
```

For headless/logged testing:

```bash
.venv/bin/python pc_tools/yolo_uno_bridge.py --port /dev/ttyACM0 --source http://192.168.4.1/stream --no-display --duration 30 --log-jsonl runs/pc_uno_yolo.jsonl
```

If multiple serial ports are detected and `--port` is omitted, the script asks which port belongs to the UNO.

## Safety Defaults

- UNO starts disarmed.
- PC script disarms the UNO before exit.
- UNO logic only drives the three status LEDs on pins `7`, `6` and `5`.
- Serial protocol is documented in `docs/serial_protocol.md`.
