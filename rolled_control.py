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
    0: (100,550), 1: (180, 490),
    2: (80, 530), 3: (140, 460),
    4: (130, 580), 5: (130, 420),
    6: (80, 530),  7: (460, 150), # Reversed
    8: (80, 530), 9: (460, 150), # Reversed
    10: (570, 120), 11: (510, 200)  # Reversed
}

# Apply calibration and determine orientation
for pin, (val1, val2) in CALIBRATION_DATA.items():
    p_min = count_to_us(min(val1, val2))
    p_max = count_to_us(max(val1, val2))
    kit.servo[pin].set_pulse_width_range(p_min, p_max)

# Gait parameters
STEP_DELAY = 0.5  # og was 0.25 # Slightly faster for smoother tripod transitions
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
    set_angle(0, KNEE_LOWERED)
    set_angle(2, KNEE_LOWERED)
    set_angle(4, KNEE_LOWERED)
    time.sleep(1)
    set_angle(6, KNEE_LOWERED)
    set_angle(8, KNEE_LOWERED)
    set_angle(10, KNEE_LOWERED)
    time.sleep(1)
    
    # Move all hips to neutral
    set_angle(1, HIP_NEUTRAL)
    set_angle(3, HIP_NEUTRAL)
    set_angle(5, HIP_NEUTRAL)
    set_angle(7, HIP_NEUTRAL)
    set_angle(9, HIP_NEUTRAL)
    set_angle(11, HIP_NEUTRAL)
    time.sleep(0.5)

def amplitude_to_swing(amplitude):
    """Maps 10-100 amplitude to a 10-50 degree hip swing."""
    return 10 + (amplitude - 10) * (50 - 10) / (100 - 10)

# ============================================================================
# Explicit Gait Directions
# Group A: Legs 1, 3, 5 (Knee Pins: 0, 4, 8 | Hip Pins: 1, 5, 9)
# Group B: Legs 2, 4, 6 (Knee Pins: 2, 6, 10 | Hip Pins: 3, 7, 11)
# ============================================================================

def forward(amplitude):
    swing = amplitude_to_swing(amplitude)
    fwd = HIP_NEUTRAL - swing

    # === TRIPOD GROUP A ===
    # Ensure Group B is grounded
    set_angle(2, KNEE_LOWERED)
    set_angle(6, KNEE_LOWERED)
    set_angle(10, KNEE_LOWERED)

    set_angle(0, KNEE_LIFTED)  # leg 1 up
    set_angle(4, KNEE_LIFTED)  # leg 3 up
    set_angle(8, KNEE_LIFTED)  # leg 5 up
    time.sleep(STEP_DELAY)

    set_angle(1, fwd)  # rotate leg 1 forward
    set_angle(5, fwd)  # rotate leg 3 forward
    set_angle(9, fwd)  # rotate leg 5 forward
    time.sleep(STEP_DELAY)

    set_angle(0, KNEE_LOWERED - 5)  # leg 1 down
    set_angle(4, KNEE_LOWERED - 5)  # leg 3 down
    set_angle(8, KNEE_LOWERED - 5)  # leg 5 down
    time.sleep(STEP_DELAY)

    set_angle(1, HIP_NEUTRAL)  # rotate leg 1 back (power stroke)
    set_angle(5, HIP_NEUTRAL)  # rotate leg 3 back (power stroke)
    set_angle(9, HIP_NEUTRAL)  # rotate leg 5 back (power stroke)
    time.sleep(SETTLE_DELAY)

    # === TRIPOD GROUP B ===
    # Ensure Group A is grounded
    #set_angle(0, KNEE_LOWERED + 3)
    #set_angle(4, KNEE_LOWERED + 3)
    #set_angle(8, KNEE_LOWERED + 3)

    set_angle(2, KNEE_LIFTED)  # leg 2 up
    set_angle(6, KNEE_LIFTED)  # leg 4 up
    set_angle(10, KNEE_LIFTED) # leg 6 up
    time.sleep(STEP_DELAY)

    set_angle(3, fwd)  # rotate leg 2 forward
    set_angle(7, fwd)  # rotate leg 4 forward
    set_angle(11, fwd) # rotate leg 6 forward
    time.sleep(STEP_DELAY)

    # Offset for better ground contact specifically on Group B
    set_angle(2, KNEE_LOWERED - 5)  # leg 2 down
    set_angle(6, KNEE_LOWERED - 5)  # leg 4 down
    set_angle(10, KNEE_LOWERED - 5) # leg 6 down
    time.sleep(STEP_DELAY)

    set_angle(3, HIP_NEUTRAL)  # rotate leg 2 back (power stroke)
    set_angle(7, HIP_NEUTRAL)  # rotate leg 4 back (power stroke)
    set_angle(11, HIP_NEUTRAL) # rotate leg 6 back (power stroke)
    time.sleep(SETTLE_DELAY)


def backward(amplitude):
    swing = amplitude_to_swing(amplitude)
    back = HIP_NEUTRAL + swing

    # === TRIPOD GROUP A ===
    #set_angle(2, KNEE_LOWERED)
    #set_angle(6, KNEE_LOWERED)
    #set_angle(10, KNEE_LOWERED)

    set_angle(0, KNEE_LIFTED)  # leg 1 up
    set_angle(4, KNEE_LIFTED)  # leg 3 up
    set_angle(8, KNEE_LIFTED)  # leg 5 up
    time.sleep(STEP_DELAY)

    set_angle(1, back)  # rotate leg 1 backward
    set_angle(5, back)  # rotate leg 3 backward
    set_angle(9, back)  # rotate leg 5 backward
    time.sleep(STEP_DELAY)

    set_angle(0, KNEE_LOWERED)  # leg 1 down
    set_angle(4, KNEE_LOWERED)  # leg 3 down
    set_angle(8, KNEE_LOWERED)  # leg 5 down
    time.sleep(STEP_DELAY)

    set_angle(1, HIP_NEUTRAL)  # rotate leg 1 forward (power stroke)
    set_angle(5, HIP_NEUTRAL)  # rotate leg 3 forward (power stroke)
    set_angle(9, HIP_NEUTRAL)  # rotate leg 5 forward (power stroke)
    time.sleep(SETTLE_DELAY)

    # === TRIPOD GROUP B ===
    #set_angle(0, KNEE_LOWERED)
    #set_angle(4, KNEE_LOWERED)
    #set_angle(8, KNEE_LOWERED)

    set_angle(2, KNEE_LIFTED)  # leg 2 up
    set_angle(6, KNEE_LIFTED)  # leg 4 up
    set_angle(10, KNEE_LIFTED) # leg 6 up
    time.sleep(STEP_DELAY)

    set_angle(3, back)  # rotate leg 2 backward
    set_angle(7, back)  # rotate leg 4 backward
    set_angle(11, back) # rotate leg 6 backward
    time.sleep(STEP_DELAY)

    set_angle(2, KNEE_LOWERED)  # leg 2 down
    set_angle(6, KNEE_LOWERED)  # leg 4 down
    set_angle(10, KNEE_LOWERED) # leg 6 down
    time.sleep(STEP_DELAY)

    set_angle(3, HIP_NEUTRAL)  # rotate leg 2 forward (power stroke)
    set_angle(7, HIP_NEUTRAL)  # rotate leg 4 forward (power stroke)
    set_angle(11, HIP_NEUTRAL) # rotate leg 6 forward (power stroke)
    time.sleep(SETTLE_DELAY)


def turn_right(amplitude):
    swing = amplitude_to_swing(amplitude)
    fwd = HIP_NEUTRAL - swing
    back = HIP_NEUTRAL + swing

    # === TRIPOD GROUP A ===
    set_angle(2, KNEE_LOWERED)
    set_angle(6, KNEE_LOWERED)
    set_angle(10, KNEE_LOWERED)

    set_angle(0, KNEE_LIFTED)  # leg 1 up
    set_angle(4, KNEE_LIFTED)  # leg 3 up
    set_angle(8, KNEE_LIFTED)  # leg 5 up
    time.sleep(STEP_DELAY)

    set_angle(1, fwd)   # rotate leg 1(L) forward
    set_angle(5, fwd)   # rotate leg 3(R) forward
    set_angle(9, back)  # rotate leg 5(L) backward
    time.sleep(STEP_DELAY)

    set_angle(0, KNEE_LOWERED)  # leg 1 down
    set_angle(4, KNEE_LOWERED)  # leg 3 down
    set_angle(8, KNEE_LOWERED)  # leg 5 down
    time.sleep(STEP_DELAY)

    set_angle(1, HIP_NEUTRAL)  # power stroke
    set_angle(5, HIP_NEUTRAL)  # power stroke
    set_angle(9, HIP_NEUTRAL)  # power stroke
    time.sleep(SETTLE_DELAY)

    # === TRIPOD GROUP B ===
    #set_angle(0, KNEE_LOWERED)
    #set_angle(4, KNEE_LOWERED)
    #set_angle(8, KNEE_LOWERED)

    set_angle(2, KNEE_LIFTED)  # leg 2 up
    set_angle(6, KNEE_LIFTED)  # leg 4 up
    set_angle(10, KNEE_LIFTED) # leg 6 up
    time.sleep(STEP_DELAY)

    set_angle(3, fwd)   # rotate leg 2(R) forward
    set_angle(7, back)  # rotate leg 4(L) backward
    set_angle(11, back) # rotate leg 6(R) backward
    time.sleep(STEP_DELAY)

    set_angle(2, KNEE_LOWERED - 5)  # leg 2 down
    set_angle(6, KNEE_LOWERED - 5)  # leg 4 down
    set_angle(10, KNEE_LOWERED - 5) # leg 6 down
    time.sleep(STEP_DELAY)

    set_angle(3, HIP_NEUTRAL)  # power stroke
    set_angle(7, HIP_NEUTRAL)  # power stroke
    set_angle(11, HIP_NEUTRAL) # power stroke
    time.sleep(SETTLE_DELAY)


def turn_left(amplitude):
    swing = amplitude_to_swing(amplitude)
    fwd = HIP_NEUTRAL - swing
    back = HIP_NEUTRAL + swing

    # === TRIPOD GROUP A ===
    set_angle(2, KNEE_LOWERED)
    set_angle(6, KNEE_LOWERED)
    set_angle(10, KNEE_LOWERED)

    set_angle(0, KNEE_LIFTED)  # leg 1 up
    set_angle(4, KNEE_LIFTED)  # leg 3 up
    set_angle(8, KNEE_LIFTED)  # leg 5 up
    time.sleep(STEP_DELAY)

    set_angle(1, back)  # rotate leg 1(L) backward
    set_angle(5, back)  # rotate leg 3(R) backward
    set_angle(9, fwd)   # rotate leg 5(L) forward
    time.sleep(STEP_DELAY)

    set_angle(0, KNEE_LOWERED)  # leg 1 down
    set_angle(4, KNEE_LOWERED)  # leg 3 down
    set_angle(8, KNEE_LOWERED)  # leg 5 down
    time.sleep(STEP_DELAY)

    set_angle(1, HIP_NEUTRAL)  # power stroke
    set_angle(5, HIP_NEUTRAL)  # power stroke
    set_angle(9, HIP_NEUTRAL)  # power stroke
    time.sleep(SETTLE_DELAY)

    # === TRIPOD GROUP B ===
    #set_angle(0, KNEE_LOWERED)
    #set_angle(4, KNEE_LOWERED)
    #set_angle(8, KNEE_LOWERED)

    set_angle(2, KNEE_LIFTED)  # leg 2 up
    set_angle(6, KNEE_LIFTED)  # leg 4 up
    set_angle(10, KNEE_LIFTED) # leg 6 up
    time.sleep(STEP_DELAY)

    set_angle(3, back)  # rotate leg 2(R) backward
    set_angle(7, fwd)   # rotate leg 4(L) forward
    set_angle(11, fwd)  # rotate leg 6(R) forward
    time.sleep(STEP_DELAY)

    set_angle(2, KNEE_LOWERED)  # leg 2 down
    set_angle(6, KNEE_LOWERED)  # leg 4 down
    set_angle(10, KNEE_LOWERED) # leg 6 down
    time.sleep(STEP_DELAY)

    set_angle(3, HIP_NEUTRAL)  # power stroke
    set_angle(7, HIP_NEUTRAL)  # power stroke
    set_angle(11, HIP_NEUTRAL) # power stroke
    time.sleep(SETTLE_DELAY)

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
