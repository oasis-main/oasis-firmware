#---------------------------------------------------------------------------------------
#Manages Hardware for Lighting
#---------------------------------------------------------------------------------------

#import shell modules
import sys
import signal
import time
 
#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

import rusty_pins
from peripherals import digital_relays
from utils import concurrent_state as cs
from utils import error_handler as err

resource_name = "air_pump"
cs.check_lock(resource_name)

#setup GPIO
cs.load_state()
air_GPIO = int(cs.structs["hardware_config"]["equipment_gpio_map"]["air_relay"]) #air pump pin pulls from config file
pin = rusty_pins.GpioOut(air_GPIO)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, cs.wrapped_sys_exit)
    try:
        while True:
            print("Turning air pump on at " + cs.structs["control_params"]["time_start_air"] + ":00 and off at " + cs.structs["control_params"]["time_stop_air"] + ":00, refreshing every " + cs.structs["control_params"]["air_interval"] + " minutes...")
            digital_relays.actuate_time_hod(pin, int(cs.structs["control_params"]["time_start_air"]), int(cs.structs["control_params"]["time_stop_air"]), int(cs.structs["control_params"]["air_interval"]), interval_units = "minutes", wattage=cs.structs["hardware_config"]["equipment_wattage"]["air_pump"], log="air_pump_kwh")
            cs.load_state() #no time recorded here because it is not on an interval
            time.sleep(1)
    except SystemExit: #This is handled by the relay as well when terminated from main
        print("Air pump was terminated.")
    except KeyboardInterrupt: #This is handled by the relay as well when terminated with keyboard
        print("Air pump was interrupted.")
    except Exception:
        print("Air pump encountered an error!")
        print(err.full_stack())
    finally:
        print("Shutting down air pump...")
        try:
            digital_relays.turn_off(pin)
        except:
            print(resource_name + " has no relay objects remaining.")
        
        cs.rusty_pipes.unlock(cs.lock_filepath, resource_name)


