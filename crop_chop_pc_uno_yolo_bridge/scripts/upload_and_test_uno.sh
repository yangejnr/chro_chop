#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$PROJECT_DIR/.." && pwd)"

PORT="${PORT:-/dev/ttyUSB0}"
SERVO_IDS="${SERVO_IDS:-1,2,3}"
SERVO_BAUDS="${SERVO_BAUDS:-1000000,115200,500000,250000,57600}"
POSITION_A="${POSITION_A:-1900}"
POSITION_B="${POSITION_B:-2200}"
SPEED="${SPEED:-100}"
CYCLES="${CYCLES:-1}"
SCAN_MAX_ID="${SCAN_MAX_ID:-20}"
PLATFORMIO_CORE_DIR="${PLATFORMIO_CORE_DIR:-$REPO_DIR/crop_chop_xiao_camera_test/.pio_core}"
PIO_BIN="${PIO_BIN:-$REPO_DIR/crop_chop_xiao_camera_test/.venv/bin/pio}"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"
LOG_CSV="${LOG_CSV:-$PROJECT_DIR/runs/upload_and_servo_test.csv}"

usage() {
  cat <<EOF
Upload Crop Chop UNO firmware, then run the servo-bus diagnostic.

Usage:
  $(basename "$0") [options]

Options:
  --port PORT             UNO serial port. Default: $PORT
  --servo-ids IDS         Comma-separated servo IDs. Default: $SERVO_IDS
  --servo-bauds BAUDS     Comma-separated servo-bus baud rates. Default: $SERVO_BAUDS
  --position-a VALUE      First safe position. Default: $POSITION_A
  --position-b VALUE      Second safe position. Default: $POSITION_B
  --speed VALUE           Servo speed. Default: $SPEED
  --cycles VALUE          Movement cycles after acknowledgement. Default: $CYCLES
  --scan-max-id VALUE     Highest servo ID to scan. Default: $SCAN_MAX_ID
  --log-csv PATH          Diagnostic CSV path. Default: $LOG_CSV
  -h, --help              Show this help.

Examples:
  $(basename "$0") --port /dev/ttyUSB0
  $(basename "$0") --port /dev/ttyACM0 --servo-ids 1,2,3

You can also override values with environment variables:
  PORT=/dev/ttyACM0 SERVO_IDS=1,2,3 $(basename "$0")
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --servo-ids)
      SERVO_IDS="$2"
      shift 2
      ;;
    --servo-bauds)
      SERVO_BAUDS="$2"
      shift 2
      ;;
    --position-a)
      POSITION_A="$2"
      shift 2
      ;;
    --position-b)
      POSITION_B="$2"
      shift 2
      ;;
    --speed)
      SPEED="$2"
      shift 2
      ;;
    --cycles)
      CYCLES="$2"
      shift 2
      ;;
    --scan-max-id)
      SCAN_MAX_ID="$2"
      shift 2
      ;;
    --log-csv)
      LOG_CSV="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -x "$PIO_BIN" ]]; then
  echo "PlatformIO not found or not executable: $PIO_BIN" >&2
  echo "Expected existing PlatformIO from the XIAO project virtual environment." >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python virtual environment not found: $PYTHON_BIN" >&2
  echo "Create it first in $PROJECT_DIR or set PYTHON_BIN=/path/to/python." >&2
  exit 1
fi

echo "== Crop Chop UNO upload + servo diagnostic =="
echo "Project: $PROJECT_DIR"
echo "UNO port: $PORT"
echo "Servo IDs: $SERVO_IDS"
echo "Servo baud scan: $SERVO_BAUDS"
echo

cd "$PROJECT_DIR"

echo "== Uploading UNO firmware =="
PLATFORMIO_CORE_DIR="$PLATFORMIO_CORE_DIR" "$PIO_BIN" run --target upload --upload-port "$PORT"

echo
echo "== Waiting for UNO to reconnect =="
for _ in {1..20}; do
  if [[ -e "$PORT" ]]; then
    break
  fi
  sleep 0.5
done

if [[ ! -e "$PORT" ]]; then
  echo "UNO port did not reappear: $PORT" >&2
  echo "Check the Arduino USB cable and run: ls /dev/ttyUSB* /dev/ttyACM*" >&2
  exit 1
fi

sleep 2

echo
echo "== Running servo-bus diagnostic =="
MPLCONFIGDIR=/tmp "$PYTHON_BIN" pc_tools/servo_bus_diagnostic.py \
  --port "$PORT" \
  --servo-ids "$SERVO_IDS" \
  --servo-bauds "$SERVO_BAUDS" \
  --scan-max-id "$SCAN_MAX_ID" \
  --position-a "$POSITION_A" \
  --position-b "$POSITION_B" \
  --speed "$SPEED" \
  --cycles "$CYCLES" \
  --log-csv "$LOG_CSV"

echo
echo "== Complete =="
echo "Diagnostic CSV: $LOG_CSV"
