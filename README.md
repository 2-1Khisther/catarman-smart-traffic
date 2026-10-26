# Catarman LGU Climate-Resilient SMART Traffic Light

Monorepo for the 4th-year IT midterm project. Squad B (Edge Vision & AI) starter kit.

## Folders

| Folder | Owner | What's inside |
| --- | --- | --- |
| `/edge_vision` | Squad B | Python vision service: camera ingest, YOLOv8n, tracking, PCU, violations, MQTT |
| `/backend/db` | Squad B (design) / Squad A (ingest) | MySQL schema for vision tables |
| `/firmware` | Squad A | ESP32 firmware (not in this starter) |
| `/dashboard` | Squad C | Next.js dashboard + Express API (not in this starter) |
| `/docs` | All | Plan, MQTT contract (JSON Schema), test reports |

## Squad B quick start (Windows + PyCharm)

1. Open `edge_vision` as a PyCharm project with a Python 3.10 or 3.11 virtualenv.
2. In PyCharm's Terminal:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` in the repo root and fill in your values.
4. Connect the phone with DroidCam (USB mode), then run, in order:
   ```
   python tools/camera_test.py        # Step 1: camera works, note resolution + FPS
   python tools/benchmark.py          # Step 2: YOLOv8n FPS on this laptop
   python tools/mock_publisher.py     # Step 3: needs Mosquitto running
   pytest tests                       # Step 4: payloads match the MQTT contract
   ```
5. Write your numbers in `docs/test-reports/phase0-baseline.md`.

## Running the real vision node

1. Point the phone at the intersection, then mark the roads (redo whenever the camera moves):
   ```
   python tools/roi_tool.py
   ```
   SPACE freezes the picture. For each road N, E, S, W: click the corners of the waiting lane,
   press ENTER, then click the two ends of its stop line. Saves `rois.json`.
2. Start the node (Mosquitto running):
   ```
   python vision_node.py
   ```
   Window shows boxes, track IDs, counts per road (T/M/C), FPS, camera status and MQTT state.
   Press q to stop. Use `--source clip.mp4` for a recorded clip, `--no-window` for headless.
3. Test: cover the lens with your hand -> status OCCLUDED at once, back to OK 5 s after you uncover it.

Violations are only judged when Squad A's `controller/state` is received (and never during
flood L4, faults or amber). Crops in `crops/` are 96 px and blurred (RA 10173).
Everything published is also logged to `buffer/vision_log.db` (offline-first).

## MQTT contract

See `docs/mqtt-contract/`. Every message Squad B publishes must pass these schemas.
Change a schema only after Squads A and C agree.
