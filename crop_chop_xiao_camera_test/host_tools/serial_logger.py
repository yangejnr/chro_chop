#!/usr/bin/env python3
import argparse
import pathlib
import sys
import time

import serial
from serial.tools import list_ports


def list_serial_ports():
    return [port.device for port in list_ports.comports()]


def choose_port(port):
    if port:
        return port

    ports = list_serial_ports()
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


def main():
    parser = argparse.ArgumentParser(description="Record serial output from the XIAO ESP32S3 Sense.")
    parser.add_argument("--port", help="Serial port, for example /dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    port = choose_port(args.port)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    end_time = time.monotonic() + args.duration
    with serial.Serial(port, args.baud, timeout=0.5) as connection, args.output.open("w", encoding="utf-8") as log_file:
      while time.monotonic() < end_time:
          data = connection.readline()
          if not data:
              continue
          text = data.decode("utf-8", errors="replace")
          sys.stdout.write(text)
          sys.stdout.flush()
          log_file.write(text)
          log_file.flush()


if __name__ == "__main__":
    main()
