# Arduino UNO Safety Logic Bench Test Outcome

## Test Title

Arduino UNO safety-logic serial output and LED state bench test

## Project

Crop Chop: The Autonomous Agri-Trimmer

## Date

2026-07-30

## Objective

Verify that the Arduino UNO safety-logic firmware can be flashed, boot successfully, report wiring and runtime state over serial, monitor XIAO input lines, and drive the status LED outputs in the idle safe condition.

This test is limited to the UNO safety-logic bench setup. It does not test YOLO inference accuracy, STS3215 servos, ESCs, brushless motors, the cutting mechanism, or any actuator control.

## Hardware Under Test

| Item | Role |
| --- | --- |
| Arduino UNO-compatible board | Safety-logic controller |
| Seeed Studio XIAO ESP32S3 Sense | Input signal source to UNO pins |
| Green LED | Safe-state indicator |
| Yellow LED | Danger-state indicator |
| Red LED | Power/status indicator and danger blink indicator |
| Host PC | Firmware build, upload, and serial monitor |

## Wiring Used

| Connection | UNO pin | Observed in firmware as |
| --- | ---: | --- |
| XIAO `D1` | `9` | `xiao_d1` |
| XIAO `D2` | `8` | `xiao_d2` |
| Green LED | `7` | `green` |
| Yellow LED | `6` | `yellow` |
| Red LED | `5` | `red` |

All LEDs require current-limiting resistors. XIAO GND and UNO GND must be connected when XIAO signal wires are connected to the UNO.

## Firmware and Toolchain

| Component | Value |
| --- | --- |
| Firmware file | `uno_firmware/crop_chop_uno_logic/crop_chop_uno_logic.ino` |
| Firmware version reported | `0.3.0` |
| PlatformIO environment | `uno_logic` |
| PlatformIO platform | `atmelavr` |
| Board target | `uno` |
| Serial baud rate | `115200` |
| Upload port used | `/dev/ttyUSB0` |

## Build Result

The firmware built successfully for the Arduino UNO target.

| Resource | Measured usage |
| --- | ---: |
| SRAM | `1034 bytes / 2048 bytes` |
| Flash | `8880 bytes / 32256 bytes` |

## Upload Result

The upload process wrote the firmware image to flash:

```text
avrdude: 8880 bytes of flash written
```

During read-back verification, avrdude reported a protocol/read-back error:

```text
avrdude: stk500_paged_load(): (a) protocol error, expect=0x10, resp=0x55
avrdude: failed to read all of flash memory, rc=-2
```

The subsequent serial monitor session confirmed that the new firmware was running and reporting firmware version `0.3.0`. Therefore, the flash write and boot were treated as successful, while the verification read-back was recorded as unreliable on this USB-serial path.

The PlatformIO project was then updated to pass avrdude `-V` for future uploads, disabling the unreliable read-back verification step while preserving the flash write operation.

## Serial Evidence

On reset, the UNO reported:

```text
UNO_READY firmware=0.3.0
BEGIN_UNO_WIRING_TEST
project=Crop Chop PC YOLO to UNO Bridge
firmware=0.3.0
baud=115200
xiao_d1_input_pin=9
xiao_d2_input_pin=8
green_safe_led_pin=7
yellow_danger_led_pin=6
red_power_danger_led_pin=5
commands=HELLO,PING,STATUS,ARM_LOGIC,DISARM_LOGIC,NO_DETECTION,SET_THRESHOLD,DETECTION
END_UNO_WIRING_TEST
```

Initial status:

```text
STATUS armed=0 xiao_d1=1 xiao_d2=0 detections=0 last_label=none last_confidence=0.000 threshold=0.500 decision=SAFE
```

Representative periodic test output:

```text
TEST_STATUS uptime_ms=1000 armed=0 xiao_d1=1 xiao_d2=0 green=1 yellow=0 red=1 detections=0 confidence=0.000 threshold=0.500 decision=SAFE
TEST_STATUS uptime_ms=30000 armed=0 xiao_d1=1 xiao_d2=0 green=1 yellow=0 red=1 detections=0 confidence=0.000 threshold=0.500 decision=SAFE
TEST_STATUS uptime_ms=71000 armed=0 xiao_d1=1 xiao_d2=0 green=1 yellow=0 red=1 detections=0 confidence=0.000 threshold=0.500 decision=SAFE
```

## Observed Results

| Test item | Expected result | Observed result | Assessment |
| --- | --- | --- | --- |
| Firmware boot report | UNO reports firmware identity | `UNO_READY firmware=0.3.0` | Pass |
| Wiring report | UNO reports configured pins | Pins `9`, `8`, `7`, `6`, `5` reported correctly | Pass |
| XIAO `D1` input read | Live logic level reported | `xiao_d1=1` | Pass |
| XIAO `D2` input read | Live logic level reported | `xiao_d2=0` | Pass |
| Idle safety decision | Disarmed logic should be safe | `decision=SAFE` | Pass |
| Green safe LED output | ON in safe state | `green=1` | Pass |
| Yellow danger LED output | OFF in safe state | `yellow=0` | Pass |
| Red power/status LED output | ON in normal safe state | `red=1` | Pass |
| Periodic serial output | Repeated status at runtime | `TEST_STATUS` every second | Pass |

## Interpretation

The bench test confirmed that the UNO safety-logic firmware is running and producing dissertation-usable evidence through serial output. In the tested idle condition, the system correctly remained disarmed and safe, with the green and red indicators on and the yellow danger indicator off.

The observed XIAO input states at the UNO were `D1=HIGH` and `D2=LOW` during the recorded test interval. These are reported as input observations only; no claim is made here about the XIAO-side firmware behaviour beyond the voltage levels seen by the UNO.

## Limitations

- The avrdude read-back verification step was unreliable, although serial output confirmed that the new firmware executed.
- This test did not validate PC YOLO model inference.
- This test did not validate serial commands from the PC YOLO bridge.
- This test did not operate any servos, ESCs, brushless motors, cutting head, or cutting mechanism.
- LED electrical behaviour was inferred from UNO output state reporting; photographic or oscilloscope evidence may be added later for stronger dissertation evidence.

## Conclusion

The Arduino UNO safety-logic bench test passed for firmware boot, serial reporting, XIAO input monitoring, and idle safe-state LED output logic. The result supports using the UNO as a deterministic serial safety-logic layer for later integration with the PC-based YOLOv8 model.
