# Three-Servo Bench Test Procedure

## Purpose

Test the servo bus alongside the existing camera/YOLO-to-UNO safety logic without enabling any cutting mechanism.

This procedure starts with non-motion checks. Motion is allowed only after the UNO logic is armed and only through the bounded `SERVO_MOVE_SAFE` command.

## Current Servo Arrangement

| Servo role | Intended motion |
| --- | --- |
| Base servo | Left/right base rotation |
| Hip servo | Vertical movement from right to left |
| Upper vertical servo | Vertical movement left to right, mechanically 90 degrees opposite the hip servo |

Record the actual servo ID for each role after `SERVO_SCAN`.

## Assumed Serial Wiring

The firmware uses SoftwareSerial for the servo driver:

| Servo driver signal | UNO pin |
| --- | ---: |
| Driver `RX` | UNO `D2` / software RX |
| Driver `TX` | UNO `D3` / software TX |
| Driver `GND` | UNO `GND` |

For UNO UART control, the bus servo adapter jumper must be in `A` mode. The adapter documentation labels the UART pins from the adapter side, so use `RX` to UNO software RX and `TX` to UNO software TX for this board.

If the jumper is in `B` mode, the adapter is configured for USB control. In that mode, the UNO UART pins will not control the servos; connect the adapter directly to the PC by USB instead.

## Power Safety

- Do not power servos from the UNO `5V` pin.
- Use the servo driver/external supply sized for the servos.
- Connect external supply ground, servo driver ground, UNO ground and XIAO ground together.
- Keep the cutting mechanism disconnected during this bench test.
- Keep the robot mechanically supported so a servo movement cannot strike the bench or operator.

## Important UNO Limitation

Many STS3215/Feetech bus servos use `1000000` baud by default. Arduino UNO `SoftwareSerial` may be unreliable at that baud rate.

If `SERVO_SCAN` finds no servos:

- confirm the adapter jumper is in `A` mode for UNO UART control,
- confirm adapter `RX` goes to UNO `D2` and adapter `TX` goes to UNO `D3`,
- confirm common ground,
- confirm servo power,
- test the common servo bus baud rates with the PC diagnostic script,
- consider using a board with an extra hardware UART, such as Arduino Mega, for reliable servo bus communication.

## Upload Firmware

```bash
cd /home/henry/crop-chop/crop_chop_pc_uno_yolo_bridge
env PLATFORMIO_CORE_DIR=/home/henry/crop-chop/crop_chop_xiao_camera_test/.pio_core ../crop_chop_xiao_camera_test/.venv/bin/pio run --target upload --upload-port /dev/ttyUSB0
```

## Open Serial Monitor

```bash
env PLATFORMIO_CORE_DIR=/home/henry/crop-chop/crop_chop_xiao_camera_test/.pio_core ../crop_chop_xiao_camera_test/.venv/bin/pio device monitor --port /dev/ttyUSB0 --baud 115200
```

Expected startup includes:

```text
UNO_READY firmware=0.5.0
servo_bus_rx_pin=2
servo_bus_tx_pin=3
servo_bus_baud=1000000
servo_protocol=Feetech_STS_SMS_serial_bus_assumed
```

## Non-Motion Tests

Type commands in Serial Monitor with newline enabled.

Select the servo bus baud rate:

```text
SERVO_BAUD 1000000
```

Expected response:

```text
SERVO_BAUD baud=1000000 ok=1
```

Scan common IDs:

```text
SERVO_SCAN 20
```

Expected response:

```text
SERVO_SCAN_BEGIN max_id=20
SERVO_FOUND id=1
SERVO_FOUND id=2
SERVO_FOUND id=3
SERVO_SCAN_END
```

Ping a known ID:

```text
SERVO_PING 1
```

Expected response:

```text
SERVO_PING id=1 ok=1
```

Read a present position:

```text
SERVO_STATUS 1
```

Expected response:

```text
SERVO_STATUS id=1 ok=1 position=<integer>
```

## Torque Test

Enable torque only after scan/status works:

```text
SERVO_TORQUE 1 1
```

Disable torque:

```text
SERVO_TORQUE 1 0
```

## Limited Motion Test

Motion requires the UNO logic to be armed:

```text
ARM_LOGIC
```

The firmware only accepts positions from `1800` to `2300` and speeds from `1` to `300`.

Small safe movement example:

```text
SERVO_MOVE_SAFE 1 2048 100
```

Try one servo at a time. Do not run simultaneous movement commands during first bench tests.

Return to disarmed:

```text
DISARM_LOGIC
```

## Dissertation Evidence To Record

For each servo, record:

- servo role,
- servo ID,
- command sent,
- serial response,
- whether the servo moved,
- whether the movement direction matched the mechanical expectation,
- any abnormal noise, heat, twitching or communication failure.

Do not claim servo control success unless the serial response and physical movement were both observed.

## PC Diagnostic Script

To run the same checks from the PC without YOLO:

```bash
cd /home/henry/crop-chop/crop_chop_pc_uno_yolo_bridge
MPLCONFIGDIR=/tmp .venv/bin/python pc_tools/servo_bus_diagnostic.py --port /dev/ttyUSB0 --servo-ids 1,2,3 --position-a 1900 --position-b 2200 --speed 100 --cycles 1
```

The script tests `1000000`, `115200`, `500000`, `250000` and `57600` servo-bus baud rates before any movement command. If no servo acknowledges, it skips torque and movement commands for safety.

If the output shows `No servo acknowledgement found at tested baud rates`, focus on adapter jumper mode, RX/TX labeling, common ground, servo power and servo IDs before returning to the camera/YOLO sequence.
