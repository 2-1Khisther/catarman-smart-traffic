"""Camera health: is the lens clear, blurry/wet, or covered?

Bad news is reported immediately; going back to OK needs `recover_seconds`
of continuous good frames, so the controller doesn't flap between levels.
"""
import cv2
import numpy as np

OK, DEGRADED, OCCLUDED = "OK", "DEGRADED", "OCCLUDED"
_RANK = {OK: 0, DEGRADED: 1, OCCLUDED: 2}


def frame_metrics(frame):
    """Return (brightness 0-255, sharpness = Laplacian variance) on a small grey copy."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    small = cv2.resize(gray, (320, int(320 * gray.shape[0] / gray.shape[1])))
    return float(small.mean()), float(cv2.Laplacian(small, cv2.CV_64F).var())


def classify(brightness, sharpness, confs, cfg):
    """Raw status for one frame. confs = detection confidences (empty road is fine)."""
    if brightness < cfg["occluded_brightness_max"] or sharpness < cfg["occluded_blur_max"]:
        return OCCLUDED
    if sharpness < cfg["degraded_blur_min"]:
        return DEGRADED
    if len(confs) and float(np.mean(confs)) < cfg["degraded_conf_min"]:
        return DEGRADED
    return OK


class HealthMonitor:
    def __init__(self, cfg):
        self.cfg = cfg
        self.status = OK
        self._good_since = None

    def update(self, raw, now):
        if _RANK[raw] >= _RANK[self.status]:
            if raw != OK:
                self.status = raw                 # worse (or same): report right away
            self._good_since = None
        else:
            # Better than current: wait recover_seconds before relaxing
            if self._good_since is None:
                self._good_since = now
            elif now - self._good_since >= self.cfg["recover_seconds"]:
                self.status = raw
                self._good_since = None
        return self.status
