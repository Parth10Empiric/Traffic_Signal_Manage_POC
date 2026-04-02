import streamlit as st
import cv2
import time
import threading

from detector import VehicleDetector
from decision import *

# =========================
# SESSION STATE
# =========================
if "has_started" not in st.session_state:
    st.session_state.has_started = False

if "is_transition_phase" not in st.session_state:
    st.session_state.is_transition_phase = False

if "current_green" not in st.session_state:
    st.session_state.current_green = 0

if "last_lane" not in st.session_state:
    st.session_state.last_lane = 0

if "signal_end_time" not in st.session_state:
    st.session_state.signal_end_time = time.time() + 5

# =========================
# GLOBAL FRAME STORAGE
# =========================
latest_frames = [None] * 4
lock = threading.Lock()

prev_green = None
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
frozen_frames = [None] * 4
lane_states = ["RED"] * 4  
# =========================
# VIDEO THREAD
# =========================
def video_reader(index, cap):
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = 25

    delay = 1 / fps

    while True:
        start = time.time()

        # 🔴 If RED → do not read new frame (freeze)
        if lane_states[index] == "RED":
            time.sleep(delay)
            continue
        
        if cap.get(cv2.CAP_PROP_POS_FRAMES) == 0:
            pass  # already at start

        # 🟢 If GREEN/YELLOW → read normally
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        with lock:
            latest_frames[index] = frame

        elapsed = time.time() - start
        time.sleep(max(0, delay - elapsed))


# START THREADS ONLY ONCE
if "threads_started" not in st.session_state:
    st.session_state.threads_started = True
    for i, cap in enumerate(caps):
        t = threading.Thread(target=video_reader, args=(i, cap))
        t.daemon = True
        t.start()

# =========================
# DETECTION STATE
# =========================
detection_result = {
    "ready": False,
    "lane": None,
    "count": 0,
    "density": "LOW"
}

detecting = False

# =========================
# DETECTION FUNCTION
# =========================
def detect_next_lane(lane_id, frame):
    global detection_result, detecting

    frame = cv2.resize(frame, (640, 360))

    vehicles = detector.detect(frame)
    count = len(vehicles)
    density = get_density(count)

    detection_result = {
        "ready": True,
        "lane": lane_id,
        "count": count,
        "density": density
    }

    detecting = False


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
sidebar_placeholder = st.sidebar.empty()

# =========================
# LOAD STATE
# =========================
current_green = st.session_state.current_green
last_lane = st.session_state.last_lane
signal_end_time = st.session_state.signal_end_time
is_transition_phase = st.session_state.is_transition_phase

lane_info = {i: {"count": 0, "density": "LOW"} for i in range(4)}

# =========================
# MAIN LOOP
# =========================
while True:
    current_time = time.time()
    remaining_time = signal_end_time - current_time
    next_lane_id = (last_lane + 1) % 4

    # =========================
    # START DETECTION BEFORE END
    # =========================
    if remaining_time <= 10 and not detecting and not detection_result["ready"]:
        with lock:
            frame = latest_frames[next_lane_id]

        if frame is not None:
            detecting = True
            threading.Thread(
                target=detect_next_lane,
                args=(next_lane_id, frame),
                daemon=True
            ).start()

    # =========================
    # SIGNAL SWITCH
    # =========================
    if current_time >= signal_end_time:

        # FIRST START
        if not st.session_state.has_started:
            st.session_state.has_started = True
            is_transition_phase = False

        # 🟡 IF CURRENTLY YELLOW → SWITCH TO GREEN
        elif is_transition_phase:
            if detection_result["ready"]:
                current_green = detection_result["lane"]
                last_lane = current_green

                lane_info[current_green] = {
                    "count": detection_result["count"],
                    "density": detection_result["density"]
                }

                duration = get_signal_time(detection_result["count"])
                signal_end_time = current_time + duration

                detection_result["ready"] = False

            else:
                # fallback if detection not ready
                current_green = next_lane_id
                last_lane = current_green
                signal_end_time = current_time + 10  # default green

            is_transition_phase = False  # ✅ EXIT YELLOW

        # 🟢 IF GREEN → GO TO YELLOW
        else:
            signal_end_time = current_time + 3  # yellow duration
            is_transition_phase = True

    # =========================
    # DETECT GREEN → RED TRANSITION
    # =========================
    if prev_green is not None and prev_green != current_green:

        # 🔴 Old green becomes RED → reset video
        caps[prev_green].set(cv2.CAP_PROP_POS_FRAMES, 0)

        # also clear frozen frame so it captures fresh 00:00
        frozen_frames[prev_green] = None

    # update tracker
    prev_green = current_green

    # =========================
    # DISPLAY
    # =========================
    with lock:
        frames_to_show = [
            f.copy() if f is not None else None
            for f in latest_frames
        ]

    for i, frame in enumerate(frames_to_show):
        if frame is None:
            continue

        frame = frame.copy()

        if i == current_green:
            if is_transition_phase:
                color = (0, 255, 255)
                status = "YELLOW"
            else:
                color = (0, 255, 0)
                status = "GREEN"

            remaining = int(signal_end_time - current_time)

        else:
            color = (0, 0, 255)
            status = "RED"
            remaining = 0
            
        # if lane_states[i] == "RED":
        #     if frozen_frames[i] is None:
        #         if frame is not None:
        #             frozen_frames[i] = frame.copy()
        #         else:
        #             continue  # skip safely
                
        #     if frozen_frames[i] is not None:
        #         frame = frozen_frames[i]
        #     else:
        #         continue
        if lane_states[i] == "RED":
            if frozen_frames[i] is None:
                # try to grab first frame (00:00)
                caps[i].set(cv2.CAP_PROP_POS_FRAMES, 0)

                ret, first_frame = caps[i].read()
                if ret:
                    frozen_frames[i] = first_frame.copy()
                else:
                    continue
                
            frame = frozen_frames[i]

        else:
            # 🟢 Reset frozen frame when GREEN
            frozen_frames[i] = None

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

        frame_containers[i].image(frame, channels="BGR", width="stretch")

    # =========================
    # SIDEBAR
    # =========================
    # Reset all lanes
    for i in range(4):
        lane_states[i] = "RED"

    # Set active lane
    if is_transition_phase:
        lane_states[current_green] = "YELLOW"
    else:
        lane_states[current_green] = "GREEN"
        
    with sidebar_placeholder.container():
        for i in range(4):
            
            if i == current_green:
                if is_transition_phase:
                    st.warning(f"Lane {i} → YELLOW")
                else:
                    st.success(f"Lane {i} → GREEN")
            else:
                st.error(f"Lane {i} → RED")

            st.write(f"Count: {lane_info[i]['count']}")
            st.write(f"Density: {lane_info[i]['density']}")

    # SAVE STATE
    st.session_state.current_green = current_green
    st.session_state.last_lane = last_lane
    st.session_state.signal_end_time = signal_end_time
    st.session_state.is_transition_phase = is_transition_phase

    time.sleep(0.03)