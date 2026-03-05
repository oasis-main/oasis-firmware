import sys
import smbus2

# Create a new SMBus instance on line 2
bus = smbus2.SMBus(1)  

def set_rtcm():
    # Device i2c write address
    device_address = 0x51

    # Register address
    register_address = 0x28

    # First, we need to read the current value of the register
    current_value = bus.read_byte_data(device_address, register_address)

    # Then, we need to clear the fourth bit (fifth from the left, little endian starting at 0)
    # We can do this by creating a mask where all bits are 1, except for the fourth bit, which is 0. 
    # Then, we use the bitwise AND operation to clear the fourth bit.
    mask = 0b11101111
    new_value = current_value & mask

    # Write the new value back to the register
    bus.write_byte_data(device_address, register_address, new_value)

if __name__ == "__main__":

    if sys.argv[1] == "set_rtcm":
        print("Setting RTCM on the RTC")
        set_rtcm()
    

