#!/usr/bin/env python3
import argparse
import csv
import json
import time
from pathlib import Path

import cv2
import serial
from serial.tools import list_ports
from ultralytics import YOLO


DEFAULT_XIAO_STREAM = "http://192.168.4.1/stream"
DEFAULT_SERVO_IDS = "1,2,3"
DEFAULT_SERVO_POSITIONS = "1900,2048,2200"
STOP_CLASS = "person"


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


def detections_from_result(result):
    if result.boxes is None or len(result.boxes) == 0:
        return []

    height, width = result.orig_shape
    detections = []
    for box in result.boxes:
        class_id = int(box.cls[0])
        label = str(result.names[class_id]).replace(" ", "_")
        confidence = float(box.conf[0])
        x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
        detections.append({
            "label": label,
            "confidence": confidence,
            "center_x": ((x1 + x2) / 2.0) / width,
            "center_y": ((y1 + y2) / 2.0) / height,
            "width": (x2 - x1) / width,
            "height": (y2 - y1) / height,
        })
    return sorted(detections, key=lambda detection: detection["confidence"], reverse=True)


def detection_command(detections):
    if not detections:
        return "NO_DETECTION"
    detection = detections[0]
    return (
        f"DETECTION {detection['label']} {detection['confidence']:.3f} "
        f"{detection['center_x']:.3f} {detection['center_y']:.3f} "
        f"{detection['width']:.3f} {detection['height']:.3f}"
    )


def has_stop_detection(detections, stop_class):
    return any(detection["label"] == stop_class for detection in detections)


def send_line(connection, line):
    connection.write((line + "\n").encode("ascii"))
    connection.flush()


def read_available(connection):
    responses = []
    while connection.in_waiting:
        responses.append(connection.readline().decode("ascii", errors="replace").strip())
    return responses


def send_command(connection, line, wait_s=0.05):
    print(f">> {line}")
    send_line(connection, line)
    if wait_s > 0:
        time.sleep(wait_s)
    responses = read_available(connection)
    for response in responses:
        print(f"<< {response}")
    return responses


def parse_int_list(text, name):
    try:
        values = [int(value.strip()) for value in text.split(",") if value.strip()]
    except ValueError as exc:
        raise SystemExit(f"Invalid {name}: {text}") from exc
    if not values:
        raise SystemExit(f"{name} cannot be empty")
    return values


def parse_args():
    parser = argparse.ArgumentParser(description="Run YOLO on the PC and send model decisions to an Arduino UNO.")
    parser.add_argument("--port", help="UNO serial port, for example /dev/ttyACM0 or COM3.")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--source", default=DEFAULT_XIAO_STREAM, help="OpenCV source. Defaults to the XIAO ESP32S3 stream.")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--uno-threshold", type=float, default=0.50)
    parser.add_argument("--send-rate-hz", type=float, default=5.0)
    parser.add_argument("--arm", action="store_true", help="Arm UNO logic after connecting. Still does not drive actuators.")
    parser.add_argument("--servo-sequence", action="store_true", help="Sequentially move configured servos until a person is detected.")
    parser.add_argument("--servo-ids", default=DEFAULT_SERVO_IDS, help="Comma-separated servo IDs for sequence mode.")
    parser.add_argument("--servo-positions", default=DEFAULT_SERVO_POSITIONS, help="Comma-separated safe positions for each servo step.")
    parser.add_argument("--servo-speed", type=int, default=100)
    parser.add_argument("--servo-step-interval", type=float, default=1.5)
    parser.add_argument("--skip-servo-torque-enable", action="store_true")
    parser.add_argument("--stop-class", default=STOP_CLASS)
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--log-jsonl", type=Path)
    parser.add_argument("--log-csv", type=Path)
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


def next_servo_command(servo_ids, servo_positions, servo_speed, step_index):
    servo_id = servo_ids[step_index % len(servo_ids)]
    position = servo_positions[(step_index // len(servo_ids)) % len(servo_positions)]
    return f"SERVO_MOVE_SAFE {servo_id} {position} {servo_speed}"


def write_csv_row(writer, row):
    if writer:
        writer.writerow(row)


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

    csv_file = None
    csv_writer = None
    if args.log_csv:
        args.log_csv.parent.mkdir(parents=True, exist_ok=True)
        csv_file = args.log_csv.open("w", newline="", encoding="utf-8")
        csv_writer = csv.DictWriter(csv_file, fieldnames=[
            "timestamp", "frame", "event", "command", "stop_detected",
            "best_label", "best_confidence", "uno_response",
        ])
        csv_writer.writeheader()

    servo_ids = parse_int_list(args.servo_ids, "servo IDs")
    servo_positions = parse_int_list(args.servo_positions, "servo positions")
    send_interval = 1.0 / args.send_rate_hz if args.send_rate_hz > 0 else 0.2
    last_send = 0.0
    last_servo_step = 0.0
    servo_step_index = 0
    sequence_stopped = False
    frames = 0
    started = time.monotonic()

    with serial.Serial(port, args.baud, timeout=0.1) as connection:
        time.sleep(2.0)
        send_command(connection, "HELLO")
        send_command(connection, f"SET_THRESHOLD {args.uno_threshold:.3f}")
        should_arm = args.arm or args.servo_sequence
        send_command(connection, "ARM_LOGIC" if should_arm else "DISARM_LOGIC")
        if args.servo_sequence and not args.skip_servo_torque_enable:
            for servo_id in servo_ids:
                send_command(connection, f"SERVO_TORQUE {servo_id} 1", wait_s=0.1)

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    time.sleep(0.05)
                    continue

                result = model.predict(frame, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
                detections = detections_from_result(result)
                now = time.monotonic()
                frames += 1

                command = detection_command(detections)
                stop_detected = has_stop_detection(detections, args.stop_class)
                event = "detection"
                if stop_detected and not sequence_stopped:
                    send_command(connection, command)
                    for servo_id in servo_ids:
                        send_command(connection, f"SERVO_TORQUE {servo_id} 0", wait_s=0.1)
                    send_command(connection, "DISARM_LOGIC")
                    sequence_stopped = True
                    event = "stop_person_detected"
                elif args.servo_sequence and not sequence_stopped and now - last_servo_step >= args.servo_step_interval:
                    command = next_servo_command(servo_ids, servo_positions, args.servo_speed, servo_step_index)
                    send_command(connection, command, wait_s=0.1)
                    servo_step_index += 1
                    last_servo_step = now
                    event = "servo_step"

                responses = read_available(connection)
                if not args.servo_sequence and now - last_send >= send_interval:
                    send_command(connection, command, wait_s=0.0)
                    last_send = now

                best_detection = detections[0] if detections else {}
                if json_log:
                    json_log.write(json.dumps({
                        "timestamp": time.time(),
                        "frame": frames,
                        "event": event,
                        "command": command,
                        "stop_detected": stop_detected,
                        "detections": detections,
                        "uno_responses": responses,
                    }) + "\n")
                    json_log.flush()
                write_csv_row(csv_writer, {
                    "timestamp": time.time(),
                    "frame": frames,
                    "event": event,
                    "command": command,
                    "stop_detected": int(stop_detected),
                    "best_label": best_detection.get("label", ""),
                    "best_confidence": best_detection.get("confidence", ""),
                    "uno_response": responses[-1] if responses else "",
                })

                if not args.no_display:
                    annotated = result.plot()
                    draw_bridge_overlay(annotated, command, responses, should_arm and not sequence_stopped)
                    cv2.imshow("Crop Chop PC YOLO to UNO", annotated)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

                if args.duration and now - started >= args.duration:
                    break
        finally:
            if args.servo_sequence:
                for servo_id in servo_ids:
                    send_command(connection, f"SERVO_TORQUE {servo_id} 0", wait_s=0.1)
            send_command(connection, "DISARM_LOGIC")
            capture.release()
            if json_log:
                json_log.close()
            if csv_file:
                csv_file.close()
            if not args.no_display:
                cv2.destroyAllWindows()

    elapsed = time.monotonic() - started
    print(f"Processed {frames} frames in {elapsed:.2f} s ({frames / elapsed if elapsed else 0:.2f} FPS).")


if __name__ == "__main__":
    main()
