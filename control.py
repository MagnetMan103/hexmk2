import time
import sys
import busio
import board
from adafruit_servokit import ServoKit

# ============================================================================
# Setup I2C and ServoKit
# ============================================================================
# Initializing I2C on Bus 1 of the Jetson Orin 40-pin header
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
    """Converts PCA9685 register counts to microseconds."""
    return int(count * 4.8828)

# Updated Hip Calibrations and Original Knee Calibrations
CALIBRATION_DATA = {
    0: (120,600), 1: (180, 490),
    2: (120, 575), 3: (140, 460),
    4: (125, 570), 5: (130, 420),
    6: (45, 510),  7: (480, 170), # Reversed
    8: (75, 530), 9: (460, 150), # Reversed
    10: (560, 100), 11: (510, 200)  # Reversed
}

# Apply calibration and determine orientation
for pin, (val1, val2) in CALIBRATION_DATA.items():
    p_min = count_to_us(min(val1, val2))
    p_max = count_to_us(max(val1, val2))
    kit.servo[pin].set_pulse_width_range(p_min, p_max)

# Gait parameters
STEP_DELAY = 0.25   # Slightly faster for smoother tripod transitions
SETTLE_DELAY = 0.5
KNEE_NEUTRAL = 110
KNEE_LIFTED = 120
KNEE_LOWERED = 100
HIP_NEUTRAL = 90

# ============================================================================
# Core Movement Logic
# ============================================================================

def set_angle(servo_index, angle):
    """Sets angle while respecting reversed calibrations (val1 > val2)"""
    angle = max(0, min(180, angle))
    val1, val2 = CALIBRATION_DATA[servo_index]
    
    # Logic for reversed servos: if the first value is larger, 
    # then the movement direction is inverted relative to standard servos.
    if val1 > val2:
        actual_angle = 180 - angle
    else:
        actual_angle = angle
        
    kit.servo[servo_index].angle = actual_angle

def stand_up():
    """Forces all legs to ground and hips to neutral for stability."""
    print("SYSTEM: Initializing Stance (Standing Up)...")
    # Ground all knees first to support weight
    for i in [0, 2, 4, 6, 8, 10]:
        set_angle(i, KNEE_LOWERED)
    time.sleep(0.5)
    # Move all hips to neutral
    for i in [1, 3, 5, 7, 9, 11]:
        set_angle(i, HIP_NEUTRAL)
    time.sleep(0.5)

def amplitude_to_swing(amplitude):
    """Maps 10-100 amplitude to a 10-50 degree hip swing."""
    return 10 + (amplitude - 10) * (50 - 10) / (100 - 10)

def move_tripod(group, hip_angles, knee_pos):
    """
    Executes a tripod gait phase.
    Group A: Legs 1, 3, 5 (Pins 0,1; 4,5; 8,9)
    Group B: Legs 2, 4, 6 (Pins 2,3; 6,7; 10,11)
    """
    active_knees = [0, 4, 8] if group == 'A' else [2, 6, 10]
    idle_knees = [2, 6, 10] if group == 'A' else [0, 4, 8]
    
    # 1. ENSURE IDLE LEGS ARE DOWN: This prevents the "all legs up" floating issue.
    for i in idle_knees:
        set_angle(i, KNEE_LOWERED)
    
    # 2. LIFT: Lift the active tripod group
    for i in active_knees:
        set_angle(i, KNEE_LIFTED)
    time.sleep(STEP_DELAY)
    
    # 3. SWING: Move active hips to the commanded forward/backward/turn angle
    for i, angle in zip(active_knees, hip_angles):
        set_angle(i + 1, angle)
    time.sleep(STEP_DELAY)
    
    # 4. LOWER: Place the active legs back on the ground
    for i in active_knees:
        set_angle(i, knee_pos)
    time.sleep(STEP_DELAY)
    
    # 5. PUSH: Return hips to neutral while grounded to propel the body
    for i in active_knees:
        set_angle(i + 1, HIP_NEUTRAL)
    time.sleep(SETTLE_DELAY)

# ============================================================================
# Gait Directions
# ============================================================================

def forward(amplitude):
    swing = amplitude_to_swing(amplitude)
    fwd = HIP_NEUTRAL - swing
    move_tripod('A', [fwd, fwd, fwd], KNEE_LOWERED)
    move_tripod('B', [fwd, fwd, fwd], KNEE_LOWERED - 5)

def backward(amplitude):
    swing = amplitude_to_swing(amplitude)
    back = HIP_NEUTRAL + swing
    move_tripod('A', [back, back, back], KNEE_LOWERED)
    move_tripod('B', [back, back, back], KNEE_LOWERED)

def turn_right(amplitude):
    swing = amplitude_to_swing(amplitude)
    fwd = HIP_NEUTRAL - swing
    back = HIP_NEUTRAL + swing
    # Tripod A: Leg 1(L) fwd, 3(R) fwd, 5(L) back
    move_tripod('A', [fwd, fwd, back], KNEE_LOWERED)
    # Tripod B: Leg 2(R) fwd, 4(L) back, 6(R) back
    move_tripod('B', [fwd, back, back], KNEE_LOWERED)

def turn_left(amplitude):
    swing = amplitude_to_swing(amplitude)
    fwd = HIP_NEUTRAL - swing
    back = HIP_NEUTRAL + swing
    # Tripod A: Leg 1(L) back, 3(R) back, 5(L) fwd
    move_tripod('A', [back, back, fwd], KNEE_LOWERED)
    # Tripod B: Leg 2(R) back, 4(L) fwd, 6(R) fwd
    move_tripod('B', [back, fwd, fwd], KNEE_LOWERED)

# ============================================================================
# Main Terminal Control Loop
# ============================================================================
if __name__ == "__main__":
    stand_up()
    print("\n--- Hexapod Controller Ready ---")
    print("Format: 'CMD:AMP' (e.g., 1:80)")
    print("1: Forward | 2: Turn Right | 3: Turn Left | 4: Backward")
    
    try:
        while True:
            user_input = input("\nCommand: ").strip()
            if not user_input: continue
            
            parts = user_input.split(':')
            cmd = parts[0]
            amp = int(parts[1]) if len(parts) > 1 else 50
            amp = max(10, min(100, amp))

            if cmd == "1":
                print(f"Forward at {amp}% amplitude")
                forward(amp)
            elif cmd == "2":
                print(f"Right Turn at {amp}% amplitude")
                turn_right(amp)
            elif cmd == "3":
                print(f"Left Turn at {amp}% amplitude")
                turn_left(amp)
            elif cmd == "4":
                print(f"Backward at {amp}% amplitude")
                backward(amp)
            else:
                print("Unknown Command. Use 1, 2, 3, or 4.")
                
    except KeyboardInterrupt:
        print("\nShutting down. Moving to neutral...")
        stand_up()
