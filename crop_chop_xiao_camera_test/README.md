# Crop Chop XIAO ESP32S3 Sense Camera Test

Reproducible camera-only test project for the MSc Robotics project "Crop Chop: The Autonomous Agri-Trimmer".

This project is limited to the Seeed Studio XIAO ESP32S3 Sense and its camera. It does not test servos, bus-servo drivers, ESCs, brushless motors or cutting hardware.

## Current Host Inspection

- Date inspected: 2026-07-29
- Host OS: Linux `6.17.0-35-generic` on x86_64
- PlatformIO executable: `/usr/bin/pio`
- PlatformIO status: installed but currently failing with `AttributeError: 'PlatformioCLI' object has no attribute 'resultcallback'`
- Arduino CLI: not found on `PATH`
- Serial ports detected during setup: none under `/dev/ttyACM*` or `/dev/ttyUSB*`
- Official XIAO camera pin source: installed Arduino ESP32 `CameraWebServer/camera_pins.h`, `CAMERA_MODEL_XIAO_ESP32S3`

## Project Layout

```text
crop_chop_xiao_camera_test/
├── firmware/
│   ├── platformio.ini
│   ├── src/main.cpp
│   └── include/camera_config.h
├── host_tools/
│   ├── camera_test_runner.py
│   ├── serial_logger.py
│   └── requirements.txt
├── data/
│   ├── raw/
│   ├── images/
│   └── processed/
├── reports/
│   └── camera_test_report.md
├── docs/test_procedure.md
└── README.md
```

## Firmware Behaviour

The firmware starts serial at 115200 baud, initialises the camera using the official XIAO ESP32S3 Sense pin mapping, enables PSRAM-backed frame buffers when PSRAM is detected, starts a Wi-Fi access point and exposes:

- `/` browser status page
- `/stream` MJPEG stream
- `/capture` single JPEG capture
- `/health` JSON health status
- `/metrics` JSON measured performance metrics
- `/config` active camera configuration
- `/set-resolution?value=QVGA`, `VGA` or `SVGA`
- `/reset-metrics`

Default access point:

- SSID: `CropChop-Camera-Test`
- Password: `CropChopTest123`
- Default ESP32 AP URL: `http://192.168.4.1`

Change the test password in `firmware/include/camera_config.h` before field use.

## Build and Upload

From this directory:

```bash
cd firmware
env PLATFORMIO_CORE_DIR=/home/henry/crop-chop/crop_chop_xiao_camera_test/.pio_core ../.venv/bin/pio run
env PLATFORMIO_CORE_DIR=/home/henry/crop-chop/crop_chop_xiao_camera_test/.pio_core ../.venv/bin/pio run --target upload --upload-port /dev/ttyACM0
env PLATFORMIO_CORE_DIR=/home/henry/crop-chop/crop_chop_xiao_camera_test/.pio_core ../.venv/bin/pio device monitor --baud 115200 --port /dev/ttyACM0
```

The project-local PlatformIO command above is used because the host `/usr/bin/pio` currently fails before loading a project. If the system PlatformIO is repaired later, plain `pio run` is also suitable.

If upload fails, enter bootloader mode:

1. Hold `BOOT`.
2. Tap `RESET`.
3. Release `BOOT`.
4. Retry the upload command with the detected serial port.

Do not run erase or SD-format commands for this camera test.

## Run Host Test

Install Python dependencies:

```bash
python3 -m pip install -r host_tools/requirements.txt
```

After firmware upload, connect the computer Wi-Fi to `CropChop-Camera-Test`, then run:

```bash
python3 host_tools/camera_test_runner.py --port /dev/ttyACM0 --base-url http://192.168.4.1
```

The runner records:

- `data/raw/camera_test_TIMESTAMP.csv`
- `data/processed/camera_test_summary_TIMESTAMP.json`
- `data/raw/serial_log_TIMESTAMP.txt`
- `data/images/TIMESTAMP/*.jpg`
- `reports/camera_test_report_TIMESTAMP.md`

The runner stops and asks for the correct port if multiple serial ports are visible. It fails rather than fabricating data if the serial port, camera server or measurements are unavailable.
