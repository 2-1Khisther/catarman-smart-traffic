"""Step 1 - Camera test.

Checks that the phone (DroidCam / Iriun over USB) is readable by OpenCV,
and prints resolution + FPS. Press q in the camera window to quit.

Run:  python tools/camera_test.py            (uses CAMERA_INDEX from .env, default 1)
      python tools/camera_test.py --index 0
"""
import argparse
import os
import sys
import time

import cv2
from dotenv import load_dotenv

load_dotenv()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=int, default=int(os.getenv("CAMERA_INDEX", 1)))
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
    cap = cv2.VideoCapture(args.index, backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        print(f"Camera {args.index} did not open. Try --index 0, 1 or 2, "
              "and check the DroidCam client says 'Connected'.")
        return

    n, t0 = 0, time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            print("No frame. Wrong index, or the camera is busy in another app.")
            break
        n += 1
        if n % 30 == 0:
            fps = n / (time.time() - t0)
            print(f"{frame.shape[1]}x{frame.shape[0]}  {fps:.1f} FPS")

        # Crosshair to help centre the phone over the intersection
        h, w = frame.shape[:2]
        cv2.line(frame, (w // 2, 0), (w // 2, h), (0, 255, 255), 1)
        cv2.line(frame, (0, h // 2), (w, h // 2), (0, 255, 255), 1)
        cv2.imshow("camera_test (q to quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    if n:
        print(f"\nRESULT: {frame.shape[1]}x{frame.shape[0]}, "
              f"{n / (time.time() - t0):.1f} FPS average over {n} frames")


if __name__ == "__main__":
    main()
