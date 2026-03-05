import sys
import time
import signal

#set custom module path
sys.path.append('/home/pi/oasis-rpi')

from utils import concurrent_state as cs
from networking import db_tools as dbt
from utils import error_handler as err

resource_name = "listener"

def update_synced_fields():
    cloud_device = dbt.fetch_device_data(cs.structs["access_config"])

    device_state_fields = list(cs.structs["device_state"].keys())
    control_params_fields = list(cs.structs["control_params"].keys())
    hardware_config_groups = list(cs.structs["hardware_config"].keys())
    #note: we do not log feaure toggles, as these are updated by the cloud in a controlled interval   

    device_state_dict = {} #dict of keys and values
    control_params_dict = {} #dict of keys and values
    hardware_config_dicts= {} #dict of dicts with groups, keys, and values

    #loop through all device data
    for k,v in cloud_device.items():
        #print("Listener: writing " + str(v) + " to " + str(k))

        payload = {k: v}

        if (k in device_state_fields) & (k != "connected"):
            payload = {k: v} #add a timestamp
            device_state_dict.update(payload)
        elif k in control_params_fields:
            payload = {k: v} #add a timestamp
            control_params_dict.update(payload)
        elif k in hardware_config_groups:
            payload = {k: v} #add a timestamp
            hardware_config_dicts.update(payload)
        else:
            continue

        #time.sleep(0.1) #just do this as quickly as possible

    #write the assembled dicts to memory, outside of the loop
    cs.write_dict("/home/pi/oasis-rpi/configs/device_state.json", device_state_dict)
    cs.write_dict("/home/pi/oasis-rpi/configs/control_params.json", control_params_dict)
    for group, dictionary in hardware_config_dicts.items():
        cs.write_nested_dict("/home/pi/oasis-rpi/configs/hardware_config.json", group, dictionary)

    print("Successfully synced state with cloud!")

if __name__ == "__main__":
    cs.check_lock(resource_name)
    signal.signal(signal.SIGTERM, cs.wrapped_sys_exit)
    print("Database listener activated.")
    try:
        cs.load_state()
        #sign the user in
        user, db, storage = dbt.initialize_user(cs.structs["access_config"]["refresh_token"])
        #fetch all the most recent data from the database & patch the listener
        
        listener_timer = time.time()-30
        
        while True:
            if (time.time() - listener_timer) > 30:
                update_synced_fields()
                listener_timer = time.time()
            else:
                time.sleep(1)
    except SystemExit:
        print("Terminating listener...")
    except KeyboardInterrupt:
        print("Listener was interrupted...")    
    except Exception:
        print(err.full_stack())
        print("Listener encountered an error!")
    finally:
        print("Database listener deactivated.")
        cs.rusty_pipes.unlock(cs.lock_filepath, resource_name)
        
        