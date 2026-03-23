#!/usr/bin/env python3
import socket
import sys
import base64
import time
import serial
import math
from pynmeagps import NMEAReader

# --- CONFIGURATION ---
CASTER = "rtn.dot.ny.gov"
PORT = 8080
MOUNTPOINT = "/net_msm_vrs"
USER = "amunschy"
PASS = "amunschy"
SERIAL_DEV = "/dev/ttyUSB0"
BAUD = 115200

# Ithaca-specific conversion (Meters per degree)
LAT_M = 111132
LON_M = 82190

class HexapodTracker:
    def __init__(self):
        try:
            self.ser = serial.Serial(SERIAL_DEV, BAUD, timeout=0.1)
            self.nmr = NMEAReader(self.ser)
        except Exception as e:
            print(f"Serial Error: {e}. Check if /dev/ttyUSB0 is plugged in.")
            sys.exit(1)
            
        self.socket = None
        self.home_lat = None
        self.home_lon = None
        
        # Auth header
        auth_str = f"{USER}:{PASS}"
        self.auth = base64.b64encode(auth_str.encode()).decode()

    def get_mount_header(self):
        header = (
            f"GET {MOUNTPOINT} HTTP/1.0\r\n"
            f"User-Agent: NTRIP PythonClient\r\n"
            f"Authorization: Basic {self.auth}\r\n"
            f"Connection: close\r\n\r\n"
        )
        return header.encode()

    def get_current_gga(self):
        """Reads GPS hardware for a GGA string to send to NYSNet."""
        start_time = time.time()
        while time.time() - start_time < 3:
            (raw, parsed) = self.nmr.read()
            if parsed and parsed.msgID == "GGA":
                return raw
        # Fallback if GPS hasn't sent a string yet (Riley Robb coordinates)
        return b"$GNGGA,201513.00,4226.70,N,07628.92,W,1,12,1.0,280.0,M,0.0,M,,*72\r\n"

    def run(self):
        try:
            print(f"Connecting to {CASTER}...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((CASTER, PORT))
            self.socket.sendall(self.get_mount_header())
            
            # Initial handshake to wake up the VRS server
            self.socket.sendall(self.get_current_gga())

            print("--- Live Tracking Started ---")
            print("Zeroing on first available fix...")
            
            while True:
                # 1. Corrections: Internet -> GPS Hardware
                try:
                    self.socket.setblocking(False)
                    corrections = self.socket.recv(2048)
                    if corrections:
                        self.ser.write(corrections)
                except (BlockingIOError, socket.error):
                    pass

                # 2. Position: GPS Hardware -> Python Math
                (raw, parsed) = self.nmr.read()
                if parsed and parsed.msgID == "GGA":
                    lat, lon = parsed.lat, parsed.lon
                    quality = parsed.quality
                    
                    # Any quality > 0 means we have a position
                    if quality > 0:
                        if self.home_lat is None:
                            self.home_lat, self.home_lon = lat, lon
                            print(f"\n[START POINT SET] @ {lat}, {lon}")
                        
                        # Relative Position Calculation
                        # dy = North/South meters, dx = East/West meters
                        dy = (lat - self.home_lat) * LAT_M
                        dx = (lon - self.home_lon) * LON_M
                        
                        status_name = {1:"GPS", 2:"DGPS", 4:"FIXED", 5:"FLOAT"}.get(quality, "???")
                        
                        # Formatting output for the terminal
                        print(f"X: {dx:+.3f}m | Y: {dy:+.3f}m | Status: {quality} ({status_name})    ", end='\r')

                # 3. NYSNet Heartbeat (every 10s)
                if int(time.time()) % 10 == 0:
                    try:
                        self.socket.sendall(self.get_current_gga())
                    except:
                        pass

        except KeyboardInterrupt:
            print("\nShutting down hexapod tracker...")
        finally:
            if self.socket: self.socket.close()
            self.ser.close()

if __name__ == "__main__":
    HexapodTracker().run()
