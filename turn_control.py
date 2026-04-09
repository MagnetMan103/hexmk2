import time
import sys
import busio
import board
import serial
import threading
from adafruit_servokit import ServoKit

# ============================================================================
# IMU Serial Reader Setup
# ============================================================================
ARDUINO_PORT = '/dev/ttyACM0'  # Adjust if your Jetson enumerates it as /dev/ttyUSB0
BAUD_RATE = 9600

current_yaw = 0.0
yaw_lock = threading.Lock()

def imu_reader_thread():
    """Background thread to keep `current_yaw` updated with the freshest IMU data."""
    global current_yaw
    try:
        ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=0.1)
        print(f"SYSTEM: Connected to Arduino IMU on {ARDUINO_PORT}")
    except Exception as e:
        print(f"SYSTEM: IMU Serial connection failed: {e}")
        return

    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("YPR:"):
                    # Parse "YPR: <yaw>, <pitch>, <roll>"
                    parts = line.split("YPR:")[1].split(",")
                    with yaw_lock:
                        current_yaw = float(parts[0])
        except Exception:
            pass # Ignore malformed serial bytes

# Start the IMU listener immediately
imu_thread = threading.Thread(target=imu_reader_thread, daemon=True)
imu_thread.start()

# ============================================================================
# Setup I2C and ServoKit
# ============================================================================
try:
    i2c = busio.I2C(board.SCL_1, board.SDA_1)
    kit = ServoKit(channels=16, i2c=i2c, address=0x41)
except Exception as e:
    print(f"I2C Error: {e}. Check your SCL/SDA pins and 0x41 address.")
    sys.exit(1)

# ============================================================================
# Calibration & Constants
# ============================================================================
def count_to_us(count):
    return int(count * 4.8828)

CALIBRATION_DATA = {
    0: (100,550), 1: (180, 490),
    2: (80, 530), 3: (140, 460),
    4: (130, 580), 5: (130, 420),
    6: (80, 530),  7: (460, 150),
    8: (80, 530), 9: (460, 150),
    10: (570, 120), 11: (510, 200)
}

for pin, (val1, val2) in CALIBRATION_DATA.items():
    p_min = count_to_us(min(val1, val2))
    p_max = count_to_us(max(val1, val2))
    kit.servo[pin].set_pulse_width_range(p_min, p_max)

STEP_DELAY = 0.5
SETTLE_DELAY = 0.5
KNEE_NEUTRAL = 110
KNEE_LIFTED = 120
KNEE_LOWERED = 100
HIP_NEUTRAL = 90
DEFAULT_SWING = 30 # Default step angle size in degrees

# ============================================================================
# Core Movement Logic
# ============================================================================
def set_angle(servo_index, angle):
    angle = max(0, min(180, angle))
    val1, val2 = CALIBRATION_DATA[servo_index]
    if val1 > val2:
        actual_angle = 180 - angle
    else:
        actual_angle = angle
    kit.servo[servo_index].angle = actual_angle

def stand_up():
    print("SYSTEM: Initializing Stance (Standing Up)...")
    set_angle(0, KNEE_LOWERED)
    set_angle(2, KNEE_LOWERED)
    set_angle(4, KNEE_LOWERED)
    time.sleep(1)
    set_angle(6, KNEE_LOWERED)
    set_angle(8, KNEE_LOWERED)
    set_angle(10, KNEE_LOWERED)
    time.sleep(1)
    
    for pin in [1, 3, 5, 7, 9, 11]:
        set_angle(pin, HIP_NEUTRAL)
    time.sleep(0.5)

# ============================================================================
# Gait Directions (Direct Angles)
# ============================================================================
def backward(swing_angle):
    fwd = HIP_NEUTRAL - swing_angle

    # === TRIPOD GROUP A ===
    for p in [2, 6, 10]: set_angle(p, KNEE_LOWERED)
    for p in [0, 4, 8]: set_angle(p, KNEE_LIFTED)
    time.sleep(STEP_DELAY)
    for p in [1, 5, 9]: set_angle(p, fwd)
    time.sleep(STEP_DELAY)
    for p in [0, 4, 8]: set_angle(p, KNEE_LOWERED - 5)
    time.sleep(STEP_DELAY)
    for p in [1, 5, 9]: set_angle(p, HIP_NEUTRAL)
    time.sleep(SETTLE_DELAY)

    # === TRIPOD GROUP B ===
    for p in [2, 6, 10]: set_angle(p, KNEE_LIFTED)
    time.sleep(STEP_DELAY)
    for p in [3, 7, 11]: set_angle(p, fwd)
    time.sleep(STEP_DELAY)
    for p in [2, 6, 10]: set_angle(p, KNEE_LOWERED - 5)
    time.sleep(STEP_DELAY)
    for p in [3, 7, 11]: set_angle(p, HIP_NEUTRAL)
    time.sleep(SETTLE_DELAY)

def forward(swing_angle):
    back = HIP_NEUTRAL + swing_angle

    # === TRIPOD GROUP A ===
    for p in [0, 4, 8]: set_angle(p, KNEE_LIFTED)
    time.sleep(STEP_DELAY)
    for p in [1, 5, 9]: set_angle(p, back)
    time.sleep(STEP_DELAY)
    for p in [0, 4, 8]: set_angle(p, KNEE_LOWERED)
    time.sleep(STEP_DELAY)
    for p in [1, 5, 9]: set_angle(p, HIP_NEUTRAL)
    time.sleep(SETTLE_DELAY)

    # === TRIPOD GROUP B ===
    for p in [2, 6, 10]: set_angle(p, KNEE_LIFTED)
    time.sleep(STEP_DELAY)
    for p in [3, 7, 11]: set_angle(p, back)
    time.sleep(STEP_DELAY)
    for p in [2, 6, 10]: set_angle(p, KNEE_LOWERED)
    time.sleep(STEP_DELAY)
    for p in [3, 7, 11]: set_angle(p, HIP_NEUTRAL)
    time.sleep(SETTLE_DELAY)

def step_turn_right(swing_angle):
    fwd = HIP_NEUTRAL - swing_angle
    back = HIP_NEUTRAL + swing_angle

    # === TRIPOD GROUP A ===
    for p in [2, 6, 10]: set_angle(p, KNEE_LOWERED)
    for p in [0, 4, 8]: set_angle(p, KNEE_LIFTED)
    time.sleep(STEP_DELAY)
    set_angle(1, fwd); set_angle(5, fwd); set_angle(9, back)
    time.sleep(STEP_DELAY)
    for p in [0, 4, 8]: set_angle(p, KNEE_LOWERED)
    time.sleep(STEP_DELAY)
    for p in [1, 5, 9]: set_angle(p, HIP_NEUTRAL)
    time.sleep(SETTLE_DELAY)

    # === TRIPOD GROUP B ===
    for p in [2, 6, 10]: set_angle(p, KNEE_LIFTED)
    time.sleep(STEP_DELAY)
    set_angle(3, fwd); set_angle(7, back); set_angle(11, back)
    time.sleep(STEP_DELAY)
    for p in [2, 6, 10]: set_angle(p, KNEE_LOWERED - 5)
    time.sleep(STEP_DELAY)
    for p in [3, 7, 11]: set_angle(p, HIP_NEUTRAL)
    time.sleep(SETTLE_DELAY)

def step_turn_left(swing_angle):
    fwd = HIP_NEUTRAL - swing_angle
    back = HIP_NEUTRAL + swing_angle

    # === TRIPOD GROUP A ===
    for p in [2, 6, 10]: set_angle(p, KNEE_LOWERED)
    for p in [0, 4, 8]: set_angle(p, KNEE_LIFTED)
    time.sleep(STEP_DELAY)
    set_angle(1, back); set_angle(5, back); set_angle(9, fwd)
    time.sleep(STEP_DELAY)
    for p in [0, 4, 8]: set_angle(p, KNEE_LOWERED)
    time.sleep(STEP_DELAY)
    for p in [1, 5, 9]: set_angle(p, HIP_NEUTRAL)
    time.sleep(SETTLE_DELAY)

    # === TRIPOD GROUP B ===
    for p in [2, 6, 10]: set_angle(p, KNEE_LIFTED)
    time.sleep(STEP_DELAY)
    set_angle(3, back); set_angle(7, fwd); set_angle(11, fwd)
    time.sleep(STEP_DELAY)
    for p in [2, 6, 10]: set_angle(p, KNEE_LOWERED)
    time.sleep(STEP_DELAY)
    for p in [3, 7, 11]: set_angle(p, HIP_NEUTRAL)
    time.sleep(SETTLE_DELAY)

# ============================================================================
# Closed-Loop Angle Turn Logic
# ============================================================================
def get_angle_diff(target, current):
    """Calculates shortest distance between two angles handling wrap-around."""
    return (target - current + 180) % 360 - 180

def turn_left(target_degrees, swing_angle, max_iterations=15):
    global current_yaw
    print(f"SYSTEM: Initiating LEFT turn by {target_degrees} degrees (initial step swing: {swing_angle} deg)")
    
    with yaw_lock:
        start_yaw = current_yaw
        
    target_yaw = (start_yaw + target_degrees + 180) % 360 - 180 
    TOLERANCE = 8.0 
    
    iteration = 0
    previous_diff = None
    
    while iteration < max_iterations:
        with yaw_lock:
            current = current_yaw
            
        diff = get_angle_diff(target_yaw, current)
        
        if abs(diff) <= TOLERANCE:
            print(f"SYSTEM: Turn complete. Target: {target_yaw:.1f}, Current: {current:.1f}")
            return True
            
        # Overshoot Check & Adaptive Control
        if previous_diff is not None:
            if (previous_diff > 0 and diff < 0) or (previous_diff < 0 and diff > 0):
                swing_angle = max(swing_angle // 2, 5) # Cut swing in half, minimum 5 deg
                print(f"SYSTEM: Overshot target! Reducing step swing to {swing_angle} deg")
        
        if diff > 0:
            step_turn_left(swing_angle) 
        else:
            step_turn_right(swing_angle) # Bang-bang correction
            
        previous_diff = diff
        iteration += 1

    print(f"SYSTEM: WARNING: Turn timed out after {max_iterations} steps. Final yaw: {current_yaw:.1f}")
    return False

def turn_right(target_degrees, swing_angle, max_iterations=15):
    global current_yaw
    print(f"SYSTEM: Initiating RIGHT turn by {target_degrees} degrees (initial step swing: {swing_angle} deg)")
    
    with yaw_lock:
        start_yaw = current_yaw
        
    target_yaw = (start_yaw - target_degrees + 180) % 360 - 180 
    TOLERANCE = 8.0 
    
    iteration = 0
    previous_diff = None
    
    while iteration < max_iterations:
        with yaw_lock:
            current = current_yaw
            
        diff = get_angle_diff(target_yaw, current)
        
        if abs(diff) <= TOLERANCE:
            print(f"SYSTEM: Turn complete. Target: {target_yaw:.1f}, Current: {current:.1f}")
            return True
            
        # Overshoot Check & Adaptive Control
        if previous_diff is not None:
            if (previous_diff > 0 and diff < 0) or (previous_diff < 0 and diff > 0):
                swing_angle = max(swing_angle // 2, 5) # Cut swing in half, minimum 5 deg
                print(f"SYSTEM: Overshot target! Reducing step swing to {swing_angle} deg")
        
        if diff < 0:
            step_turn_right(swing_angle) 
        else:
            step_turn_left(swing_angle) # Bang-bang correction
            
        previous_diff = diff
        iteration += 1

    print(f"SYSTEM: WARNING: Turn timed out after {max_iterations} steps. Final yaw: {current_yaw:.1f}")
    return False

# ============================================================================
# Main Terminal Control Loop
# ============================================================================
if __name__ == "__main__":
    stand_up()
    print("\n--- Hexapod Controller Ready ---")
    print("Move Commands format:  'CMD:SWING_ANGLE' (e.g., 1:30)")
    print("Turn Commands format:  'CMD:TARGET_DEGREES:SWING_ANGLE' (e.g., 2:90:30)")
    print("1: Forward | 2: Turn Right | 3: Turn Left | 4: Backward")
    
    try:
        while True:
            user_input = input("\nCommand: ").strip()
            if not user_input: continue
            
            parts = user_input.split(':')
            cmd = parts[0]
            
            # Forward & Backward
            if cmd in ["1", "4"]:
                swing = int(parts[1]) if len(parts) > 1 else DEFAULT_SWING
                swing = max(5, min(60, swing)) # Safety limit: 5 to 60 degree swings
                
                if cmd == "1":
                    print(f"Forward with {swing} degree step")
                    forward(swing)
                elif cmd == "4":
                    print(f"Backward with {swing} degree step")
                    backward(swing)
            
            # Turning
            elif cmd in ["2", "3"]:
                target_deg = int(parts[1]) if len(parts) > 1 else 90
                swing = int(parts[2]) if len(parts) > 2 else DEFAULT_SWING
                swing = max(5, min(60, swing))
                
                if cmd == "2":
                    turn_right(target_deg, swing)
                elif cmd == "3":
                    turn_left(target_deg, swing)
                    
            else:
                print("Unknown Command. Use 1, 2, 3, or 4.")
                
    except KeyboardInterrupt:
        print("\nShutting down. Moving to neutral...")
        stand_up()
