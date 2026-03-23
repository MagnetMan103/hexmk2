import serial
import pynmea2
import math

# --- Configuration ---
PORT = "/dev/ttyUSB0"
BAUD = 115200

# Constants for coordinate to meter conversion
EARTH_RADIUS = 6378137.0  # meters

def get_meters_offset(lat1, lon1, lat2, lon2):
    """
    Calculates the X (East) and Y (North) offset in meters 
    from a reference point (lat1, lon1) to a target (lat2, lon2).
    """
    # Convert latitude to radians for the cosine correction
    lat_rad = math.radians(lat1)
    
    # Delta degrees to delta meters
    # 1 degree of latitude is ~111,111 meters
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    
    y_offset = delta_lat * (math.pi / 180.0) * EARTH_RADIUS
    x_offset = delta_lon * (math.pi / 180.0) * EARTH_RADIUS * math.cos(lat_rad)
    
    return x_offset, y_offset

def main():
    initial_pos = None
    
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        print(f"Connected to {PORT}. Waiting for GPS Fix...")

        while True:
            line = ser.readline().decode('utf-8', errors='ignore')
            
            # We use GNGGA because it has the best fix/satellite data
            if line.startswith('$GNGGA'):
                try:
                    msg = pynmea2.parse(line)
                    
                    # Check if we have valid data (Fix quality > 0)
                    if msg.gps_qual > 0:
                        curr_lat = msg.latitude
                        curr_lon = msg.longitude
                        
                        # Set the start point if this is our first valid fix
                        if initial_pos is None:
                            initial_pos = (curr_lat, curr_lon)
                            print("\n--- INITIAL POSITION LOCKED ---")
                            print(f"Lat: {curr_lat:.6f}, Lon: {curr_lon:.6f}\n")
                        
                        # Calculate offset in meters
                        off_x, off_y = get_meters_offset(initial_pos[0], initial_pos[1], curr_lat, curr_lon)
                        distance = math.sqrt(off_x**2 + off_y**2)

                        # Clean, readable output
                        print(f"Sats: {msg.num_sats:2} | "
                              f"X: {off_x:7.2f}m | Y: {off_y:7.2f}m | "
                              f"Dist: {distance:7.2f}m", end='\r')
                    else:
                        print("Searching for satellites...", end='\r')
                        
                except pynmea2.ParseError:
                    continue

    except KeyboardInterrupt:
        print("\nStopping Tracker...")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
