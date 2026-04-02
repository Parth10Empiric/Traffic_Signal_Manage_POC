from flask import Flask, Response
import cv2
import threading
import time
from collections import deque

from detector import VehicleDetector
from decision import get_density, get_signal_time

app = Flask(__name__)

# =========================
# CONFIG
# =========================
NUM_LANES = 4
VIDEO_PATHS = [
    "videos/lane1.mp4",
    "videos/lane2.mp4",
    "videos/lane3.mp4",
    "videos/lane4.mp4"
]

# =========================
# INIT
# =========================
detector = VehicleDetector()

caps = [cv2.VideoCapture(path) for path in VIDEO_PATHS]

for cap in caps:
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

# =========================
# FRAME STORAGE
# =========================
frame_buffers = [deque(maxlen=5) for _ in range(NUM_LANES)]
lock = threading.Lock()

# =========================
# STATE VARIABLES
# =========================
current_green = 0
last_lane = 0
signal_end_time = time.time() + 5

lane_info = {i: {"count": 0, "density": "LOW"} for i in range(NUM_LANES)}

detection_result = {
    "ready": False,
    "lane": None,
    "count": 0,
    "density": "LOW"
}

detecting = False
is_transition_phase = False
last_detection_time = 0
DETECTION_COOLDOWN = 2  # seconds

# =========================
# VIDEO THREAD
# =========================
def video_reader(index, cap):
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    delay = 1 / fps

    while True:
        start = time.time()

        if not cap.isOpened():
            print(f"[ERROR] Camera {index} not opened")
            time.sleep(1)
            continue

        ret, frame = cap.read()

        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        with lock:
            frame_buffers[index].append(frame)

        elapsed = time.time() - start
        time.sleep(max(0, delay - elapsed))


# =========================
# DETECTION FUNCTION
# =========================
def detect_next_lane(lane_id, frame):
    global detection_result, detecting

    try:
        small = cv2.resize(frame, (640, 360))
        vehicles = detector.detect(small)

        count = len(vehicles)
        density = get_density(count)

        detection_result.update({
            "ready": True,
            "lane": lane_id,
            "count": count,
            "density": density
        })

    except Exception as e:
        print(f"[ERROR] Detection failed: {e}")

    finally:
        detecting = False


# =========================
# CONTROL LOOP
# =========================
def control_loop():
    global current_green, signal_end_time, last_lane
    global detecting, detection_result, is_transition_phase, last_detection_time

    while True:
        now = time.time()
        remaining = signal_end_time - now
        next_lane = (last_lane + 1) % NUM_LANES

        # 🔥 PRE-DETECTION (last 5 sec)
        if (
            remaining <= 5 and
            not detecting and
            not detection_result["ready"] and
            (now - last_detection_time > DETECTION_COOLDOWN)
        ):
            with lock:
                frame = frame_buffers[next_lane][-1] if frame_buffers[next_lane] else None

            if frame is not None:
                detecting = True
                last_detection_time = now

                threading.Thread(
                    target=detect_next_lane,
                    args=(next_lane, frame),
                    daemon=True
                ).start()

        # 🔥 SIGNAL SWITCH
        if now >= signal_end_time:

            if detection_result["ready"]:
                current_green = detection_result["lane"]
                last_lane = current_green

                lane_info[current_green] = {
                    "count": detection_result["count"],
                    "density": detection_result["density"]
                }

                duration = get_signal_time(detection_result["count"])
                signal_end_time = now + duration

                detection_result["ready"] = False
                is_transition_phase = False

            elif not is_transition_phase:
                current_green = next_lane
                last_lane = current_green
                signal_end_time = now + 5
                is_transition_phase = True

            else:
                signal_end_time = now + 1

        time.sleep(0.05)


# =========================
# STREAM GENERATOR
# =========================
def generate_frames():
    while True:

        with lock:
            frames = [
                buf[-1] if buf else None
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
                if is_transition_phase:
                    color = (0, 255, 255)
                    status = "YELLOW"
                else:
                    color = (0, 255, 0)
                    status = "GREEN"

                remaining = int(signal_end_time - time.time())
            else:
                color = (0, 0, 255)
                status = "RED"
                remaining = 0

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

        if len(processed_frames) != NUM_LANES:
            continue

        top = cv2.hconcat(processed_frames[:2])
        bottom = cv2.hconcat(processed_frames[2:])
        final_frame = cv2.vconcat([top, bottom])

        _, buffer = cv2.imencode('.jpg', final_frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# =========================
# ROUTES
# =========================
@app.route('/')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# =========================
# START THREADS
# =========================
def start_threads():
    for i, cap in enumerate(caps):
        threading.Thread(
            target=video_reader,
            args=(i, cap),
            daemon=True
        ).start()

    threading.Thread(target=control_loop, daemon=True).start()


# =========================
# RUN
# =========================
if __name__ == "__main__":
    start_threads()
    app.run(debug=True, threaded=True)

