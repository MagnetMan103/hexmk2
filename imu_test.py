import serial
import time

# Open the serial port
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)

# These are the official Quectel LC29H(DA) commands with verified checksums
cmds = [
    # Variant 1: Try Port 0 instead of Port 1
    b'$PQTMCFGMSGOUT,PQTMIMU,0,1*29\r\n',
    
    # Variant 2: Ask the module what sensors it actually detects
    b'$PQTMIMUTYPE*43\r\n'
]

print("--- Sending Configuration ---")
for cmd in cmds:
    print(f"Sending: {cmd.decode().strip()}")
    ser.write(cmd)
    time.sleep(0.5)

print("\n--- Listening for IMU Data ---")
try:
    while True:
        line = ser.readline().decode('ascii', errors='replace').strip()
        if "PQTM" in line:
            print(f"GOT DATA: {line}")
        elif "GGA" in line and ",1," in line:
            print("Status: GPS Fix established.")
except KeyboardInterrupt:
    ser.close()
