#!/usr/bin/env python3
import argparse
import csv
import json
import platform
import statistics
import threading
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests
import serial
from PIL import Image
from serial.tools import list_ports


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
IMAGE_DIR = PROJECT_ROOT / "data" / "images"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
RESOLUTIONS = ("QVGA", "VGA", "SVGA")


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def detected_ports():
    return [port.device for port in list_ports.comports()]


def choose_port(requested):
    if requested:
        return requested
    ports = detected_ports()
    if len(ports) == 1:
        return ports[0]
    if not ports:
        raise SystemExit("No serial ports detected. Connect the XIAO ESP32S3 Sense by USB-C and retry.")
    print("Multiple serial ports detected:")
    for index, device in enumerate(ports, start=1):
        print(f"  {index}. {device}")
    selected = input("Enter the XIAO serial port path: ").strip()
    if selected not in ports:
        raise SystemExit(f"Selected port is not in detected ports: {selected}")
    return selected


def serial_capture(port, baud, output_path, stop_event):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with serial.Serial(port, baud, timeout=0.5) as connection, output_path.open("w", encoding="utf-8") as log_file:
        while not stop_event.is_set():
            data = connection.readline()
            if not data:
                continue
            text = data.decode("utf-8", errors="replace")
            print(text, end="")
            log_file.write(text)
            log_file.flush()


def wait_for_server(base_url, timeout_s):
    deadline = time.monotonic() + timeout_s
    last_error = None
    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{base_url}/health", timeout=3)
            if response.ok:
                return response.json()
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(2)
    raise SystemExit(f"Camera server did not become available at {base_url}: {last_error}")


def get_json(base_url, route):
    response = requests.get(f"{base_url}{route}", timeout=5)
    response.raise_for_status()
    return response.json()


def validate_jpeg(data):
    with Image.open(BytesIO(data)) as image:
        image.verify()
        return image.format == "JPEG"


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((percent / 100.0) * (len(ordered) - 1)))
    return ordered[index]


def test_resolution(base_url, resolution, duration_s, image_output_dir):
    requests.get(f"{base_url}/set-resolution", params={"value": resolution}, timeout=5).raise_for_status()
    requests.get(f"{base_url}/reset-metrics", timeout=5).raise_for_status()

    deadline = time.monotonic() + duration_s
    requested = 0
    successful = 0
    failed = 0
    latencies_ms = []
    jpeg_sizes = []
    sample_count = 0
    fps_samples = []
    observations = []

    while time.monotonic() < deadline:
        started = time.monotonic()
        requested += 1
        try:
            response = requests.get(f"{base_url}/capture", timeout=10)
            latency_ms = (time.monotonic() - started) * 1000.0
            if response.ok and validate_jpeg(response.content):
                successful += 1
                latencies_ms.append(latency_ms)
                jpeg_sizes.append(len(response.content))
                if sample_count < 5:
                    sample_count += 1
                    image_path = image_output_dir / f"{resolution.lower()}_{sample_count:02d}.jpg"
                    image_path.write_bytes(response.content)
            else:
                failed += 1
        except (requests.RequestException, OSError):
            failed += 1

        metrics = get_json(base_url, "/metrics")
        fps_samples.append(float(metrics.get("current_fps", 0.0)))
        observations.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "resolution": resolution,
            "requested_frames": requested,
            "successful_frames": successful,
            "failed_frames": failed,
            "latency_ms": latencies_ms[-1] if latencies_ms else "",
            "current_fps": fps_samples[-1],
            "jpeg_size_bytes": jpeg_sizes[-1] if jpeg_sizes else "",
            "minimum_free_heap": metrics.get("minimum_free_heap"),
        })

    metrics = get_json(base_url, "/metrics")
    health = get_json(base_url, "/health")
    success_rate = successful / requested if requested else 0.0

    summary = {
        "resolution": resolution,
        "number_of_requested_frames": requested,
        "number_of_successful_frames": successful,
        "number_of_failed_frames": failed,
        "success_rate": success_rate,
        "mean_fps": statistics.fmean(fps_samples) if fps_samples else None,
        "minimum_fps": min(fps_samples) if fps_samples else None,
        "maximum_fps": max(fps_samples) if fps_samples else None,
        "mean_capture_latency_ms": statistics.fmean(latencies_ms) if latencies_ms else None,
        "median_capture_latency_ms": statistics.median(latencies_ms) if latencies_ms else None,
        "p95_capture_latency_ms": percentile(latencies_ms, 95),
        "minimum_capture_latency_ms": min(latencies_ms) if latencies_ms else None,
        "maximum_capture_latency_ms": max(latencies_ms) if latencies_ms else None,
        "mean_jpeg_file_size_bytes": statistics.fmean(jpeg_sizes) if jpeg_sizes else None,
        "minimum_free_heap": metrics.get("minimum_free_heap"),
        "psram_detection_status": health.get("psram_detected"),
        "camera_initialisation_status": health.get("camera_initialised"),
        "camera_model": health.get("camera_model"),
        "samples_saved": sample_count,
    }
    return observations, summary


def write_csv(path, rows):
    fieldnames = [
        "test_date_local", "operating_system", "serial_port", "firmware_version",
        "camera_model", "resolution", "timestamp", "requested_frames",
        "successful_frames", "failed_frames", "latency_ms", "current_fps",
        "jpeg_size_bytes", "minimum_free_heap",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path, summary):
    rows = []
    for item in summary["results"]:
        rows.append(
            f"| {item['resolution']} | {item['number_of_requested_frames']} | "
            f"{item['number_of_successful_frames']} | {item['number_of_failed_frames']} | "
            f"{item['success_rate']:.3f} | {item['mean_fps']} | "
            f"{item['mean_capture_latency_ms']} | {item['mean_jpeg_file_size_bytes']} | "
            f"{item['minimum_free_heap']} |"
        )

    passed = all(
        item["camera_initialisation_status"] and item["number_of_successful_frames"] > 0 and item["samples_saved"] >= 5
        for item in summary["results"]
    )
    assessment = "PASS" if passed else "FAIL or INCOMPLETE"

    text = f"""# Crop Chop XIAO ESP32S3 Sense Camera Test Report

## Date and time

{summary["test_date_local"]}

## Project name

Crop Chop: The Autonomous Agri-Trimmer

## Test objective

Detect, initialise and characterise the Seeed Studio XIAO ESP32S3 Sense camera without testing any actuator or cutting hardware.

## Hardware under test

Seeed Studio XIAO ESP32S3 Sense camera system connected over USB-C.

## Firmware and software environment

- Firmware version: {summary["firmware_version"]}
- Host operating system: {summary["operating_system"]}
- Serial port: {summary["serial_port"]}
- Camera server URL: {summary["base_url"]}

## Camera sensor identified

{summary["camera_model"]}

## PSRAM status

{summary["psram_detection_status"]}

## Test procedure

The Python runner recorded serial output, waited for the camera HTTP server, tested QVGA, VGA and SVGA sequentially for {summary["duration_seconds"]} seconds each, requested repeated JPEG captures, validated JPEG readability and saved up to five sample images per supported resolution.

## Results

| Resolution | Requested | Successful | Failed | Success rate | Mean FPS | Mean latency ms | Mean JPEG bytes | Minimum free heap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Pass/fail assessment

{assessment}

No result in this report is estimated. Missing values indicate measurements that were not completed.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run reproducible XIAO ESP32S3 Sense camera tests.")
    parser.add_argument("--port", help="Serial port, for example /dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--base-url", default="http://192.168.4.1")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--server-timeout", type=int, default=120)
    args = parser.parse_args()

    run_id = timestamp()
    port = choose_port(args.port)
    serial_log_path = RAW_DIR / f"serial_log_{run_id}.txt"
    csv_path = RAW_DIR / f"camera_test_{run_id}.csv"
    summary_path = PROCESSED_DIR / f"camera_test_summary_{run_id}.json"
    report_path = REPORTS_DIR / f"camera_test_report_{run_id}.md"
    image_output_dir = IMAGE_DIR / run_id
    image_output_dir.mkdir(parents=True, exist_ok=True)

    stop_event = threading.Event()
    logger = threading.Thread(target=serial_capture, args=(port, args.baud, serial_log_path, stop_event), daemon=True)
    logger.start()

    try:
        health = wait_for_server(args.base_url, args.server_timeout)
        all_observations = []
        results = []
        firmware_version = "unknown"
        test_date_local = datetime.now().isoformat(timespec="seconds")
        operating_system = f"{platform.system()} {platform.release()} ({platform.machine()})"

        for resolution in RESOLUTIONS:
            observations, result = test_resolution(args.base_url, resolution, args.duration, image_output_dir)
            for observation in observations:
                observation.update({
                    "test_date_local": test_date_local,
                    "operating_system": operating_system,
                    "serial_port": port,
                    "firmware_version": firmware_version,
                    "camera_model": health.get("camera_model", "unknown"),
                })
            all_observations.extend(observations)
            results.append(result)

        summary = {
            "test_date_local": test_date_local,
            "operating_system": operating_system,
            "serial_port": port,
            "firmware_version": firmware_version,
            "camera_model": health.get("camera_model", "unknown"),
            "psram_detection_status": health.get("psram_detected"),
            "camera_initialisation_status": health.get("camera_initialised"),
            "base_url": args.base_url,
            "duration_seconds": args.duration,
            "serial_log": str(serial_log_path),
            "images_directory": str(image_output_dir),
            "results": results,
        }

        write_csv(csv_path, all_observations)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        write_report(report_path, summary)

        print(f"CSV: {csv_path}")
        print(f"Summary JSON: {summary_path}")
        print(f"Serial log: {serial_log_path}")
        print(f"Images: {image_output_dir}")
        print(f"Report: {report_path}")
    finally:
        stop_event.set()
        logger.join(timeout=2)


if __name__ == "__main__":
    main()
