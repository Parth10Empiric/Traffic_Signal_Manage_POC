# config.py

# Density thresholds
LOW_THRESHOLD = 10
MEDIUM_THRESHOLD = 25

# Signal timings
# SIGNAL_TIMES = {
#     "LOW": 10,
#     "MEDIUM": 20,
#     "HIGH": 30
# }

MIN_GREEN = 10   # Minimum time for safety/pedestrians
MAX_GREEN = 60   # Maximum time to prevent frustration
SEC_PER_CAR = 1.6 # Average time for one vehicle to cross

# Yellow signal duration
YELLOW_TIME = 2

# Scoring weights
COUNT_WEIGHT = 0.7
WAIT_WEIGHT = 0.3

MAX_WAIT_TIME = 90  # Max wait time in seconds before a lane gets emergency priority