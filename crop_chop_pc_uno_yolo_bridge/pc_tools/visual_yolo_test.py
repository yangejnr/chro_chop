#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path

import cv2
from ultralytics import YOLO


def parse_args():
    parser = argparse.ArgumentParser(description="Display live YOLO detections before using the UNO bridge.")
    parser.add_argument("--source", default="0", help="OpenCV source: webcam index, video file, or stream URL.")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--save-jsonl", type=Path)
    parser.add_argument("--save-video", type=Path)
    return parser.parse_args()


def open_source(source):
    if source.isdigit():
        return cv2.VideoCapture(int(source))
    return cv2.VideoCapture(source)


def best_detection(result):
    if result.boxes is None or len(result.boxes) == 0:
        return None
    box = max(result.boxes, key=lambda candidate: float(candidate.conf[0]))
    class_id = int(box.cls[0])
    return {
        "label": str(result.names[class_id]),
        "confidence": float(box.conf[0]),
        "xyxy": [float(value) for value in box.xyxy[0].tolist()],
    }


def draw_status(frame, text, colour):
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 54), (0, 0, 0), -1)
    cv2.putText(frame, text, (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, colour, 2, cv2.LINE_AA)


def main():
    args = parse_args()
    model = YOLO(args.model)
    capture = open_source(args.source)
    if not capture.isOpened():
        raise SystemExit(f"Could not open video source: {args.source}")

    json_log = None
    if args.save_jsonl:
        args.save_jsonl.parent.mkdir(parents=True, exist_ok=True)
        json_log = args.save_jsonl.open("w", encoding="utf-8")

    writer = None
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
            detection = best_detection(result)
            frames += 1
            elapsed = time.monotonic() - started
            fps = frames / elapsed if elapsed > 0 else 0.0

            if detection:
                status = f"DETECTED {detection['label']} {detection['confidence']:.2f} | FPS {fps:.1f}"
                colour = (0, 255, 255)
            else:
                status = f"NO DETECTION | SAFE would remain active | FPS {fps:.1f}"
                colour = (0, 255, 0)
            draw_status(annotated, status, colour)

            if json_log:
                json_log.write(json.dumps({
                    "timestamp": time.time(),
                    "frame": frames,
                    "fps": fps,
                    "best_detection": detection,
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

            cv2.imshow("Crop Chop Visual YOLO Test", annotated)
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
        cv2.destroyAllWindows()

    elapsed = time.monotonic() - started
    print(f"Processed {frames} frames in {elapsed:.2f} s ({frames / elapsed if elapsed else 0:.2f} FPS).")


if __name__ == "__main__":
    main()
