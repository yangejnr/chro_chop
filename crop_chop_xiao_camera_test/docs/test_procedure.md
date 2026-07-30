# XIAO ESP32S3 Sense Camera Test Procedure

## Scope

This procedure tests only the Seeed Studio XIAO ESP32S3 Sense camera system. Do not connect or operate servos, ESCs, motors or cutting hardware during this test.

## Pre-Test Inspection

1. Confirm the host OS:

   ```bash
   uname -a
   ```

2. Confirm available serial ports:

   ```bash
   ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
   ```

3. Confirm PlatformIO:

   ```bash
   command -v pio
   pio system info
   ```

4. If PlatformIO is unavailable, install/configure it where permitted. If it is present but broken, record the exact error before changing the environment.

## Firmware Build

1. Open `crop_chop_xiao_camera_test/firmware` in VS Code or a terminal.
2. Build:

   ```bash
   env PLATFORMIO_CORE_DIR=/home/henry/crop-chop/crop_chop_xiao_camera_test/.pio_core ../.venv/bin/pio run
   ```

3. Connect the XIAO ESP32S3 Sense by USB-C.
4. Confirm there is exactly one likely serial port. If more than one appears, identify the XIAO before uploading.
5. Upload:

   ```bash
   env PLATFORMIO_CORE_DIR=/home/henry/crop-chop/crop_chop_xiao_camera_test/.pio_core ../.venv/bin/pio run --target upload --upload-port /dev/ttyACM0
   ```

6. If upload fails, hold `BOOT`, tap `RESET`, release `BOOT`, then retry upload.

## Serial Verification

1. Open the serial monitor at 115200 baud:

   ```bash
   pio device monitor --baud 115200 --port /dev/ttyACM0
   ```

2. Record the complete structured device-information block.
3. Confirm:
   - Camera initialisation result is `0x00000000`.
   - PSRAM status is printed.
   - Camera product ID is printed.
   - Interpreted camera model is `OV2640`, `OV3660` or `unknown`.
   - Access point IP is printed.

Do not mark this section passed unless the serial output is observed and recorded.

## Browser Stream Test

1. Connect host Wi-Fi to `CropChop-Camera-Test`.
2. Open `http://192.168.4.1/`.
3. Confirm `/stream` shows a live MJPEG stream.
4. Open `/capture` and save a JPEG manually if needed for quick inspection.

Do not record stream success unless live images are visible in the browser.

## Automated Performance Test

Run:

```bash
python3 host_tools/camera_test_runner.py --port /dev/ttyACM0 --base-url http://192.168.4.1
```

The runner tests QVGA, VGA and SVGA for 30 seconds each, captures repeated JPEGs, validates saved sample images and writes CSV, JSON, serial log and Markdown report artifacts.

## Pass Criteria

- XIAO serial port is detected.
- Firmware builds and uploads without erasing unrelated flash partitions.
- Camera initialises successfully.
- Camera model is identified as OV2640, OV3660 or unknown using the sensor PID.
- `/health`, `/metrics`, `/capture` and `/stream` respond.
- At least five valid JPEG sample images are saved for each supported tested resolution.
- CSV, JSON and Markdown outputs are generated.

Any failed or unavailable measurement must be reported as failed or incomplete, not estimated.
