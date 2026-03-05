#---------------------------------------------------------------------------------------
#Manages Hardware for Lighting
#---------------------------------------------------------------------------------------

#import shell modules
import sys
import signal
import time

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi)
 
import rusty_pins
from peripherals import relays
from utils import concurrent_state as cs
from utils import error_handler as err

resource_name = "lights"
cs.check_lock(resource_name)

#get configs
cs.load_state()
light_GPIO = int(cs.structs["hardware_config"]["equipment_gpio_map"]["light_relay"]) #lights pin pulls from config file
pin = rusty_pins.GpioOut(light_GPIO)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, cs.wrapped_sys_exit)
    try:
        while True:
            print("Turning lights on at " + cs.structs["control_params"]["time_start_light"] + ":00 and off at " + cs.structs["control_params"]["time_stop_light"] + ":00, refreshing every " + cs.structs["control_params"]["lighting_interval"] + " minutes...")
            relays.actuate_time_hod(pin, int(cs.structs["control_params"]["time_start_light"]), int(cs.structs["control_params"]["time_stop_light"]), int(cs.structs["control_params"]["lighting_interval"]), interval_units = "minutes", wattage=cs.structs["hardware_config"]["equipment_wattage"]["lights"], log="lights_kwh")
            cs.load_state() #no time logging since we're just working with hours of the day here
            time.sleep(1)
    except SystemExit:
        print("Lights were terminated.")
    except KeyboardInterrupt:
        print("Lights were interrupted.")
    except Exception:
        print("Lights encountered an error!")
        print(err.full_stack())
    finally:
        print("Shutting down lights...")
        try:
            relays.turn_off(pin)
        except:
            print(resource_name + " has no relay objects remaining.")
        
        cs.rusty_pipes.unlock(cs.lock_filepath, resource_name)

