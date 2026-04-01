from config import *
import time

def get_density(count):
    if count < LOW_THRESHOLD:
        return "LOW"
    elif count < MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "HIGH"


# def get_signal_time(density):
#     return SIGNAL_TIMES[density]

def get_signal_time(count):

    count = int(count) 
    calculated_time = count * SEC_PER_CAR
    actual_time = max(MIN_GREEN, min(MAX_GREEN, calculated_time))
    
    return int(actual_time)

lane_last_green_time = {0: time.time(), 1: time.time(), 2: time.time(), 3: time.time()}

def choose_lane(lanes, last_lane):
    
    if not lanes:
        return None

    # Calculate the next lane ID in sequence
    # If last_lane was 3, (3 + 1) % 4 = 0
    # If last_lane was -1 (start), (-1 + 1) % 4 = 0
    next_lane_id = (last_lane + 1) % 4

    # Find the data for the next_lane_id from our detection list
    for l in lanes:
        if l["lane"] == next_lane_id:
            return l

    # Fallback: return first available if ID match fails
    return lanes[0]