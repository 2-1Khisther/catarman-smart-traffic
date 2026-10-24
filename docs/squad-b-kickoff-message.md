Good evening, Squad B! We're starting the project now. Please read the attached plan (squad-b-implementation-testing-plan.md) before Monday.

Our roles:
• Khristher (lead): MQTT contract, camera rig, coordination with Squads A and C, testing, demo runbook
• [B2 name] – Model & dataset: toy vehicles (with Squad A), image capture, labeling, training, accuracy reports
• [B3 name] – Pipeline logic: ROIs, tracking, PCU scoring, red-light violation detection, camera health monitor
• [B4 name] – Data & backend: MySQL vision tables (spec for Squad A's ingest), offline buffer + replay, video stream for the dashboard, database tests

This weekend (Phase 0):
1. Everyone: install Python 3.10/3.11 + PyCharm, clone the repo, run `pip install -r requirements.txt` in edge_vision.
2. Khristher: camera test + YOLOv8 FPS benchmark on the demo laptop, then meet the Squad A and C leads.
3. B2: check with Squad A on the toy vehicles (at least 3 per type, bright colors).
4. B4: open backend/db/vision_schema.sql in MySQL Workbench and review the tables.

Next week (Phase 1, Oct 26 – Nov 1):
• B2: capture 200+ photos per vehicle type and start labeling
• B3: camera → YOLO → tracking loop with stock weights
• B4: finalize the MySQL schema + EER diagram, hand the spec to Jim Ivan (Squad A)
• Khristher: Mosquitto on the laptop + mock MQTT messages for Squads A and C

Questions, ask in the GC. Let's go! 🚦
