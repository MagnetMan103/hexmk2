import serial
import time

# On Jetson, it usually shows up as /dev/ttyUSB0 if it's the only USB-serial device
port = "/dev/ttyUSB0" 
baud = 115200 # Default for LC29H(DA)

try:
    # Initialize serial connection
    ser = serial.Serial(port, baud, timeout=1)
    print(f"Connected to {port} at {baud} baud.")
    print("Waiting for data... (Make sure the antenna is connected and has a view of the sky)")

    while True:
        if ser.in_waiting > 0:
            # Read one line of NMEA data
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(line)
        time.sleep(0.1)

except serial.SerialException as e:
    print(f"Error: {e}")
except KeyboardInterrupt:
    print("\nStopping script...")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
