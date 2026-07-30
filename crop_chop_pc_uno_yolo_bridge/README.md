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
env PLATFORMIO_CORE_DIR=/home/henry/crop-chop/crop_chop_xiao_camera_test/.pio_core ../crop_chop_xiao_camera_test/.venv/bin/pio run --target upload --upload-port /dev/ttyUSB0
```

Use `/dev/ttyACM0` instead if the UNO appears as an Arduino USB CDC device. This project passes avrdude `-V` because your UNO successfully runs the flashed firmware even though read-back verification can fail on this USB-serial path.

## Serial Monitor Test Output

Open Serial Monitor at `115200` baud after upload. On reset, the UNO prints:

```text
UNO_READY firmware=0.3.0
BEGIN_UNO_WIRING_TEST
...
END_UNO_WIRING_TEST
STATUS armed=0 xiao_d1=... xiao_d2=... decision=SAFE
```

Every second it prints a test line:

```text
TEST_STATUS uptime_ms=... armed=0 xiao_d1=... xiao_d2=... green=1 yellow=0 red=1 detections=0 confidence=0.000 threshold=0.500 decision=SAFE
```

Expected idle result:

- `decision=SAFE`
- `green=1`
- `yellow=0`
- `red=1`
- `xiao_d1` and `xiao_d2` reflect the live voltage level on UNO pins `9` and `8`

Your first successful monitor run showed `xiao_d1=1`, `xiao_d2=0`, `green=1`, `yellow=0`, `red=1` and `decision=SAFE`, which is the expected idle safe state.

You can type these commands into Serial Monitor with newline enabled:

```text
STATUS
ARM_LOGIC
DETECTION weed 0.800 0.500 0.500 0.200 0.200
NO_DETECTION
DISARM_LOGIC
```

After `ARM_LOGIC` and the example `DETECTION`, the expected result is `decision=DANGER`, yellow ON, green OFF and red blinking.

The bench-test outcome from the first successful upload and serial monitor run is recorded in:

```text
docs/uno_logic_test_outcome_2026-07-30.md
```

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

## Visual YOLO Test Before UNO

Run the visual test first so you can see the image, bounding boxes, class label, confidence and FPS before involving the UNO:

```bash
.venv/bin/python pc_tools/visual_yolo_test.py --source 0 --model yolov8n.pt --imgsz 640 --conf 0.25
```

For the XIAO camera stream:

```bash
.venv/bin/python pc_tools/visual_yolo_test.py --source http://192.168.4.1/stream --model yolov8n.pt --imgsz 320 --conf 0.25
```

Press `q` to close the display window.

If you bring your hand close to the camera and the display says `NO DETECTION`, the UNO will correctly remain `SAFE`. The default `yolov8n.pt` model is trained on COCO objects and does not have a dedicated `hand` class. It may detect a full person, but it should not be treated as a reliable hand detector.

Save visual evidence for reports:

```bash
.venv/bin/python pc_tools/visual_yolo_test.py --source 0 --duration 30 --save-jsonl runs/visual_yolo_test.jsonl --save-video runs/visual_yolo_test.mp4
```

## Run With PC Webcam

```bash
.venv/bin/python pc_tools/yolo_uno_bridge.py --port /dev/ttyACM0 --source 0 --model yolov8n.pt --arm
```

The bridge display overlays the serial command sent to the UNO and the latest UNO response. If the overlay says `NO_DETECTION`, the UNO should remain `SAFE`.

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
