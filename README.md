# chro_chop

Crop Chop robotics development workspace.

Current project modules:

- `crop_chop_xiao_camera_test`: XIAO ESP32S3 Sense camera firmware and host test tools.
- `crop_chop_pi_yolov8`: Raspberry Pi YOLOv8 setup notes and scripts.
- `crop_chop_pc_uno_yolo_bridge`: PC YOLOv8 to Arduino UNO serial logic bridge.

Current bench-test evidence:

- `crop_chop_pc_uno_yolo_bridge/docs/uno_logic_test_outcome_2026-07-30.md`: Arduino UNO safety-logic upload, serial output, XIAO input monitoring, and idle safe-state LED outcome.
- `crop_chop_pc_uno_yolo_bridge/docs/visual_yolo_test_procedure.md`: Visual YOLO display procedure for confirming what the PC model detects before interpreting UNO `SAFE` or `DANGER` outputs.
- `crop_chop_pc_uno_yolo_bridge/docs/servo_bench_test_procedure.md`: Conservative three-servo bench-test procedure for scan/status and bounded movement commands.
- `crop_chop_pc_uno_yolo_bridge/docs/person_stop_servo_sequence_procedure.md`: Sequential servo movement procedure that stops and logs data when YOLO detects `person`.
