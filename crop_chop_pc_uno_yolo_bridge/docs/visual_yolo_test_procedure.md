# Visual YOLO Test Procedure

## Purpose

Use this procedure to verify what the PC-side YOLO model can actually see before relying on Arduino UNO `SAFE` or `DANGER` outputs.

This is important because the UNO does not inspect images. It only receives serial commands from the PC. If the PC model sends `NO_DETECTION`, the UNO should remain `SAFE`.

## Scope

This test covers:

- Live image display on the PC
- YOLO bounding-box display
- Class label and confidence display
- Optional JSONL and video evidence output
- Interpretation of why the UNO remains `SAFE`

This test does not validate motors, servos, ESCs, the cutting head, or the cutting mechanism.

## Required Setup

From `crop_chop_pc_uno_yolo_bridge`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

## Test With PC Webcam

```bash
.venv/bin/python pc_tools/visual_yolo_test.py --source 0 --model yolov8n.pt --imgsz 640 --conf 0.25
```

Expected behaviour:

- A display window opens.
- The live camera image is visible.
- If YOLO detects an object, bounding boxes, class labels and confidence values are shown.
- If YOLO detects nothing, the overlay reports `NO DETECTION`.

Press `q` to close the window.

## Test With XIAO Camera Stream

First connect the PC Wi-Fi to the XIAO access point:

```text
CropChop-Camera-Test
```

Then run:

```bash
.venv/bin/python pc_tools/visual_yolo_test.py --source http://192.168.4.1/stream --model yolov8n.pt --imgsz 320 --conf 0.25
```

Use `--imgsz 320` first for the XIAO stream because it is more conservative for live MJPEG testing.

## Save Evidence

To save a JSONL detection log and annotated video:

```bash
.venv/bin/python pc_tools/visual_yolo_test.py --source 0 --duration 30 --save-jsonl runs/visual_yolo_test.jsonl --save-video runs/visual_yolo_test.mp4
```

Evidence files:

- `runs/visual_yolo_test.jsonl`: frame-by-frame best detection data
- `runs/visual_yolo_test.mp4`: annotated visual output

## Hand Test Interpretation

The default model `yolov8n.pt` is trained on COCO classes. It does not include a dedicated `hand` class.

If a hand is placed close to the camera and the visual display reports:

```text
NO DETECTION
```

then the Arduino UNO remaining in:

```text
decision=SAFE
```

is the correct system behaviour for the current software.

To detect hands reliably, the project will need either:

- a hand-specific model,
- a custom trained crop/weed/danger-zone model,
- or a rule based on a COCO class that the current model actually detects, such as `person`, if that is appropriate for the test.

## Link To UNO Bridge

After confirming that YOLO is detecting the intended object visually, run the UNO bridge:

```bash
.venv/bin/python pc_tools/yolo_uno_bridge.py --port /dev/ttyUSB0 --source 0 --model yolov8n.pt --arm
```

The bridge display overlays:

- the annotated camera image,
- the serial command sent to the UNO,
- and the latest UNO response.

If the bridge sends `NO_DETECTION`, the UNO should remain `SAFE`. If the bridge sends a `DETECTION ...` command while armed and confidence exceeds the UNO threshold, the UNO should report `DANGER`.

## Dissertation Note

For dissertation reporting, distinguish between:

- perception result: what YOLO detected in the image,
- communication result: what command the PC sent over serial,
- logic result: what the UNO reported as `SAFE` or `DANGER`,
- physical indicator result: which LEDs were ON or blinking.

Do not report a hand-detection success unless the visual display or saved JSONL evidence shows a model detection for the hand or intended object.
