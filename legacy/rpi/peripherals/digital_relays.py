#OS libraries
import sys

#Time libraries
import time
import datetime

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

from utils import concurrent_state as cs
from utils import error_handler as err
from utils import physics

#import rusty_pins and initialize GPIO pin from calling process
#pass in the rust pin object for scoping & resource management

def turn_on(output, switch_mode = "momentary", normal_state = "open", latch_pulse_width = 1):
    if switch_mode == "momentary":
        if normal_state == "open":
            output.set_high()
        if normal_state == "closed":
            output.set_low()
    if switch_mode == "latching": #this is going to be the same whether our switch is NO or NC
        output.set_high() #assumes the latch itself is NO
        time.sleep(latch_pulse_width)
        output.set_low()

def turn_off(output, switch_mode = "momentary", normal_state = "open", latch_pulse_width = 1):
    if switch_mode == "momentary":
        if normal_state == "open":
            output.set_low()
        if normal_state == "closed":
            output.set_high()
    if switch_mode == "latching":
        output.set_high()
        time.sleep(latch_pulse_width)
        output.set_low()

def actuate_time_hod(output, time_on = 0, time_off = 0, interval = 1, interval_units = "minutes", wattage = "0", log = None): #updates every 20 minutes by default 
    
    if interval_units == "seconds":
        time_active = interval
    if interval_units == "minutes":
        time_active = interval*60
    if interval_units == "hours":
        time_active = interval*60**2
    if interval_units == "days":
        time_active = interval*24*60**2 #everything must be passed to sleep in seconds, thats why we convert it
    
    time_inactive = time_active #we make a time_inactive variable just for clarity-sake when calling time.sleep after pin i/o

    now = datetime.datetime.now()
    HoD = now.hour

    if time_on < time_off:
        if HoD >= time_on and HoD < time_off:
            turn_on(output) #light on (relay closed)
            time.sleep(time_active)
            if log is not None:
                cs.write_state("/home/pi/oasis-rpi/configs/power_data.json", log, str(float(cs.structs["power_data"][log])+ physics.kwh(float(wattage),float(time_active))))
        if HoD < time_on or HoD >= time_off:
            turn_off(output)
            time.sleep(time_inactive)
    if time_on > time_off:
        if HoD >=  time_on or HoD < time_off:
            turn_on(output) #light on (relay closed)
            time.sleep(time_active)
            if log is not None:
                cs.write_state("/home/pi/oasis-rpi/configs/power_data.json", log, str(float(cs.structs["power_data"][log])+ physics.kwh(float(wattage),float(time_active))))
        if HoD < time_on and  HoD >= time_off:
            turn_off(output) #light on (relay closed)
            time.sleep(time_inactive)
    if time_on == time_off:
        turn_on(output)
        time.sleep(time_active)
        if log is not None:
            cs.write_state("/home/pi/oasis-rpi/configs/power_data.json", log, str(float(cs.structs["power_data"][log])+ physics.kwh(float(wattage),float(time_active))))

def actuate_interval_sleep(output, duration = 15, sleep = 45, duration_units = "seconds", sleep_units = "seconds", wattage = "0", log = None):
    
    if duration_units == "seconds":
        time_active = duration
    if duration_units == "minutes":
        time_active = duration * 60
    if duration_units == "hours":
        time_active = duration * 60 ** 2
    if duration_units == "days":
        time_active = duration * 24 * 60 ** 2

    if sleep_units == "seconds":
        time_sleep = sleep
    if sleep_units == "minutes":
        time_sleep = sleep * 60
    if sleep_units == "hours":
        time_sleep = sleep * 60 ** 2
    if sleep_units == "days":
        time_sleep = sleep * 24 * 60 ** 2

    turn_on(output)
    time.sleep(time_active) #set seconds to minutes
    if log is not None:
            cs.write_state("/home/pi/oasis-rpi/configs/power_data.json", log, str(physics.kwh(float(wattage),float(time_active))))
    
    turn_off(output)
    time.sleep(time_sleep)
    
def actuate_slow_pwm(output, intensity: int, pulse_domain = 10.0, wattage = "0", log = None):
    time_active = intensity/100 * pulse_domain #the intensity is a no. between 0-100, representing % power
    time_off = pulse_domain - time_active #so the device time spent on is %power * pulse domain (secs), off is domain -on  

    if (intensity >= 0) and (intensity < 1):
        turn_off(output) #off
        time.sleep(time_off)

    if (intensity >= 1) and (intensity < 99):
        turn_on(output)
        time.sleep(time_active) #on
        if log is not None:
            cs.write_state("/home/pi/oasis-rpi/configs/power_data.json", log, str(physics.kwh(float(wattage),float(time_active))))
        turn_off(output)
        time.sleep(time_off) #off

    if (intensity > 99) and (intensity <= 100):
        turn_on(output)
        time.sleep(time_active) #on
        if log is not None:
            cs.write_state("/home/pi/oasis-rpi/configs/power_data.json", log, str(physics.kwh(float(wattage),float(time_active)))) 

if __name__ == "__main__":
    print("This is a unit test for relays physical I/O.")
    print("Watch the lights...")
    actuate_time_hod(pin = 14, interval=5)
    actuate_interval_sleep(pin = 14, duration = 5, sleep = 5)
    actuate_time_hod(pin = 14, interval=5)