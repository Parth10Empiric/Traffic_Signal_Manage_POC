from flask import Flask, Response
import cv2
import threading
import time
from collections import deque

from detector import VehicleDetector
from decision import *

app = Flask(__name__)

# =========================
# INIT
# =========================
detector = VehicleDetector()

caps = [
    cv2.VideoCapture("videos/lane1.mp4"),
    cv2.VideoCapture("videos/lane2.mp4"),
    cv2.VideoCapture("videos/lane3.mp4"),
    cv2.VideoCapture("videos/lane4.mp4")
]

# Reduce internal buffering (IMPORTANT)
for cap in caps:
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

# =========================
# FRAME BUFFER
# =========================
frame_buffers = [deque(maxlen=5) for _ in range(4)]
lock = threading.Lock()

# =========================
# STATE VARIABLES
# =========================
current_green = None
signal_end_time = 0
last_lane = -1

lane_info = {i: {"count": 0, "density": "LOW"} for i in range(4)}

# =========================
# VIDEO THREAD (FAST)
# =========================
def video_reader(index, cap):
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    delay = 1 / fps

    while True:
        start = time.time()

        ret, frame = cap.read()

        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        with lock:
            frame_buffers[index].append(frame)

        elapsed = time.time() - start
        time.sleep(max(0, delay - elapsed))


# =========================
# DETECTION THREAD (ASYNC)
# =========================
def detection_loop():
    global current_green, signal_end_time, last_lane

    while True:
        current_time = time.time()

        if current_time >= signal_end_time:

            lane_data = []

            with lock:
                frames_copy = [
                    buf[-1] if len(buf) > 0 else None
                    for buf in frame_buffers
                ]

            for i, frame in enumerate(frames_copy):
                if frame is None:
                    continue

                # 🔥 Fast detection
                small = cv2.resize(frame, (416, 416))
                vehicles = detector.detect(small)

                count = len(vehicles)
                density = get_density(count)

                lane_info[i] = {
                    "count": count,
                    "density": density
                }

                lane_data.append({
                    "lane": i,
                    "count": count,
                    "wait": 5
                })

            selected = choose_lane(lane_data, last_lane)

            if selected:
                current_green = selected["lane"]
                last_lane = current_green

                duration = get_signal_time(
                    lane_info[current_green]["density"]
                )

                signal_end_time = time.time() + duration

        time.sleep(0.5)  # reduce CPU usage


# =========================
# START THREADS
# =========================
for i, cap in enumerate(caps):
    t = threading.Thread(target=video_reader, args=(i, cap))
    t.daemon = True
    t.start()

# Start detection thread
t_detect = threading.Thread(target=detection_loop)
t_detect.daemon = True
t_detect.start()


# =========================
# FRAME GENERATOR (STREAM)
# =========================
def generate_frames():
    while True:

        with lock:
            frames = [
                buf.popleft() if len(buf) > 0 else None
                for buf in frame_buffers
            ]

        processed_frames = []

        for i, frame in enumerate(frames):
            if frame is None:
                continue

            frame = frame.copy()

            count = lane_info[i]["count"]
            density = lane_info[i]["density"]

            if i == current_green:
                color = (0, 255, 0)
                status = "GREEN"
                remaining = int(signal_end_time - time.time())
            else:
                color = (0, 0, 255)
                status = "RED"
                remaining = 0

            # Draw info
            cv2.putText(frame, f"Lane {i}", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)

            cv2.putText(frame, status, (20, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)

            cv2.putText(frame, f"Time: {remaining}s", (20, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

            cv2.putText(frame, f"Count: {count}", (20, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,0), 2)

            cv2.putText(frame, f"{density}", (20, 180),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,0), 2)

            processed_frames.append(cv2.resize(frame, (640, 360)))

        if len(processed_frames) == 4:
            top = cv2.hconcat(processed_frames[:2])
            bottom = cv2.hconcat(processed_frames[2:])
            final_frame = cv2.vconcat([top, bottom])
        else:
            continue

        _, buffer = cv2.imencode('.jpg', final_frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# =========================
# ROUTE
# =========================
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True, threaded=True)