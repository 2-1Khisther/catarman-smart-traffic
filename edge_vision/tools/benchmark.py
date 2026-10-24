"""Step 2 - YOLOv8n FPS benchmark on THIS laptop.

Measures pure inference FPS for:
  - PyTorch at imgsz 640 and 416
  - OpenVINO at imgsz 640 and 416 (usually much faster on Intel CPUs)

Uses live camera frames if a camera opens, otherwise a synthetic frame.
Run it twice: once alone, once with Mosquitto + MySQL + Next.js running.

Run:  python tools/benchmark.py
      python tools/benchmark.py --frames 300 --no-openvino
"""
import argparse
import os
import platform
import shutil
import sys
import time

import cv2
import numpy as np
from dotenv import load_dotenv
from ultralytics import YOLO

load_dotenv()
TARGET_FPS = 15


def get_frames(index, count):
    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
    cap = cv2.VideoCapture(index, backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    frames = []
    if cap.isOpened():
        for _ in range(count):
            ok, f = cap.read()
            if not ok:
                break
            frames.append(f)
    cap.release()
    if frames:
        print(f"Using {len(frames)} live camera frames ({frames[0].shape[1]}x{frames[0].shape[0]})")
        return frames
    print("No camera - using a synthetic 1280x720 frame")
    return [np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)]


def bench(model, frames, imgsz, n):
    for i in range(10):                      # warm-up
        model.predict(frames[i % len(frames)], imgsz=imgsz, verbose=False)
    t0 = time.perf_counter()
    for i in range(n):
        model.predict(frames[i % len(frames)], imgsz=imgsz, verbose=False)
    return n / (time.perf_counter() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=int, default=int(os.getenv("CAMERA_INDEX", 1)))
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--no-openvino", action="store_true")
    args = ap.parse_args()

    print(f"Machine: {platform.processor() or platform.machine()} | {platform.system()} {platform.release()}")
    frames = get_frames(args.index, 60)
    results = []

    pt = YOLO("yolov8n.pt")                  # downloads on first run (~6 MB)
    for size in (640, 416, 320):
        fps = bench(pt, frames, size, args.frames)
        results.append(("PyTorch", size, fps))
        print(f"PyTorch  imgsz {size}: {fps:5.1f} FPS")

    if not args.no_openvino:
        for size in (640, 416, 320):
            try:
                # Each size gets its own folder; Windows locks a loaded model's files,
                # so re-exporting into the same folder fails.
                dst = f"yolov8n_{size}_openvino_model"
                if not os.path.isdir(dst):
                    path = YOLO("yolov8n.pt").export(format="openvino", imgsz=size, verbose=False)
                    shutil.move(path, dst)
                ov = YOLO(dst, task="detect")
                fps = bench(ov, frames, size, args.frames)
                results.append(("OpenVINO", size, fps))
                print(f"OpenVINO imgsz {size}: {fps:5.1f} FPS")
                del ov
            except Exception as e:
                print(f"OpenVINO imgsz {size} skipped: {e}")

    print("\n=== Copy this into docs/test-reports/phase0-baseline.md ===")
    print("| Runtime | imgsz | FPS | >= 15? |\n| --- | --- | --- | --- |")
    for rt, size, fps in results:
        print(f"| {rt} | {size} | {fps:.1f} | {'PASS' if fps >= TARGET_FPS else 'FAIL'} |")
    print("\nNote: this is inference only. Tracking, drawing and MQTT add a few ms per frame,"
          "\nso aim for about 20 FPS here to keep 15 FPS in the full pipeline.")


if __name__ == "__main__":
    main()