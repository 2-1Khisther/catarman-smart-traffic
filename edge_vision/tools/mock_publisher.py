"""Step 3 - Mock vision publisher.

Publishes fake heartbeat, density and status messages that follow the MQTT
contract, so Squad A (ESP32) and Squad C (dashboard) can build against
Squad B before the real model is ready.

Needs Mosquitto running. Watch the output with:
  mosquitto_sub -h 127.0.0.1 -t "catarman/#" -v

Run:  python tools/mock_publisher.py
      python tools/mock_publisher.py --occlude-after 20   (status goes OCCLUDED after 20 s)
"""
import argparse
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import yaml
from dotenv import load_dotenv

load_dotenv()
HERE = os.path.dirname(os.path.abspath(__file__))
CFG = yaml.safe_load(open(os.path.join(HERE, "..", "config.yaml"), encoding="utf-8"))
PCU = CFG["pcu"]
INT = os.getenv("INTERSECTION_ID", "int01")
BASE = f"catarman/{INT}/vision"


def now():
    return datetime.now(timezone.utc).isoformat()


def density(seq):
    approaches = {}
    for a in "NESW":
        counts = {c: random.randint(0, 4) for c in ("tricycle", "motorcycle", "car")}
        approaches[a] = {"counts": counts, "pcu": round(sum(PCU[c] * n for c, n in counts.items()), 2)}
    phases = {p: round(sum(approaches[a]["pcu"] for a in members), 2)
              for p, members in CFG["phases"].items()}
    return {"ts": now(), "seq": seq, "approaches": approaches, "phases": phases}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--occlude-after", type=float, default=0, help="seconds; 0 = never")
    ap.add_argument("--violation-every", type=float, default=15)
    args = ap.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="squadb-mock")
    client.will_set(f"{BASE}/status", "OFFLINE", qos=1, retain=True)   # Last Will
    client.connect(os.getenv("MQTT_HOST", "127.0.0.1"), int(os.getenv("MQTT_PORT", 1883)))
    client.loop_start()
    client.publish(f"{BASE}/status", "ONLINE", qos=1, retain=True)

    hb_period = 1 / CFG["mqtt"]["heartbeat_hz"]
    start = time.time()
    seq = 0
    next_density = next_violation = start
    print(f"Publishing to {BASE}/... (Ctrl+C to stop)")
    try:
        while True:
            t = time.time()
            status = "OCCLUDED" if args.occlude_after and t - start > args.occlude_after else "OK"
            seq += 1
            hb = {"ts": now(), "seq": seq, "fps": round(random.uniform(15, 20), 1),
                  "conf_avg": round(random.uniform(0.6, 0.9), 2) if status == "OK" else 0.05,
                  "status": status}
            client.publish(f"{BASE}/heartbeat", json.dumps(hb), qos=0)

            if t >= next_density:
                client.publish(f"{BASE}/density", json.dumps(density(seq)), qos=0)
                next_density = t + 1 / CFG["mqtt"]["density_hz"]

            if args.violation_every and t >= next_violation and t > start:
                v = {"event_id": str(uuid.uuid4()), "ts": now(), "approach": random.choice("NESW"),
                     "cls": random.choice(["tricycle", "motorcycle", "car"]),
                     "centroid": [random.randint(0, 1280), random.randint(0, 720)],
                     "bbox": [100, 100, 160, 140], "crop_file": "crops/mock.jpg"}
                client.publish(f"{BASE}/violation", json.dumps(v), qos=1)
                print("violation", v["approach"], v["cls"])
            if t >= next_violation:
                next_violation = t + args.violation_every

            time.sleep(hb_period)
    except KeyboardInterrupt:
        client.publish(f"{BASE}/status", "OFFLINE", qos=1, retain=True)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
