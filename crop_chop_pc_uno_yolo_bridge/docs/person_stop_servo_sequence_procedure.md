# Person-Stop Sequential Servo Test Procedure

## Purpose

Run the three servos sequentially while the PC watches the XIAO ESP32S3 Sense camera stream with YOLOv8. If YOLO detects a `person`, the PC stops the sequence, turns servo torque off for the configured servo IDs, disarms the UNO logic, and records the event.

This procedure is for bench testing only. It does not operate the brushless motor, ESC, nylon cutting head or cutting mechanism.

## Control Architecture

```text
XIAO camera stream -> PC YOLOv8 person detection -> USB serial -> UNO -> servo bus driver -> three servos
```

The PC controls sequencing because it has the live image-detection context. The UNO receives explicit serial commands and enforces bounded movement through `SERVO_MOVE_SAFE`.

## Safety Preconditions

- Cutting mechanism disconnected.
- Brushless motor and ESC disconnected.
- Servo mechanism mechanically supported.
- Servo power supplied by the servo driver/external supply, not the UNO.
- Common ground between XIAO, UNO, servo driver and servo supply.
- Servo IDs confirmed with `SERVO_SCAN` before movement.
- Visual YOLO test confirms that the XIAO stream is visible.

## Servo Driver Wiring

| Bus servo adapter | Arduino UNO |
| --- | ---: |
| `TX` | `D2` software RX |
| `RX` | `D3` software TX |
| `GND` | `GND` |

Serial is crossed: adapter `TX` goes to UNO receive, and adapter `RX` goes to UNO transmit.

## Step 1: Confirm XIAO Camera View

Connect the PC Wi-Fi to:

```text
CropChop-Camera-Test
```

Run:

```bash
cd /home/henry/crop-chop/crop_chop_pc_uno_yolo_bridge
MPLCONFIGDIR=/tmp .venv/bin/python pc_tools/visual_yolo_test.py --model yolov8n.pt --imgsz 320 --conf 0.25
```

Confirm that the display shows the XIAO camera stream. Press `q` to close it.

## Step 2: Confirm Servo Communication

Open the UNO serial monitor:

```bash
env PLATFORMIO_CORE_DIR=/home/henry/crop-chop/crop_chop_xiao_camera_test/.pio_core ../crop_chop_xiao_camera_test/.venv/bin/pio device monitor --port /dev/ttyUSB0 --baud 115200
```

Run:

```text
SERVO_SCAN 20
SERVO_STATUS 1
SERVO_STATUS 2
SERVO_STATUS 3
```

Do not run the sequence until all expected servos are found and status reads succeed.

## Step 3: Run Sequential Servo Test With Person Stop

Close the serial monitor so the PC bridge can use `/dev/ttyUSB0`.

Run:

```bash
MPLCONFIGDIR=/tmp .venv/bin/python pc_tools/yolo_uno_bridge.py \
  --port /dev/ttyUSB0 \
  --model yolov8n.pt \
  --imgsz 320 \
  --conf 0.25 \
  --servo-sequence \
  --servo-ids 1,2,3 \
  --servo-positions 1900,2048,2200 \
  --servo-speed 100 \
  --servo-step-interval 1.5 \
  --stop-class person \
  --log-jsonl runs/person_stop_servo_sequence.jsonl \
  --log-csv runs/person_stop_servo_sequence.csv
```

The bridge defaults to the XIAO stream:

```text
http://192.168.4.1/stream
```

## Expected Behaviour

When no person is detected:

- the PC sends sequential `SERVO_MOVE_SAFE ...` commands,
- the UNO remains armed,
- the sequence continues through the configured servo IDs and positions.

When a person is detected:

- the PC sends the current `DETECTION person ...` command,
- the PC sends `SERVO_TORQUE <id> 0` for each configured servo ID,
- the PC sends `DISARM_LOGIC`,
- the sequence stops,
- logs mark `event=stop_person_detected`.

## Data Recorded

JSONL log:

```text
runs/person_stop_servo_sequence.jsonl
```

CSV log:

```text
runs/person_stop_servo_sequence.csv
```

Each row records:

- timestamp,
- frame number,
- event type,
- command sent,
- whether stop detection occurred,
- best detected class,
- best confidence,
- latest UNO response.

## Dissertation Reporting Notes

Report the result as four separate evidence layers:

- perception: YOLO detected or did not detect `person`,
- control command: PC command sent to UNO,
- embedded response: UNO serial response,
- physical outcome: observed servo movement or stop.

Do not claim a successful person-stop event unless the log shows `event=stop_person_detected` and physical motion stopped during the test.
