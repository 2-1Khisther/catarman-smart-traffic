import os, sys
import cv2
from dotenv import load_dotenv
from ultralytics import YOLO

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
cam = int(os.getenv("CAMERA_INDEX", 1))
cap = cv2.VideoCapture(cam, cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
model = YOLO("best.pt")

while True:
    ok, frame = cap.read()
    if not ok:
        print("No frame - check CAMERA_INDEX in .env")
        break
    res = model(frame, imgsz=416, conf=0.5, verbose=False)[0]
    for b in res.boxes:
        print(res.names[int(b.cls)], round(float(b.conf), 2))
    cv2.imshow("detect_test (q to quit)", res.plot())
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()