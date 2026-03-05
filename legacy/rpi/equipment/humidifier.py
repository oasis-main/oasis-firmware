#---------------------------------------------------------------------------------------
#Manages Hardware for Humidity
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
from networking import db_tools as dbt

resource_name = "humidifier"
cs.check_lock(resource_name)

#setup GPIO
cs.load_state() #get configs
hum_GPIO = int(cs.structs["hardware_config"]["equipment_gpio_map"]["humidifier_relay"]) #heater pin pulls from config file
pin = rusty_pins.GpioOut(hum_GPIO)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, cs.wrapped_sys_exit)
    try:
        while True:
            if cs.structs["feature_toggles"]["hum_pid"] == "1":
                print("Running humidifier in pulse mode with " + cs.structs["control_params"]["hum_feedback"] + "%" + " power...")
                digital_relays.actuate_slow_pwm(pin, float(cs.structs["control_params"]["hum_feedback"]), wattage=cs.structs["hardware_config"]["equipment_wattage"]["humidifier"], log="humidifier_kwh") #trigger appropriate response
            else:
                print("Running humidifier for " + cs.structs["control_params"]["humidifier_duration"] + " minute(s) on, " + cs.structs["control_params"]["humidifier_interval"] + " minute(s) off...")
                if (time.time() - float(cs.structs["control_params"]["last_humidifier_run_time"])) > (float(cs.structs["control_params"]["humidifier_interval"])*60): #convert setting units (minutes) to base (seconds)
                    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "last_humidifier_run_time", str(time.time()), db_writer = dbt.patch_firebase)
                    digital_relays.actuate_interval_sleep(pin, float(cs.structs["control_params"]["humidifier_duration"]), float(cs.structs["control_params"]["humidifier_interval"]), duration_units= "minutes", sleep_units="minutes", wattage=cs.structs["hardware_config"]["equipment_wattage"]["humidifier"], log="humidifier_kwh")
            cs.load_state()
            time.sleep(1)
    except SystemExit:
        print("Humidifier was terminated.")
    except KeyboardInterrupt:
        print("Humidifier was interrupted.")
    except Exception:    
        print("Humidifier ncountered an error!")
        print(err.full_stack())
    finally:
        print("Shutting down humidifier...")
        try:
            digital_relays.turn_off(pin)
        except:
            print(resource_name + " has no relay objects remaining.")
        
        cs.rusty_pipes.unlock(cs.lock_filepath, resource_name)