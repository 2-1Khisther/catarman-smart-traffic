# Squad B Implementation & Testing Plan: Edge Vision & AI

Oct 21, 2026 · Khristher

Squad B owns everything between the camera lens and a validated, published traffic message. Squad A owns what the ESP32 does with that message; Squad C owns how it is displayed.

## Stack reconciliation (settle this week)

The brief specifies a Python edge server, a plain HTML/Tailwind/JS dashboard and SQLite/CSV storage. The midterm requires Next.js, Tailwind, Node/Express and MySQL. This plan assumes the following reconciliation, to be confirmed with the adviser and the Squad A and C leads:

- **Keep the Python vision node.** YOLOv8 is Python-native; nobody expects inference in Node.
- **Add Express and MySQL as the system-of-record layer** behind the MQTT broker.
- **Keep SQLite/CSV as the vision node's offline buffer.** This still satisfies the brief's 100% offline-retention KPI.
- **Update the brief's Technology Preferences section** so the panel does not see two architectures.

## 1. Squad Scope & Core Responsibilities

Squad B owns five MVP features, one alone and four shared.

| MVP feature | Squad B's share |
| --- | --- |
| Edge mixed-traffic profiling | Sole owner: camera ingest, YOLOv8n detection, classification, per-approach counting |
| Dynamic green-phase allocation (A & B) | Produce the per-approach PCU congestion score; Squad A owns the timing logic that consumes it |
| Offline-first telemetry bridge (A & B) | Vision-side MQTT publisher, the message schema (co-owned), laptop side of the USB Serial fallback |
| Optical occlusion handover (A & B) | Detect that the camera is degraded and signal it (heartbeat + status); Squad A owns switching to the HC-SR04 |
| Red-light snapshot log (B & C) | Breach detection, anonymized crops, violation records; Squad C displays them |

**Midterm stack split.** Squad B owns the Python vision service, the camera rig (clamp stand, phone, phone USB cable), and the design of the vision MySQL tables and MQTT payloads. Per Squad A's diorama guide, Jim Ivan S. Benzon (Squad A) owns the Node MQTT-to-MySQL ingest, Squad C owns the Next.js dashboard and Express API, and Squad A owns firmware. Still to confirm with the B and C leads: which machine hosts the MQTT broker (the edge laptop is the default).

| Member | Role | Owns |
| --- | --- | --- |
| Khristher (lead) | Integration | MQTT contract, camera rig, cross-squad coordination, test coordination, demo runbook |
| B2 | Model & dataset | Toy-vehicle sourcing with Squad A, image capture, labeling, fine-tuning, accuracy reports |
| B3 | Pipeline logic | ROIs, tracking, PCU scoring, violation detection, health/occlusion monitor |
| B4 | Data & backend | Vision table spec for Squad A's ingest, offline buffer and replay, MJPEG stream for the dashboard, database validation tests |

## 2. Assigned Technical Stack & Deliverables

**Hardware.** Squad B owns the camera rig in Squad A's diorama: a clamp stand with a horizontal arm clamped to the table outside the board, the phone about 55 cm above the board centre, and a ≈2 m data-capable phone USB cable taped along the arm (many charge-only cables fail silently). Squad A provides the 60 × 60 cm board, the 2.4 GHz pocket Wi-Fi for laptop–ESP32 traffic, and the HDMI cable. The edge laptop is shared by all three squads.

### Diorama facts that shape the vision pipeline

| Diorama fact (Squad A guide) | Effect on Squad B |
| --- | --- |
| Two crossing 15 cm roads, keep-right, two lanes each | Four approach ROIs, each on the right-hand lane |
| White stop lines 9 cm from centre on black cartolina | Reference marks for stop-line segments and ROI calibration |
| Opposite approaches share a phase (N = S, E = W) | PCU summed per phase; violations checked per phase |
| ≈8 toy vehicles, 1:64 scale (car ≈7 × 3 cm) | Need ≥3 per class; a 1:64 motorcycle is ≈3 cm, so keep inference at imgsz 640 |
| Black road surface | Avoid dark toys; they vanish against it |
| Backup sensors only on North (HC-SR04) and East (IR) | Occlusion handover works per phase, not per approach |
| Conflict-monitor fault forces Flashing Amber, separate from flood | Suppress violations in any flashing-amber state; needs a fault flag |
| One laptop runs the broker, MySQL, ingest, YOLOv8 and Next.js | Benchmark FPS with all services running |
| Harness wires run under the board | Ask Squad A to keep jumpers and glue off the road surface |
| Phone at ≈55 cm with a ≈60° view | Short side of a landscape frame may clip the approaches; verify in Phase 0 |

| Deliverable | Location | Tools |
| --- | --- | --- |
| Vision service | `/edge_vision` | Python, Ultralytics YOLOv8n (exported to OpenVINO or ONNX for CPU speed), ByteTrack, OpenCV, paho-mqtt |
| Camera ingest | `/edge_vision/ingest` | DroidCam over USB or scrcpy, read as an OpenCV capture device |
| Custom model weights + dataset | `/edge_vision/models`, `/docs/dataset` | Roboflow, CVAT or Label Studio for labeling; Google Colab GPU for training |
| Vision MySQL schema + EER diagram | `/backend/db` | MySQL Workbench; Squad A's Node ingest writes the rows (the EER diagram doubles as a midterm artifact) |
| Camera rig | Diorama (Squad B owns) | Clamp stand, phone, 2 m USB cable; mount position marked on the table so it always returns to the same spot |
| Live annotated video stream | Endpoint for Squad C | MJPEG over HTTP from the Python service, embedded in Next.js with an `<img>` tag |
| Test suite + reports | `/edge_vision/tests`, `/docs/test-reports` | pytest, jsonschema, latency logging scripts |

### MQTT contract (lock with Squads A and C in Week 1)

```
catarman/int01/vision/heartbeat   QoS0, 2 Hz   {ts, seq, fps, conf_avg, status: "OK"|"DEGRADED"|"OCCLUDED"}
catarman/int01/vision/density     QoS0, 1 Hz   {ts, seq, approaches: {N:{counts:{tricycle,motorcycle,car}, pcu}, E:..., S:..., W:...}, phases: {NS:pcu, EW:pcu}}
catarman/int01/vision/violation   QoS1         {event_id, ts, approach, cls, centroid, bbox, crop_file}
catarman/int01/vision/status      retained, also set as Last Will = "OFFLINE"
catarman/int01/controller/state   (Squad A publishes) {ts, phase: "NS"|"EW", mode: "L1".."L4", fault, remaining_s, uptime_ms}
catarman/int01/latency/ping|pong  {seq, t_send}   (test harness only)
```

- **Heartbeat rate.** The brief's "3 missing heartbeats in under 3 seconds" requires at least 1 Hz; 2 Hz gives margin.
- **Last Will message.** A crashed vision process shows as OFFLINE immediately, not after the heartbeat timeout.
- **Controller state subscription.** Violation logic must know which approaches are red, so Squad B subscribes to Squad A's state topic. Ask Squad A to include the fault flag, since the conflict monitor forces Flashing Amber separately from flood mode.

**PCU weights.** Keep them in a config file, not code. The brief fixes only "1 car ≈ 2 tricycles" (car = 1.0, tricycle = 0.5). Motorcycle and van/jeepney weights need adviser sign-off and a cited source; the panel's EE professor may ask.

## 3. Step-by-Step Implementation Roadmap

The roadmap follows the brief's 8-week sprint ending mid-December, with October 21 in Week 1. If the midterm submission falls before mid-November, compress Phases 1–3 and make the Phase 3 checkpoint the midterm demo.

**Open question:** exact midterm submission date.

### Phase 0: Contracts & baseline (Oct 21–25)

1. Set up the monorepo with branch-per-feature workflow and a shared `.env.example` (broker IP, MySQL credentials, camera index).
2. Meet the Squad A and C leads: confirm ownership (Squad A's ingest, Squad C's Express API), the broker host and the MQTT schema; commit the schema as JSON Schema files both sides validate against.
3. Get the tethered phone camera readable in OpenCV on the actual demo laptop; record latency and resolution. Then hold the phone 55 cm over a 60 × 60 cm sheet and check all four approaches fit in frame; if the short side clips them, raise it to 65–70 cm before Squad A fixes the stand.
4. Benchmark stock YOLOv8n on that laptop at imgsz 640 and 416, in PyTorch and OpenVINO/ONNX. Run it again with the broker, MySQL and Next.js running, since one laptop hosts everything. This shows whether 15 FPS is realistic.
5. Settle the toy vehicles with Squad A. Their list has ≈8 toys (tricycles, motorcycles, cars at 1:64); ask for at least 3 per class in bright colours, bought this week or next so dataset capture can start. Drop the van class unless vans are added.

### Phase 1: Dataset & pipeline skeleton (Oct 26–Nov 1)

1. **B2:** Capture 200+ images per class from the overhead mount across varied lighting, positions, partial occlusions and touching clusters. Stock COCO weights have no tricycle class and handle toys poorly, so a custom fine-tune is necessary. Keep a held-out test set.
2. **B3:** Build the frame loop (capture → infer → track) with stock weights as a placeholder; publish mock density messages.
3. **B4:** Design the MySQL schema in Workbench: `vehicle_counts` (hourly per approach per class), `violations`, `vision_health`. Make `event_id` a unique key so replays never duplicate rows. Hand the spec to Jim Ivan (Squad A) for the ingest.
4. **Khristher:** Stand up Mosquitto on the laptop; use `mosquitto_sub` as a stand-in ESP32 so Squad B is not blocked on firmware.

### Phase 2: Core logic (Nov 2–8)

1. **Fine-tune.** Train YOLOv8n on Colab, export to OpenVINO/ONNX, run a first accuracy report.
2. **Counting.** Draw a per-approach queue ROI polygon for density/PCU, plus a stop-line segment for crossing counts and violations. Use the white stop lines (9 cm from centre) as reference marks, and sum PCU per phase (N + S, E + W).
3. **Violations.** A violation is a tracked ID crossing the stop line while its phase is red; each ID counts once and amber is excluded. Save only the bounding-box crop, downscaled and blurred, so tricycle body numbers are unreadable (this is what makes the RA 10173 claim defensible).
4. **Health monitor.** Flag degradation from mean detection confidence, frame blur (Laplacian variance) and brightness. Publish `DEGRADED`/`OCCLUDED` immediately; require about 5 seconds of good frames before reporting `OK` again so the controller does not flap.
5. **Offline buffer.** The vision node writes to local SQLite first; B4 builds the replay job that republishes buffered rows after an outage; Squad A's ingest writes them to MySQL.

### Phase 3: Bench integration / midterm prototype (Nov 9–15)

1. Run the vision node, the real ESP32 (Squad A) and the Next.js dashboard (Squad C) together on the bench.
2. Run the USB Serial fallback end to end at least once.
3. Re-capture 50–100 images per class on the actual diorama surface once it exists, then retrain; a background shift alone can drop accuracy.
4. Produce midterm evidence: architecture diagram, EER diagram, accuracy report, FPS/latency report, and a short screen recording of the working loop.

### Phase 4: Fail-safe integration & stress testing (Nov 16–29)

Run the full test plan in Section 4 on the assembled diorama. Fix, re-test, and log every run.

### Phase 5: Freeze & rehearse (Nov 30–mid-Dec)

1. Freeze code around December 4; after that, only bug fixes through reviewed PRs.
2. Write a one-page demo runbook: startup order, IPs, which terminal runs what, recovery steps per failure.
3. Record a backup demo video in case the venue fails.
4. Rehearse with the laptop on the same power plan, brightness and running apps as on stage.

**Network single point of failure.** Squad A's pocket Wi-Fi carries MQTT, so the USB-tethered phone stays camera-only. Never use the camera phone as the hotspot.

## 4. Squad-Specific Testing & Validation Plan

No system reaches literally 100% reliability; the panel will respect defined pass criteria, measured evidence, and a fallback that works when something fails. The degradation hierarchy is that story, so test it as such.

### A. Unit tests (pytest, every PR)

- **PCU calculation:** known counts give expected scores; weights load from config; an empty approach yields 0.
- **Geometry:** point-in-polygon for ROIs and stop-line crossing direction; a vehicle reversing over the line must not count.
- **Violation logic:** scripted tracks plus scripted signal states. Red + crossing gives exactly one event; amber or green gives none; a flickering track ID gives no duplicates.
- **Health monitor:** synthetic black, blurred and normal frames give `OCCLUDED`, `DEGRADED` and `OK`; the hysteresis delay is honored.
- **Schema validation:** every outgoing payload passes the committed JSON Schema; a malformed message fails.
- **Privacy:** the crop function never returns a full frame; output size and blur are within spec.

### B. Model validation

- Report mAP50 plus per-class precision and recall on the held-out diorama test set, with a confusion matrix (expect tricycle/motorcycle confusion at 1:64 scale).
- Define the 85% KPI explicitly as per-class count accuracy on recorded test clips versus manually counted ground truth, since that drives signal timing.

### C. Performance & latency

- **Sustained FPS.** 30-minute soak test logging FPS and CPU temperature every 10 seconds. Pass: ≥15 FPS with no thermal cliff.
- **End-to-end latency.** Laptop and ESP32 clocks are not synced, so: stamp frame-capture time on the laptop; the ESP32 publishes a pong right after writing the LED GPIO; compute capture-to-pong on the laptop (a conservative upper bound). Collect at least 1,000 samples, report p50/p95/p99. Pass: p95 < 200 ms.
- **MQTT-only round trip.** Ping/pong without inference, to separate the network's share from the model's.

### D. Integration & fail-safe tests

| Test | Procedure | Pass criteria |
| --- | --- | --- |
| Lens occlusion handover | Cover the lens with a card, then a wet plastic sheet (simulated rain) | OCCLUDED status and controller in L2 within 3 s (North HC-SR04 for N–S, East IR for E–W); back to L1 after hysteresis without flapping |
| Vision process crash | Kill the Python process | Retained OFFLINE via Last Will; controller in L2 within 3 s |
| Camera unplug | Pull the phone's USB cable | Same as above; vision node reconnects automatically on replug |
| Broker loss | Stop Mosquitto | Controller degrades on its own; vision buffers locally and resumes on restart |
| Serial fallback | Disable Wi-Fi, switch to USB Serial | Density messages reach the ESP32 within 30 s |
| Laptop power cut | Unplug the charger mid-run | FPS stays ≥15 (High Performance plan on battery); no process restarts |
| Diode-OR failover (Squad A circuit) | Cut primary power to the ESP32 | `uptime_ms` never resets; MQTT session continues |
| Flood override coexistence | Squad A triggers L4 | Vision keeps counting and logging; violations suppressed during flashing amber, flood or fault |

### E. Database validation

- **Integrity:** hourly totals in MySQL match the vision node's own counts for the same window.
- **No duplicates:** replaying the same buffer twice adds zero rows (unique `event_id`).
- **Outage replay:** stop MySQL for 10 minutes under traffic, restart, confirm every buffered row arrives.
- **Timestamps:** store UTC, display Asia/Manila; spot-check that a 5:00 PM local event shows as 5:00 PM on the dashboard.
- **Privacy audit:** query the violations table and crop folder; confirm no full frames, no readable plate or body-number text, no OCR fields.

### F. Test logging

For every run, record date, commit hash, who ran it, result, and a link to the logs. On judging day, a report showing 30 passing occlusion-handover runs is worth more than claiming it works.

**First two tasks:** the Phase 0 FPS benchmark and the toy-vehicle selection. They resolve the squad's two biggest risks, the custom dataset and whether the demo laptop holds 15 FPS, by the end of this week.
