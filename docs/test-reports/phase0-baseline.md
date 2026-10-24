# Phase 0 Baseline Report (Squad B)

Date: ____  ·  Run by: ____  ·  Laptop model / CPU / RAM: ____

## 1. Camera test (`tools/camera_test.py`)

| App (DroidCam / Iriun) | Camera index | Resolution | FPS |
| --- | --- | --- | --- |
| | | | |

## 2. Coverage check

| Phone height (cm) | All four approaches in frame? | Notes |
| --- | --- | --- |
| 55 | | |
| 65 | | |
| 70 | | |

## 3. YOLOv8n benchmark (`tools/benchmark.py`)

Alone:

| Runtime | imgsz | FPS | >= 15? |
| --- | --- | --- | --- |
| | | | |

With Mosquitto + MySQL + Next.js running:

| Runtime | imgsz | FPS | >= 15? |
| --- | --- | --- | --- |
| | | | |

## 4. Mock publisher + contract tests

- `mosquitto_sub` receives heartbeat / density / violation: ☐ yes ☐ no
- Killing the script shows `OFFLINE` on `vision/status`: ☐ yes ☐ no
- `pytest tests` result: ____ passed / ____ failed

## Decision

☐ 15 FPS reachable → continue with the plan
☐ Not reachable → options: OpenVINO, imgsz 416, skip frames, or a stronger laptop
