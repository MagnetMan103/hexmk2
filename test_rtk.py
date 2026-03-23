"""
RTK GPS position logger using Quectel LC29H (on Waveshare RTK HAT)
with NYS NTRIP corrections via str2str.

Architecture:
  - ttyUSB0: NMEA output FROM the GPS  (Python reads this)
  - ttyUSB1: RTCM corrections INTO the GPS  (str2str writes this)

The two ports are completely separate so there's no resource conflict.

If your HAT only exposes one USB port, you can instead pipe corrections
to the GPS over I2C or the Pi's hardware UART — see README for details.
"""

import subprocess
import serial
import math
import time
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NMEA_PORT       = "/dev/ttyUSB0"   # UART1 — GPS sends NMEA sentences here
CORRECTION_PORT = "/dev/ttyUSB1"   # UART2 — str2str pushes RTCM corrections here
BAUD_RATE       = 115200

# Your approximate location (used by the VRS server to generate local corrections)
# Replace with your actual coordinates. Height is metres above ellipsoid.
APPROX_LAT    =  42.445
APPROX_LON    = -76.482
APPROX_HEIGHT =  400

NTRIP_USER    = "amunschy"
NTRIP_PASS    = "amunschy"
NTRIP_HOST    = "rtn.dot.ny.gov"
NTRIP_PORT    = 8080
NTRIP_MOUNT   = "net_msm_vrs"

# ---------------------------------------------------------------------------
# NTRIP connection via str2str
# ---------------------------------------------------------------------------

def start_ntrip():
    """
    Launch str2str in the background. It pulls RTCM corrections from the
    NYS NTRIP caster and forwards them to the GPS correction port.

    Note: -p supplies your approximate position so the VRS caster can
    synthesise a virtual reference station near you. Without it the
    VRS mount point will refuse the connection.
    """
    cmd = [
        "str2str",
        "-in",  f"ntrip://{NTRIP_USER}:{NTRIP_PASS}@{NTRIP_HOST}:{NTRIP_PORT}/{NTRIP_MOUNT}",
        "-out", f"serial://{CORRECTION_PORT.replace('/dev/', '')}:{BAUD_RATE}",
        "-p",   f"{APPROX_LAT}", f"{APPROX_LON}", f"{APPROX_HEIGHT}",
        "-n",   "1",      # retry once on disconnect
        "-t",   "3",      # 3-second timeout before retry
    ]
    print(f"Starting NTRIP corrections → {CORRECTION_PORT}")
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------------------
# NMEA helpers
# ---------------------------------------------------------------------------

def parse_gngga(sentence: str) -> dict | None:
    """
    Parse a $GNGGA sentence and return a dict with:
        fix_quality  (int)  — 0=none, 1=GPS, 2=DGPS, 4=RTK fixed, 5=RTK float
        lat          (float) — decimal degrees, positive = North
        lon          (float) — decimal degrees, negative = West
        altitude     (float) — metres above sea level

    Returns None if the sentence is malformed or has no fix.
    """
    parts = sentence.strip().split(",")

    if len(parts) < 10:
        return None

    try:
        fix_quality = int(parts[6]) if parts[6] else 0
    except ValueError:
        return None

    if fix_quality == 0 or not parts[2] or not parts[4]:
        return None

    try:
        # NMEA lat is DDMM.MMMM  →  DD + MM.MMMM/60
        raw_lat = parts[2]
        lat = float(raw_lat[:2]) + float(raw_lat[2:]) / 60
        if parts[3] == "S":
            lat = -lat

        # NMEA lon is DDDMM.MMMM  →  DDD + MM.MMMM/60
        raw_lon = parts[4]
        lon = float(raw_lon[:3]) + float(raw_lon[3:]) / 60
        if parts[5] == "W":
            lon = -lon

        altitude = float(parts[9]) if parts[9] else 0.0

    except (ValueError, IndexError):
        return None

    return {"fix_quality": fix_quality, "lat": lat, "lon": lon, "altitude": altitude}


FIX_LABELS = {
    0: "No fix",
    1: "GPS",
    2: "DGPS",
    4: "RTK Fixed  ✓",
    5: "RTK Float",
}

def describe_fix(quality: int) -> str:
    return FIX_LABELS.get(quality, f"Unknown ({quality})")


def meters_from_home(lat: float, lon: float, home_lat: float, home_lon: float) -> tuple[float, float]:
    """
    Convert an absolute lat/lon into metres relative to a home point.
    Returns (east_m, north_m).  Positive = East / North.

    Uses a flat-Earth approximation, accurate to < 1 mm over distances
    up to ~500 m at Ithaca's latitude.
    """
    north_m = (lat - home_lat) * 111_132.0
    east_m  = (lon - home_lon) * 111_132.0 * math.cos(math.radians(home_lat))
    return east_m, north_m


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    ntrip_proc = start_ntrip()

    # Give str2str a moment to open the port before we try to read NMEA
    time.sleep(2)

    try:
        ser = serial.Serial(NMEA_PORT, BAUD_RATE, timeout=1)
    except serial.SerialException as e:
        print(f"ERROR: Could not open {NMEA_PORT}: {e}")
        ntrip_proc.terminate()
        sys.exit(1)

    home_lat: float | None = None
    home_lon: float | None = None

    print(f"Reading NMEA from {NMEA_PORT}")
    print("Waiting for RTK Fixed (fix quality 4) before logging...")
    print("(You should see fix quality improve: 1 → 2 → 5 → 4)\n")

    try:
        while True:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("ascii", errors="replace").strip()

            if not line.startswith("$GNGGA"):
                continue

            fix = parse_gngga(line)
            if fix is None:
                continue

            quality = fix["fix_quality"]
            label   = describe_fix(quality)

            # Show progress even before RTK fixed so the user knows it's working
            if quality != 4:
                print(f"  Fix: {label} — waiting for RTK Fixed...")
                continue

            # First RTK-fixed reading becomes the home point
            if home_lat is None:
                home_lat = fix["lat"]
                home_lon = fix["lon"]
                print(f"\n  HOME LOCKED  {home_lat:.8f}°N  {abs(home_lon):.8f}°W  "
                      f"alt {fix['altitude']:.1f} m\n")

            east_m, north_m = meters_from_home(
                fix["lat"], fix["lon"], home_lat, home_lon
            )

            dist = math.sqrt(east_m**2 + north_m**2)
            print(
                f"[{label}]  "
                f"E {east_m:+.3f} m   N {north_m:+.3f} m   "
                f"dist {dist:.3f} m   alt {fix['altitude']:.1f} m"
            )

    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        ser.close()
        ntrip_proc.terminate()
        ntrip_proc.wait()
        print("Closed serial and NTRIP connection.")


if __name__ == "__main__":
    main()
