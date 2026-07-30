#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path

import cv2
import serial
from serial.tools import list_ports
from ultralytics import YOLO


def serial_ports():
    return [port.device for port in list_ports.comports()]


def choose_port(requested):
    if requested:
        return requested
    ports = serial_ports()
    if len(ports) == 1:
        return ports[0]
    if not ports:
        raise SystemExit("No serial ports detected. Connect the UNO by USB and retry.")

    print("Multiple serial ports detected:")
    for index, port in enumerate(ports, start=1):
        print(f"  {index}. {port}")
    selected = input("Enter the UNO serial port path: ").strip()
    if selected not in ports:
        raise SystemExit(f"Selected port is not in detected ports: {selected}")
    return selected


def normalised_detection(result):
    if result.boxes is None or len(result.boxes) == 0:
        return None

    height, width = result.orig_shape
    best_box = max(result.boxes, key=lambda box: float(box.conf[0]))
    class_id = int(best_box.cls[0])
    label = str(result.names[class_id]).replace(" ", "_")
    confidence = float(best_box.conf[0])
    x1, y1, x2, y2 = [float(value) for value in best_box.xyxy[0].tolist()]

    center_x = ((x1 + x2) / 2.0) / width
    center_y = ((y1 + y2) / 2.0) / height
    box_width = (x2 - x1) / width
    box_height = (y2 - y1) / height
    return label, confidence, center_x, center_y, box_width, box_height


def send_line(connection, line):
    connection.write((line + "\n").encode("ascii"))
    connection.flush()


def read_available(connection):
    responses = []
    while connection.in_waiting:
        responses.append(connection.readline().decode("ascii", errors="replace").strip())
    return responses


def parse_args():
    parser = argparse.ArgumentParser(description="Run YOLO on the PC and send model decisions to an Arduino UNO.")
    parser.add_argument("--port", help="UNO serial port, for example /dev/ttyACM0 or COM3.")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--source", default="0", help="OpenCV source: webcam index, video file, or stream URL.")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--uno-threshold", type=float, default=0.50)
    parser.add_argument("--send-rate-hz", type=float, default=5.0)
    parser.add_argument("--arm", action="store_true", help="Arm UNO logic after connecting. Still does not drive actuators.")
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--log-jsonl", type=Path)
    return parser.parse_args()


def open_source(source):
    if source.isdigit():
        return cv2.VideoCapture(int(source))
    return cv2.VideoCapture(source)


def draw_bridge_overlay(frame, command, responses, armed):
    decision = "DANGER command sent" if command.startswith("DETECTION ") and armed else "SAFE / no active detection"
    colour = (0, 255, 255) if decision.startswith("DANGER") else (0, 255, 0)
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 82), (0, 0, 0), -1)
    cv2.putText(frame, decision, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, colour, 2, cv2.LINE_AA)
    cv2.putText(frame, command[:92], (12, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    if responses:
        cv2.putText(frame, responses[-1][:92], (12, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)


def main():
    args = parse_args()
    port = choose_port(args.port)
    model = YOLO(args.model)
    capture = open_source(args.source)
    if not capture.isOpened():
        raise SystemExit(f"Could not open video source: {args.source}")

    json_log = None
    if args.log_jsonl:
        args.log_jsonl.parent.mkdir(parents=True, exist_ok=True)
        json_log = args.log_jsonl.open("w", encoding="utf-8")

    send_interval = 1.0 / args.send_rate_hz if args.send_rate_hz > 0 else 0.2
    last_send = 0.0
    frames = 0
    started = time.monotonic()

    with serial.Serial(port, args.baud, timeout=0.1) as connection:
        time.sleep(2.0)
        send_line(connection, "HELLO")
        send_line(connection, f"SET_THRESHOLD {args.uno_threshold:.3f}")
        send_line(connection, "ARM_LOGIC" if args.arm else "DISARM_LOGIC")

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    time.sleep(0.05)
                    continue

                result = model.predict(frame, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
                detection = normalised_detection(result)
                now = time.monotonic()
                frames += 1

                command = "NO_DETECTION"
                if detection:
                    label, confidence, center_x, center_y, box_width, box_height = detection
                    command = (
                        f"DETECTION {label} {confidence:.3f} {center_x:.3f} {center_y:.3f} "
                        f"{box_width:.3f} {box_height:.3f}"
                    )

                responses = read_available(connection)
                if now - last_send >= send_interval:
                    send_line(connection, command)
                    last_send = now

                if json_log:
                    json_log.write(json.dumps({
                        "timestamp": time.time(),
                        "frame": frames,
                        "command": command,
                        "uno_responses": responses,
                    }) + "\n")
                    json_log.flush()

                if not args.no_display:
                    annotated = result.plot()
                    draw_bridge_overlay(annotated, command, responses, args.arm)
                    cv2.imshow("Crop Chop PC YOLO to UNO", annotated)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

                if args.duration and now - started >= args.duration:
                    break
        finally:
            send_line(connection, "DISARM_LOGIC")
            capture.release()
            if json_log:
                json_log.close()
            if not args.no_display:
                cv2.destroyAllWindows()

    elapsed = time.monotonic() - started
    print(f"Processed {frames} frames in {elapsed:.2f} s ({frames / elapsed if elapsed else 0:.2f} FPS).")


if __name__ == "__main__":
    main()
