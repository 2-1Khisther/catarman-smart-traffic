"""Squad B vision node: camera -> YOLOv8n -> tracking -> counts -> MQTT.

Publishes (see docs/mqtt-contract/):
  vision/heartbeat  2 Hz   fps, confidence, camera status (OK / DEGRADED / OCCLUDED)
  vision/density    1 Hz   counts + PCU per road and per phase (NS, EW)
  vision/violation  event  vehicle crossed the stop line on red (anonymized crop)
  vision/status     retained ONLINE, Last Will OFFLINE
Listens to:
  controller/state  from Squad A's ESP32, to know which roads are red

Run (from edge_vision):
  python vision_node.py                      camera from .env, window on
  python vision_node.py --source clip.mp4    a recorded clip (loops)
  python vision_node.py --no-window          headless
Press q in the window to stop.

Works without the broker too (offline-first): everything is also logged to
buffer/vision_log.db, and MQTT reconnects on its own when the broker is back.
"""
import argparse
import json
import os
import sqlite3
import sys
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone

import cv2
import numpy as np
import paho.mqtt.client as mqtt
import yaml
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from vision import health, logic, rois  # noqa: E402
from vision.geometry import crossed_stop_line, point_in_polygon  # noqa: E402

load_dotenv(os.path.join(ROOT, "..", ".env"))
load_dotenv()
CFG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml"), encoding="utf-8"))
INT = os.getenv("INTERSECTION_ID", "int01")
BASE = f"catarman/{INT}"
CLASS_COLORS = {"car": (255, 200, 0), "motorcycle": (0, 220, 255), "tricycle": (200, 0, 255)}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- camera
class Camera:
    """Live camera in a background thread (always the newest frame), or a video file.

    If a live camera stops giving frames (USB pulled), it keeps trying to reopen.
    """

    def __init__(self, source, width, height):
        self.source = source
        self.live = source.isdigit()
        self.width, self.height = width, height
        self.frame, self.frame_id = None, 0
        self.ok = False
        self.lock = threading.Lock()
        self.cap = self._open()
        if self.live:
            threading.Thread(target=self._reader, daemon=True).start()

    def _open(self):
        if self.live:
            backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
            cap = cv2.VideoCapture(int(self.source), backend)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            cap = cv2.VideoCapture(self.source)
        return cap

    def _reader(self):
        fails = 0
        while True:
            ok, f = self.cap.read() if self.cap.isOpened() else (False, None)
            if ok:
                fails = 0
                with self.lock:
                    self.frame, self.ok = f, True
                    self.frame_id += 1
            else:
                fails += 1
                if fails >= 10:
                    with self.lock:
                        self.ok = False
                    self.cap.release()
                    time.sleep(2)
                    print("Camera lost - trying to reopen...")
                    self.cap = self._open()
                    fails = 0
                else:
                    time.sleep(0.05)

    def read(self):
        """Returns (frame, frame_id) or (None, id) when the camera is down."""
        if self.live:
            with self.lock:
                return (self.frame if self.ok else None), self.frame_id
        ok, f = self.cap.read()
        if not ok:                                   # end of clip: loop it
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, f = self.cap.read()
        self.frame_id += 1
        return (f if ok else None), self.frame_id


# --------------------------------------------------------------------------- local log
class LocalLog:
    """Every published message also goes to SQLite, so nothing is lost if MQTT is down.
    B4 adds the replay job on top of this table (sent = 0 rows)."""

    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY, ts TEXT, "
                        "topic TEXT, payload TEXT, sent INTEGER)")
        self.db.commit()
        self.last_commit = time.time()

    def add(self, topic, payload, sent):
        self.db.execute("INSERT INTO outbox (ts, topic, payload, sent) VALUES (?,?,?,?)",
                        (utc_now(), topic, payload, int(sent)))
        if time.time() - self.last_commit > 2:
            self.db.commit()
            self.last_commit = time.time()


# --------------------------------------------------------------------------- MQTT
class Bus:
    def __init__(self, log):
        self.log = log
        self.state = {}
        self.connected = False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"squadb-vision-{INT}")
        self.client.will_set(f"{BASE}/vision/status", "OFFLINE", qos=1, retain=True)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(1, 5)
        host, port = os.getenv("MQTT_HOST", "127.0.0.1"), int(os.getenv("MQTT_PORT", 1883))
        print(f"MQTT broker: {host}:{port}")
        self.client.connect_async(host, port, keepalive=10)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = not reason_code.is_failure
        if self.connected:
            print("MQTT connected")
            client.publish(f"{BASE}/vision/status", "ONLINE", qos=1, retain=True)
            client.subscribe(f"{BASE}/controller/state")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        print("MQTT disconnected - will keep retrying")

    def _on_message(self, client, userdata, msg):
        try:
            s = json.loads(msg.payload)
            s["_rx"] = time.time()
            self.state = s
        except (ValueError, TypeError):
            pass

    def publish(self, sub, obj, qos=0):
        topic, payload = f"{BASE}/vision/{sub}", json.dumps(obj)
        sent = False
        if self.connected:
            sent = self.client.publish(topic, payload, qos=qos).rc == mqtt.MQTT_ERR_SUCCESS
        if sub != "heartbeat":                    # heartbeats are too frequent to store
            self.log.add(topic, payload, sent)

    def close(self):
        if self.connected:
            self.client.publish(f"{BASE}/vision/status", "OFFLINE", qos=1, retain=True).wait_for_publish(2)
        self.client.loop_stop()
        self.client.disconnect()


# --------------------------------------------------------------------------- helpers
def save_crop(frame, box, vcfg):
    """Shrunk + blurred crop of just the vehicle (RA 10173: no readable numbers)."""
    x1, y1, x2, y2 = [int(v) for v in box]
    crop = frame[max(0, y1):y2, max(0, x1):x2]
    if crop.size == 0:
        return None
    scale = vcfg["crop_max_px"] / max(crop.shape[:2])
    if scale < 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    k = vcfg["crop_blur"] | 1
    crop = cv2.GaussianBlur(crop, (k, k), 0)
    name = f"{uuid.uuid4()}"
    os.makedirs(os.path.join(ROOT, "crops"), exist_ok=True)
    cv2.imwrite(os.path.join(ROOT, "crops", f"{name}.jpg"), crop)
    return name, f"crops/{name}.jpg"


def draw(view, roiset, dets, counts, status, fps, metrics, bus, red_map):
    for name, a in roiset.approaches.items():
        red = red_map.get(name)
        color = (0, 0, 255) if red else (0, 200, 0) if red is False else (160, 160, 160)
        pts = np.array(a["queue"], np.int32)
        cv2.polylines(view, [pts], True, color, 2)
        p, q = a["stopline"]
        cv2.line(view, (int(p[0]), int(p[1])), (int(q[0]), int(q[1])), (255, 255, 255), 2)
        c = counts[name]
        label = f"{name}: T{c['tricycle']} M{c['motorcycle']} C{c['car']}"
        cv2.putText(view, label, (int(pts[0][0]), int(pts[0][1]) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    x1, y1, x2, y2 = roiset.crop
    cv2.rectangle(view, (x1, y1), (x2, y2), (80, 80, 80), 1)
    for d in dets:
        bx = [int(v) for v in d["box"]]
        col = CLASS_COLORS.get(d["cls"], (255, 255, 255))
        cv2.rectangle(view, (bx[0], bx[1]), (bx[2], bx[3]), col, 2)
        cv2.putText(view, f"{d['cls']} {d['tid']}", (bx[0], bx[1] - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
    st_col = {"OK": (0, 200, 0), "DEGRADED": (0, 200, 255), "OCCLUDED": (0, 0, 255)}[status]
    cv2.rectangle(view, (0, 0), (view.shape[1], 30), (0, 0, 0), -1)
    info = (f"{fps:4.1f} FPS | camera {status} | bright {metrics[0]:.0f} sharp {metrics[1]:.0f} | "
            f"MQTT {'ON' if bus.connected else 'OFF'} | ctrl {bus.state.get('phase', '-')} "
            f"{bus.state.get('mode', '')}")
    cv2.putText(view, info, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, st_col, 2)


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.getenv("CAMERA_INDEX", "1"))
    ap.add_argument("--no-window", action="store_true")
    args = ap.parse_args()

    roi_path = os.path.join(ROOT, CFG["rois"]["file"])
    if not os.path.exists(roi_path):
        sys.exit("No rois.json yet. Run:  python tools/roi_tool.py")
    roi_data = rois.load(roi_path)

    from ultralytics import YOLO
    mcfg = CFG["model"]
    model = YOLO(os.path.join(ROOT, mcfg["weights"]) if os.path.exists(os.path.join(ROOT, mcfg["weights"]))
                 else mcfg["weights"])
    class_map = {i: CFG["classes"][n] for i, n in model.names.items() if n in CFG["classes"]}
    if "tricycle" not in class_map.values():
        print("Note: this model has no 'tricycle' class (stock COCO weights). "
              "Tricycles will show as car/motorcycle until the fine-tuned model is used.")

    cam = Camera(str(args.source), CFG["camera"]["width"], CFG["camera"]["height"])
    log = LocalLog(os.path.join(ROOT, "buffer", "vision_log.db"))
    bus = Bus(log)
    monitor = health.HealthMonitor(CFG["health"])
    phases, weights = CFG["phases"], CFG["pcu"]
    vcfg, stale_s = CFG["violations"], CFG["mqtt"]["controller_stale_s"]

    roiset = None
    last_pos, last_seen, violated = {}, {}, set()
    counts = {a: {c: 0 for c in logic.CLASSES} for a in rois.APPROACHES}
    dets, metrics, confs_window = [], (0.0, 0.0), []
    status, fps, seq = health.OCCLUDED, 0.0, 0
    last_id, frame_times = -1, deque()
    next_hb = next_density = time.time()
    hb_period = 1 / CFG["mqtt"]["heartbeat_hz"]
    density_period = 1 / CFG["mqtt"]["density_hz"]
    print("Vision node running. Press q in the window (or Ctrl+C) to stop.")

    try:
        while True:
            now = time.time()
            frame, fid = cam.read()

            if frame is None:                                   # camera down
                status = monitor.update(health.OCCLUDED, now)
                fps = 0.0
                frame_times.clear()
                time.sleep(0.05)
            elif fid != last_id:                                # new frame -> process
                last_id = fid
                h, w = frame.shape[:2]
                if roiset is None or (roiset.width, roiset.height) != (w, h):
                    roiset = rois.RoiSet(roi_data, w, h, CFG["rois"]["crop_margin"])
                x1, y1, x2, y2 = roiset.crop
                res = model.track(frame[y1:y2, x1:x2], persist=True, imgsz=mcfg["imgsz"],
                                  conf=mcfg["conf"], classes=list(class_map), verbose=False,
                                  tracker=mcfg["tracker"])[0]

                dets = []
                b = res.boxes
                if b is not None and len(b):
                    ids = b.id.int().tolist() if b.id is not None else [None] * len(b)
                    for box, cls_i, conf, tid in zip(b.xyxy.tolist(), b.cls.int().tolist(),
                                                     b.conf.tolist(), ids):
                        box = [box[0] + x1, box[1] + y1, box[2] + x1, box[3] + y1]
                        dets.append({"box": box, "cls": class_map[cls_i], "conf": conf, "tid": tid,
                                     "c": ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)})

                # counts per road + stop-line crossings
                counts = {a: {c: 0 for c in logic.CLASSES} for a in rois.APPROACHES}
                red_map = {a: logic.is_red(a, phases, bus.state, now, stale_s) for a in rois.APPROACHES}
                for d in dets:
                    for name, a in roiset.approaches.items():
                        if point_in_polygon(d["c"], a["queue"]):
                            counts[name][d["cls"]] += 1
                        tid = d["tid"]
                        if tid is None or tid in violated or red_map[name] is not True:
                            continue
                        if crossed_stop_line(last_pos.get(tid), d["c"], *a["stopline"], a["queue_side"]):
                            violated.add(tid)
                            saved = save_crop(frame, d["box"], vcfg)
                            if saved:
                                event_id, crop_file = saved
                                bus.publish("violation", {
                                    "event_id": event_id, "ts": utc_now(), "approach": name,
                                    "cls": d["cls"], "centroid": [int(d["c"][0]), int(d["c"][1])],
                                    "bbox": [max(0, int(v)) for v in d["box"]], "crop_file": crop_file},
                                    qos=1)
                                print(f"VIOLATION {name} {d['cls']} (track {tid})")
                for d in dets:
                    if d["tid"] is not None:
                        last_pos[d["tid"]], last_seen[d["tid"]] = d["c"], now
                for tid in [t for t, s in last_seen.items() if now - s > vcfg["track_forget_s"]]:
                    last_seen.pop(tid), last_pos.pop(tid, None), violated.discard(tid)

                # camera health
                metrics = health.frame_metrics(frame)
                confs = [d["conf"] for d in dets]
                confs_window = (confs_window + confs)[-50:]
                status = monitor.update(health.classify(*metrics, confs, CFG["health"]), now)

                # FPS = processed frames in the last 2 seconds
                frame_times.append(time.time())
                while frame_times and frame_times[0] < frame_times[-1] - 2:
                    frame_times.popleft()
                if len(frame_times) > 1:
                    fps = (len(frame_times) - 1) / (frame_times[-1] - frame_times[0])

                if not args.no_window:
                    view = frame.copy()
                    draw(view, roiset, dets, counts, status, fps, metrics, bus, red_map)
                    scale = 960 / view.shape[1]
                    cv2.imshow("Squad B vision (q to quit)", cv2.resize(view, None, fx=scale, fy=scale))
            else:
                time.sleep(0.002)

            if not args.no_window and (cv2.waitKey(1) & 0xFF) == ord("q"):
                break

            # periodic messages
            if now >= next_hb:
                seq += 1
                conf_avg = float(np.mean(confs_window)) if confs_window else 0.0
                bus.publish("heartbeat", {"ts": utc_now(), "seq": seq, "fps": round(fps, 1),
                                          "conf_avg": round(min(max(conf_avg, 0), 1), 3),
                                          "status": status})
                next_hb = now + hb_period
            if now >= next_density:
                bus.publish("density", logic.build_density(utc_now(), seq, counts, weights, phases))
                next_density = now + density_period
    except KeyboardInterrupt:
        pass
    finally:
        log.db.commit()
        bus.close()
        cv2.destroyAllWindows()
        print("Stopped.")


if __name__ == "__main__":
    main()
