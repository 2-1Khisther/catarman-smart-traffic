"""ROI tool: mark the 4 approach roads and their stop lines on the camera view.

How to use:
  1. Point the camera at the intersection (diorama, or a taped 60x60 cm square for now).
  2. Run:  python tools/roi_tool.py
  3. Press SPACE to freeze the picture.
  4. For each road N, E, S, W:
       - LEFT-CLICK the corners of the waiting area (the lane where cars queue
         BEFORE the stop line), then press ENTER.
       - LEFT-CLICK the two ends of that road's stop line (it moves on automatically).
  5. Saved to rois.json (+ rois_preview.jpg). Redo it whenever the camera moves.

Keys: SPACE freeze/unfreeze · ENTER finish area · U undo point · R redo this road · ESC quit
Tip: mark the RIGHT-hand lane only (traffic keeps right).

With a recorded clip instead of the camera:  python tools/roi_tool.py --source clip.mp4
"""
import argparse
import os
import sys

import cv2
import yaml
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
from vision import rois  # noqa: E402

load_dotenv()
CFG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), encoding="utf-8"))
COLORS = {"N": (0, 200, 255), "E": (255, 160, 0), "S": (0, 255, 120), "W": (255, 80, 200)}
NAMES = {"N": "NORTH", "E": "EAST", "S": "SOUTH", "W": "WEST"}
ORDER = list(rois.APPROACHES)


def open_source(src):
    if src.isdigit():
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
        cap = cv2.VideoCapture(int(src), backend)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CFG["camera"]["width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CFG["camera"]["height"])
    else:
        cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        sys.exit(f"Could not open source {src}. Check CAMERA_INDEX in .env or the file path.")
    return cap


class Marker:
    """Keeps track of which road / step we are on."""

    def __init__(self):
        self.done = {}        # name -> {"queue": [...], "stopline": [...]} in 0..1 coords
        self.pending_queue = None
        self.points = []      # pixel clicks for the current step

    @property
    def index(self):
        return len(self.done)

    @property
    def finished(self):
        return self.index == 4

    @property
    def stage(self):
        return "stopline" if self.pending_queue else "queue"

    def click(self, x, y, w, h):
        if self.finished:
            return
        self.points.append((x, y))
        if self.stage == "stopline" and len(self.points) == 2:
            name = ORDER[self.index]
            self.done[name] = {"queue": self.pending_queue,
                               "stopline": [[px / w, py / h] for px, py in self.points]}
            self.pending_queue, self.points = None, []
            print(f"{NAMES[name]} saved.")

    def enter(self, w, h):
        if self.finished or self.stage != "queue":
            return
        if len(self.points) < 3:
            print("Need at least 3 corners for the waiting area.")
            return
        self.pending_queue = [[px / w, py / h] for px, py in self.points]
        self.points = []

    def undo(self):
        if self.points:
            self.points.pop()

    def redo_road(self):
        self.pending_queue, self.points = None, []


def draw(view, m):
    h, w = view.shape[:2]
    for name, a in m.done.items():
        q = [(int(x * w), int(y * h)) for x, y in a["queue"]]
        s = [(int(x * w), int(y * h)) for x, y in a["stopline"]]
        for i in range(len(q)):
            cv2.line(view, q[i], q[(i + 1) % len(q)], COLORS[name], 2)
        cv2.line(view, s[0], s[1], (255, 255, 255), 3)
        cv2.putText(view, name, q[0], cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLORS[name], 2)
    if m.finished:
        return
    cur = ORDER[m.index]
    if m.pending_queue:
        q = [(int(x * w), int(y * h)) for x, y in m.pending_queue]
        for i in range(len(q)):
            cv2.line(view, q[i], q[(i + 1) % len(q)], COLORS[cur], 2)
    for i, p in enumerate(m.points):
        cv2.circle(view, p, 4, COLORS[cur], -1)
        if i:
            cv2.line(view, m.points[i - 1], p, COLORS[cur] if m.stage == "queue" else (255, 255, 255), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.getenv("CAMERA_INDEX", "1"),
                    help="camera index (e.g. 1) or a video file")
    ap.add_argument("--out", default=os.path.join(ROOT, CFG["rois"]["file"]))
    args = ap.parse_args()

    cap = open_source(str(args.source))
    m = Marker()
    frozen = None
    saved = False
    size = [0, 0]

    def on_click(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN and frozen is not None:
            m.click(x, y, size[0], size[1])

    win = "ROI tool"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_click)

    while True:
        if frozen is None:
            ok, frame = cap.read()
            if not ok:
                print("No frame from source.")
                break
        else:
            frame = frozen
        h, w = frame.shape[:2]
        size[:] = [w, h]
        view = frame.copy()
        draw(view, m)

        if frozen is None:
            msg = "Press SPACE to freeze the picture"
        elif m.finished:
            msg = "All 4 roads saved to rois.json. Press ESC to close."
        elif m.stage == "queue":
            msg = f"{NAMES[ORDER[m.index]]}: click corners of the waiting lane, then ENTER ({len(m.points)} pts)"
        else:
            msg = f"{NAMES[ORDER[m.index]]}: click the 2 ends of the STOP LINE"

        if m.finished and not saved:
            rois.save(args.out, m.done, (w, h))
            cv2.imwrite(os.path.splitext(args.out)[0] + "_preview.jpg", view)
            saved = True
            print(f"Saved {args.out}")

        cv2.rectangle(view, (0, 0), (w, 34), (0, 0, 0), -1)
        cv2.putText(view, msg, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.imshow(win, view)

        key = cv2.waitKey(15) & 0xFF
        if key == 27:                                   # ESC
            break
        if key == 32:                                   # SPACE
            frozen = None if frozen is not None else frame.copy()
        elif key in (13, 10) and frozen is not None:    # ENTER
            m.enter(w, h)
        elif key in (ord("u"), ord("U")):
            m.undo()
        elif key in (ord("r"), ord("R")):
            m.redo_road()

    if not saved:
        print("Not saved: all 4 roads must be marked.")
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
