import streamlit as st
import cv2
import time
import threading

from detector import VehicleDetector
from decision import *

# =========================
# GLOBAL FRAME STORAGE
# =========================
latest_frames = [None] * 4
lock = threading.Lock()

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

# =========================
# VIDEO THREAD (REAL-TIME)
# =========================
def video_reader(index, cap):
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = 25

    delay = 1 / fps

    while True:
        start = time.time()

        ret, frame = cap.read()

        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        with lock:
            latest_frames[index] = frame

        elapsed = time.time() - start
        time.sleep(max(0, delay - elapsed))


# START THREADS
for i, cap in enumerate(caps):
    t = threading.Thread(target=video_reader, args=(i, cap))
    t.daemon = True
    t.start()

# =========================
# UI
# =========================
st.title("🚦 Smart Traffic Control System")

col1, col2 = st.columns(2)
col3, col4 = st.columns(2)

frame_containers = [
    col1.empty(),
    col2.empty(),
    col4.empty(),
    col3.empty()
]

st.sidebar.title("📊 Traffic Info")

# =========================
# STATE VARIABLES
# =========================
current_green = None
signal_end_time = 0
last_lane = -1

lane_info = {i: {"count": 0, "density": "LOW"} for i in range(4)}

sidebar_placeholder = st.sidebar.empty()
# =========================
# MAIN LOOP
# =========================
while True:
    current_time = time.time()

    # =========================
    # DETECTION (ONLY WHEN SIGNAL ENDS)
    # =========================
    if current_time >= signal_end_time:

        lane_data = []

        with lock:
            frames_copy = latest_frames.copy()

        for i, frame in enumerate(frames_copy):
            if frame is None:
                continue

            vehicles = detector.detect(frame)

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
                # lane_info[current_green]["density"]
                lane_info[current_green]["count"] 
            )

            signal_end_time = current_time + duration
            

    # =========================
    # DISPLAY (SMOOTH)
    # =========================
    with lock:
        frames_to_show = latest_frames.copy()

    for i, frame in enumerate(frames_to_show):
        if frame is None:
            continue

        frame = frame.copy()

        if i == current_green:
            color = (0, 255, 0)
            status = "GREEN"
            remaining = int(signal_end_time - current_time)
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

        cv2.putText(frame, f"Count: {lane_info[i]['count']}", (20, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,0), 2)

        cv2.putText(frame, f"{lane_info[i]['density']}", (20, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,0), 2)
        

        frame_containers[i].image(
            frame,
            channels="BGR",
            width="stretch"
        )

    # =========================
    # SIDEBAR
    # =========================

    with sidebar_placeholder.container():
    
        for i in range(4):
            if i == current_green:
                st.success(f"Lane {i} → GREEN")
            else:
                st.error(f"Lane {i} → RED")

            st.write(f"Count: {lane_info[i]['count']}")
            st.write(f"Density: {lane_info[i]['density']}")
            st.markdown("---")

    # 🔥 CRITICAL FOR SMOOTHNESS
    time.sleep(0.1)
    