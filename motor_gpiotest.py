import time
import board
import busio
from adafruit_servokit import ServoKit

# Alan's correct initialization for Jetson Bus 0
try:
    # Initialize I2C on Pins 27 (SDA) and 28 (SCL)
    i2c = busio.I2C(board.SCL_1, board.SDA_1)
    
    # Initialize the HAT (address 0x41 assumes A0 jumper is bridged)
    kit = ServoKit(channels=16, i2c=i2c, address=0x41)
    
    # 35kg DSSERVO Configuration
    # Channel 0; using the 500-2500 range common for high-torque digital servos
    kit.servo[0].set_pulse_width_range(500, 2500)
    
    print("Initialization successful. Starting sweep on Channel 0...")

    while True:
        print("0 Degrees")
        kit.servo[0].angle = 50
        time.sleep(1.5)


except KeyboardInterrupt:
    print("\nTest stopped. Moving to neutral...")
    kit.servo[0].angle = 90
except Exception as e:
    print(f"Hardware Error: {e}")
    print("Double-check your A0 solder bridge and 5V-6V external power supply.")
