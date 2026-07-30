#!/usr/bin/env python3
import argparse
import csv
import time
from pathlib import Path

import serial


def send_command(connection, command, wait_s=0.25):
    print(f">> {command}")
    connection.write((command + "\n").encode("ascii"))
    connection.flush()
    time.sleep(wait_s)
    responses = []
    while connection.in_waiting:
        response = connection.readline().decode("ascii", errors="replace").strip()
        responses.append(response)
        print(f"<< {response}")
    if not responses:
        print("<< NO_RESPONSE")
    return responses


def parse_args():
    parser = argparse.ArgumentParser(description="Direct Arduino UNO servo-bus diagnostic without YOLO.")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--servo-ids", default="1,2,3")
    parser.add_argument("--scan-max-id", type=int, default=20)
    parser.add_argument("--position-a", type=int, default=1900)
    parser.add_argument("--position-b", type=int, default=2200)
    parser.add_argument("--speed", type=int, default=100)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--step-delay", type=float, default=1.5)
    parser.add_argument("--log-csv", type=Path, default=Path("runs/servo_bus_diagnostic.csv"))
    return parser.parse_args()


def parse_servo_ids(text):
    try:
        values = [int(value.strip()) for value in text.split(",") if value.strip()]
    except ValueError as exc:
        raise SystemExit(f"Invalid --servo-ids: {text}") from exc
    if not values:
        raise SystemExit("--servo-ids cannot be empty")
    return values


def write_rows(writer, command, responses):
    timestamp = time.time()
    if responses:
        for response in responses:
            writer.writerow({"timestamp": timestamp, "command": command, "response": response})
    else:
        writer.writerow({"timestamp": timestamp, "command": command, "response": "NO_RESPONSE"})


def main():
    args = parse_args()
    servo_ids = parse_servo_ids(args.servo_ids)
    args.log_csv.parent.mkdir(parents=True, exist_ok=True)

    with args.log_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["timestamp", "command", "response"])
        writer.writeheader()

        with serial.Serial(args.port, args.baud, timeout=0.2) as connection:
            time.sleep(2.0)
            for command in ["HELLO", "STATUS", f"SERVO_SCAN {args.scan_max_id}"]:
                write_rows(writer, command, send_command(connection, command))

            for servo_id in servo_ids:
                for command in [f"SERVO_PING {servo_id}", f"SERVO_STATUS {servo_id}"]:
                    write_rows(writer, command, send_command(connection, command))

            write_rows(writer, "ARM_LOGIC", send_command(connection, "ARM_LOGIC"))

            for servo_id in servo_ids:
                command = f"SERVO_TORQUE {servo_id} 1"
                write_rows(writer, command, send_command(connection, command))

            for _ in range(args.cycles):
                for position in [args.position_a, args.position_b]:
                    for servo_id in servo_ids:
                        command = f"SERVO_MOVE_SAFE {servo_id} {position} {args.speed}"
                        write_rows(writer, command, send_command(connection, command, wait_s=0.4))
                        time.sleep(args.step_delay)

            for servo_id in servo_ids:
                command = f"SERVO_TORQUE {servo_id} 0"
                write_rows(writer, command, send_command(connection, command))

            write_rows(writer, "DISARM_LOGIC", send_command(connection, "DISARM_LOGIC"))

    print(f"Diagnostic log written to {args.log_csv}")


if __name__ == "__main__":
    main()
