"""Load / save the regions of interest marked with tools/roi_tool.py.

rois.json stores points as fractions of the frame (0..1), so it works at any resolution:
{
  "frame_size": [1280, 720],
  "approaches": {
    "N": {"queue": [[x, y], ...], "stopline": [[x1, y1], [x2, y2]]},
    "E": ..., "S": ..., "W": ...
  }
}
"""
import json

from .geometry import polygon_centroid, side

APPROACHES = ("N", "E", "S", "W")


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    missing = [a for a in APPROACHES if a not in data.get("approaches", {})]
    if missing:
        raise ValueError(f"{path} is missing approaches {missing}. Run tools/roi_tool.py again.")
    return data


def save(path, approaches, frame_size):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"frame_size": list(frame_size), "approaches": approaches}, f, indent=2)


class RoiSet:
    """ROIs converted to pixels for one frame size, ready for the vision loop."""

    def __init__(self, data, width, height, crop_margin=0.08):
        self.width, self.height = width, height
        self.approaches = {}
        all_pts = []
        for name in APPROACHES:
            a = data["approaches"][name]
            queue = [(x * width, y * height) for x, y in a["queue"]]
            p, q = [(x * width, y * height) for x, y in a["stopline"]]
            # The queue side is wherever the middle of the queue polygon sits.
            q_side = side(polygon_centroid(queue), p, q) or 1
            self.approaches[name] = {"queue": queue, "stopline": (p, q), "queue_side": q_side}
            all_pts += queue + [p, q]
        self.crop = self._square_crop(all_pts, crop_margin)

    def _square_crop(self, pts, margin):
        """Square box around all marked points, so YOLO only looks at the intersection."""
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + margin * self.width
        x1, y1 = max(0, int(cx - half)), max(0, int(cy - half))
        x2, y2 = min(self.width, int(cx + half)), min(self.height, int(cy + half))
        return x1, y1, x2, y2
