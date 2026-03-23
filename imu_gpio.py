import smbus2
import time

# MPU6050 Default I2C address
DEVICE_ADDRESS = 0x68 

# MPU6050 Register Addresses
PWR_MGMT_1   = 0x6B
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H  = 0x43

def init_imu(bus):
    # Wake up the MPU6050 as it starts in sleep mode
    bus.write_byte_data(DEVICE_ADDRESS, PWR_MGMT_1, 0)
    print("IMU Initialized.")

def read_raw_data(bus, addr):
    # Accelerometer and Gyro data are 16-bit (two 8-bit registers)
    high = bus.read_byte_data(DEVICE_ADDRESS, addr)
    low = bus.read_byte_data(DEVICE_ADDRESS, addr + 1)
    
    # Combine high and low bytes
    value = ((high << 8) | low)
    
    # Convert to signed 16-bit value
    if value > 32768:
        value = value - 65536
    return value

def main():
    # Jetson Nano/Orin usually uses I2C bus 1
    bus_number = 1 
    try:
        bus = smbus2.SMBus(bus_number)
        init_imu(bus)
    except Exception as e:
        print(f"Could not open I2C bus {bus_number}: {e}")
        return

    print("Reading IMU data... Press Ctrl+C to stop.")
    
    try:
        while True:
            # Read Accelerometer
            acc_x = read_raw_data(bus, ACCEL_XOUT_H)
            acc_y = read_raw_data(bus, ACCEL_XOUT_H + 2)
            acc_z = read_raw_data(bus, ACCEL_XOUT_H + 4)

            # Read Gyroscope
            gyro_x = read_raw_data(bus, GYRO_XOUT_H)
            gyro_y = read_raw_data(bus, GYRO_XOUT_H + 2)
            gyro_z = read_raw_data(bus, GYRO_XOUT_H + 4)

            print(f"ACCEL: X:{acc_x:6} Y:{acc_y:6} Z:{acc_z:6} | GYRO: X:{gyro_x:6} Y:{gyro_y:6} Z:{gyro_z:6}")
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    finally:
        bus.close()

if __name__ == "__main__":
    main()
