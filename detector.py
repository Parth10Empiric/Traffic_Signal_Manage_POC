from ultralytics import YOLO

class VehicleDetector:
    def __init__(self):
        self.model = YOLO("models/yolov8x.pt")
        self.vehicle_classes = [2, 3, 5, 7]

    def detect(self, frame):
        results = self.model(frame, verbose=False)[0]

        vehicles = []
        for box in results.boxes:
            cls = int(box.cls[0])
            if cls in self.vehicle_classes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                vehicles.append([x1, y1, x2, y2])

        return vehicles