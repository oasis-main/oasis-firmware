#TODO replace this with a rust module
#import shell modules
import sys
import os

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')
sys.path.append('/home/pi/oasis-rpi/core')
sys.path.append('/home/pi/oasis-rpi/utils')

import serial

ser_in = None  #object for reading from the microcontroller via serial
ser_out = None #object for writing to the microcontroller via serial

#attempts connection to microcontroller
def start_serial_in(): #Depends on:'serial'
    global ser_in
    try:   
        try:
            ser_in = serial.Serial("/dev/ttyUSB0", 9600)
            print("Started serial communication with Arduino Nano.")  
        except:
            ser_in = serial.Serial("/dev/ttyACM0", 9600)
            print("Started serial communication with Arduino Uno.")
    except Exception as e:
        ser_in = None
        print("Serial connection not found")

#attempts connection to microcontroller
def start_serial_out(): #Depends on:'serial'; Modifies: ser_out
    global ser_out
    try:
        try:
            ser_out = serial.Serial("/dev/ttyUSB0", 9600, timeout=1)
            ser_out.flush()
            print("Started serial communication with Arduino Nano.")
        except:
            ser_out = serial.Serial("/dev/ttyACM0", 9600, timeout=1)
            ser_out.flush()
            print("Started serial communication with Arduino Uno.")
    except Exception as e:
        #print(str(e))
        ser_out = None
        print("Serial connection not found")