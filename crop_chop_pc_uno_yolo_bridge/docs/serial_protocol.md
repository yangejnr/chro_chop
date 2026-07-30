# Crop Chop PC-to-UNO Serial Protocol

## Scope

This protocol is for communication between the PC-side YOLO process and an Arduino UNO over USB serial. It does not drive servos, ESCs, motors or cutting hardware.

## Serial Settings

- Baud: `115200`
- Line ending: newline `\n`
- Encoding: ASCII text

## Commands From PC To UNO

```text
HELLO
PING
DETECTION <label> <confidence> <center_x> <center_y> <width> <height>
NO_DETECTION
SET_THRESHOLD <confidence>
ARM_LOGIC
DISARM_LOGIC
STATUS
SERVO_SCAN <max_id>
SERVO_PING <id>
SERVO_STATUS <id>
SERVO_TORQUE <id> <0|1>
SERVO_MOVE_SAFE <id> <position> <speed>
```

Field meanings:

- `label`: object class name with spaces replaced by `_`
- `confidence`: `0.0` to `1.0`
- `center_x`, `center_y`, `width`, `height`: normalized image coordinates from `0.0` to `1.0`

## Responses From UNO To PC

```text
UNO_READY firmware=0.3.0
PONG uptime_ms=<integer>
ACK command=<name>
STATUS armed=<0|1> xiao_d1=<0|1> xiao_d2=<0|1> detections=<integer> last_label=<label> last_confidence=<float> decision=<SAFE|DANGER>
TEST_STATUS uptime_ms=<integer> armed=<0|1> xiao_d1=<0|1> xiao_d2=<0|1> green=<0|1> yellow=<0|1> red=<0|1> detections=<integer> confidence=<float> threshold=<float> decision=<SAFE|DANGER>
SERVO_SCAN_BEGIN max_id=<integer>
SERVO_FOUND id=<integer>
SERVO_SCAN_END
SERVO_PING id=<integer> ok=<0|1>
SERVO_STATUS id=<integer> ok=<0|1> position=<integer>
SERVO_TORQUE id=<integer> enable=<0|1> ok=<0|1>
SERVO_MOVE_SAFE id=<integer> position=<integer> speed=<integer> ok=<0|1>
ERROR code=<name>
```

## Decision Rule

The initial UNO logic stores the latest detection and classifies it as:

- `DANGER` when logic is armed and confidence is greater than or equal to the configured threshold.
- `SAFE` otherwise.

This is intentionally conservative. Later actuator code should be added only after separate bench tests.

## Current UNO Wiring

| Signal | UNO pin | Direction | Behaviour |
| --- | ---: | --- | --- |
| XIAO `D1` | `9` | Input to UNO | Monitored and reported as `xiao_d1` |
| XIAO `D2` | `8` | Input to UNO | Monitored and reported as `xiao_d2` |
| Green LED | `7` | Output from UNO | ON when decision is `SAFE` |
| Yellow LED | `6` | Output from UNO | ON when decision is `DANGER` |
| Red LED | `5` | Output from UNO | Steady ON for power/status, blinking during `DANGER` |

Use current-limiting resistors for all LEDs. Connect XIAO GND, UNO GND and the LED ground rail together.

## Servo Bus Wiring

| Servo driver signal | UNO pin | Direction |
| --- | ---: | --- |
| Driver `RX` with jumper `A` | `D2` | UNO software serial RX |
| Driver `TX` with jumper `A` | `D3` | UNO software serial TX |
| Driver `GND` | `GND` | Common reference |

For UNO control, the bus servo adapter jumper must be in `A` / UART mode. Jumper `B` is USB-control mode and should be used only when the adapter is connected directly to the PC by USB.

`SERVO_MOVE_SAFE` is rejected unless logic is armed. Accepted positions are restricted to `1800` to `2300`, and accepted speeds are restricted to `1` to `300`.
