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
