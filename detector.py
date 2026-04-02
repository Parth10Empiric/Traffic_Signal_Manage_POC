# from ultralytics import YOLO
# # import os
# # import time

# class VehicleDetector:
#     def __init__(self):
#         # 🔥 You can upgrade model later (yolov9 / yolov10)
#         self.model = YOLO("models/yolov8x.pt")
#         # self.save_dir = "detected_frames"
#         # os.makedirs(self.save_dir, exist_ok=True)

#         # COCO vehicle classes
#         self.vehicle_classes = [2, 3, 5, 7]  # car, motorbike, bus, truck

#     def detect(self, frame):
#         h, w = frame.shape[:2]

#         tiles = [
#             frame[0:h//2, 0:w//2],
#             frame[0:h//2, w//2:w],
#             frame[h//2:h, 0:w//2],
#             frame[h//2:h, w//2:w]
#         ]

#         vehicles = []

#         for idx, tile in enumerate(tiles):
#             results = self.model(
#                 tile,
#                 imgsz=640,
#                 conf=0.15,
#                 verbose=False
#             )[0]

#             for box in results.boxes:
#                 cls = int(box.cls[0])

#                 if cls in self.vehicle_classes:
#                     x1, y1, x2, y2 = map(int, box.xyxy[0])

#                     # 🔥 map back to original frame
#                     if idx == 1:
#                         x1 += w//2
#                         x2 += w//2
#                     elif idx == 2:
#                         y1 += h//2
#                         y2 += h//2
#                     elif idx == 3:
#                         x1 += w//2
#                         y1 += h//2
#                         x2 += w//2
#                         y2 += h//2

#                     vehicles.append([x1, y1, x2, y2])

#         # =========================
#         # 🔥 SAVE IMAGE WITH BOXES
#         # =========================
#         # if len(vehicles) > 0:
#         #     save_frame = frame.copy()

#         #     for (x1, y1, x2, y2) in vehicles:
#         #         cv2.rectangle(save_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

#         #     # unique filename
#         #     filename = f"{self.save_dir}/frame_{int(time.time()*1000)}.jpg"

#         #     cv2.imwrite(filename, save_frame)

#         return vehicles
    
    
from ultralytics import YOLO
import numpy as np
# import os
# import time
# import cv2

class VehicleDetector:
    def __init__(self):
        self.model = YOLO("models/yolov8x.pt")

        # COCO vehicle classes
        self.vehicle_classes = [2, 3, 5, 7]

        # 🔥 SAVE DIRECTORY
        # self.save_dir = "detected_frames"
        # os.makedirs(self.save_dir, exist_ok=True)

    # =========================
    # 🔥 NMS FUNCTION
    # =========================
    def apply_nms(self, boxes, iou_threshold=0.5):
        if len(boxes) == 0:
            return []

        boxes = np.array(boxes)

        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]

        areas = (x2 - x1) * (y2 - y1)
        indices = np.argsort(y2)

        keep = []

        while len(indices) > 0:
            last = indices[-1]
            keep.append(last)

            xx1 = np.maximum(x1[last], x1[indices[:-1]])
            yy1 = np.maximum(y1[last], y1[indices[:-1]])
            xx2 = np.minimum(x2[last], x2[indices[:-1]])
            yy2 = np.minimum(y2[last], y2[indices[:-1]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)

            overlap = (w * h) / areas[indices[:-1]]

            indices = np.delete(
                indices,
                np.concatenate(([len(indices) - 1],
                np.where(overlap > iou_threshold)[0]))
            )

        return boxes[keep].astype(int).tolist()

    # =========================
    # 🔍 DETECTION
    # =========================
    def detect(self, frame):
        h, w = frame.shape[:2]

        tiles = [
            frame[0:h//2, 0:w//2],
            frame[0:h//2, w//2:w],
            frame[h//2:h, 0:w//2],
            frame[h//2:h, w//2:w]
        ]

        vehicles = []

        for idx, tile in enumerate(tiles):
            results = self.model(
                tile,
                imgsz=640,
                conf=0.15,
                verbose=False
            )[0]

            for box in results.boxes:
                cls = int(box.cls[0])

                if cls in self.vehicle_classes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    # map back to original frame
                    if idx == 1:
                        x1 += w//2
                        x2 += w//2
                    elif idx == 2:
                        y1 += h//2
                        y2 += h//2
                    elif idx == 3:
                        x1 += w//2
                        y1 += h//2
                        x2 += w//2
                        y2 += h//2

                    vehicles.append([x1, y1, x2, y2])

        # 🔥 REMOVE DUPLICATES
        vehicles = self.apply_nms(vehicles)

        # =========================
        # 🔥 SAVE IMAGE WITH BOXES
        # =========================
        # if len(vehicles) > 0:
        #     save_frame = frame.copy()

        #     for (x1, y1, x2, y2) in vehicles:
        #         cv2.rectangle(save_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        #     # unique filename (timestamp)
        #     filename = f"{self.save_dir}/frame_{int(time.time()*1000)}.jpg"

        #     cv2.imwrite(filename, save_frame)

        return vehicles