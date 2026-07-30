#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path

import cv2
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="Run YOLOv8 inference on the XIAO ESP32S3 Sense MJPEG stream.")
    parser.add_argument("--source", default="http://192.168.4.1/stream", help="Camera stream URL or local video source.")
    parser.add_argument("--model", default="yolov8n.pt", help="YOLOv8 model path/name. Use nano on Pi 4B first.")
    parser.add_argument("--imgsz", type=int, default=320, help="Inference image size. 320 is conservative for Pi 4B.")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds to run. 0 means until interrupted.")
    parser.add_argument("--no-display", action="store_true", help="Disable GUI display for SSH/headless runs.")
    parser.add_argument("--save-video", type=Path, help="Optional annotated MP4 output path.")
    parser.add_argument("--save-json", type=Path, help="Optional JSONL detection log path.")
    return parser.parse_args()


def main():
    args = parse_args()
    model = YOLO(args.model)
    capture = cv2.VideoCapture(args.source)
    if not capture.isOpened():
        raise SystemExit(f"Could not open video source: {args.source}")

    writer = None
    json_log = None
    if args.save_json:
        args.save_json.parent.mkdir(parents=True, exist_ok=True)
        json_log = args.save_json.open("w", encoding="utf-8")

    started = time.monotonic()
    frames = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                time.sleep(0.05)
                continue

            result = model.predict(frame, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
            annotated = result.plot()
            frames += 1
            elapsed = time.monotonic() - started
            fps = frames / elapsed if elapsed > 0 else 0.0

            detections = []
            for box in result.boxes:
                class_id = int(box.cls[0])
                detections.append({
                    "class_id": class_id,
                    "class_name": result.names[class_id],
                    "confidence": float(box.conf[0]),
                    "xyxy": [float(value) for value in box.xyxy[0].tolist()],
                })

            if json_log:
                json_log.write(json.dumps({
                    "timestamp": time.time(),
                    "frame": frames,
                    "fps": fps,
                    "detections": detections,
                }) + "\n")
                json_log.flush()

            if args.save_video and writer is None:
                args.save_video.parent.mkdir(parents=True, exist_ok=True)
                height, width = annotated.shape[:2]
                writer = cv2.VideoWriter(
                    str(args.save_video),
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    10.0,
                    (width, height),
                )
            if writer:
                writer.write(annotated)

            if not args.no_display:
                cv2.imshow("Crop Chop YOLOv8 XIAO Stream", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if args.duration and elapsed >= args.duration:
                break
    finally:
        capture.release()
        if writer:
            writer.release()
        if json_log:
            json_log.close()
        if not args.no_display:
            cv2.destroyAllWindows()

    elapsed = time.monotonic() - started
    print(f"Processed {frames} frames in {elapsed:.2f} s ({frames / elapsed if elapsed else 0:.2f} FPS).")


if __name__ == "__main__":
    main()
