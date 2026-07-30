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


def has_ok_servo_response(responses):
    return any("SERVO_PING" in response and " ok=1" in response for response in responses)


def parse_args():
    parser = argparse.ArgumentParser(description="Direct Arduino UNO servo-bus diagnostic without YOLO.")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--servo-ids", default="1,2,3")
    parser.add_argument("--servo-bauds", default="1000000,115200,500000,250000,57600")
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


def parse_servo_bauds(text):
    try:
        values = [int(value.strip()) for value in text.split(",") if value.strip()]
    except ValueError as exc:
        raise SystemExit(f"Invalid --servo-bauds: {text}") from exc
    if not values:
        raise SystemExit("--servo-bauds cannot be empty")
    supported = {1000000, 500000, 250000, 115200, 57600}
    unsupported = [value for value in values if value not in supported]
    if unsupported:
        raise SystemExit(f"Unsupported --servo-bauds values: {unsupported}")
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
    servo_bauds = parse_servo_bauds(args.servo_bauds)
    args.log_csv.parent.mkdir(parents=True, exist_ok=True)

    with args.log_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["timestamp", "command", "response"])
        writer.writeheader()

        with serial.Serial(args.port, args.baud, timeout=0.2) as connection:
            time.sleep(2.0)
            for command in ["HELLO", "STATUS"]:
                write_rows(writer, command, send_command(connection, command))

            working_baud = None
            for servo_baud in servo_bauds:
                command = f"SERVO_BAUD {servo_baud}"
                write_rows(writer, command, send_command(connection, command, wait_s=0.4))

                command = f"SERVO_SCAN {args.scan_max_id}"
                scan_wait_s = max(1.0, min(8.0, args.scan_max_id * 0.08 + 0.5))
                write_rows(writer, command, send_command(connection, command, wait_s=scan_wait_s))

                for servo_id in servo_ids:
                    command = f"SERVO_PING {servo_id}"
                    responses = send_command(connection, command, wait_s=0.4)
                    write_rows(writer, command, responses)
                    if has_ok_servo_response(responses):
                        working_baud = servo_baud

                    command = f"SERVO_STATUS {servo_id}"
                    write_rows(writer, command, send_command(connection, command, wait_s=0.4))

                if working_baud is not None:
                    print(f"Servo acknowledgement found at {working_baud} baud.")
                    break

            if working_baud is None:
                print("No servo acknowledgement found at tested baud rates.")
                print("Skipping torque and movement commands for safety.")
                print("Check adapter jumper mode, RX/TX labeling, shared GND, servo power and servo IDs.")
                print(f"Diagnostic log written to {args.log_csv}")
                return

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
