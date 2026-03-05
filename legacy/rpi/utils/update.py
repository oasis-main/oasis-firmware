#This is an important file because it described the data structure of our program
#--Basically a bunch of nested dictionaries/hashmaps persisted in memory through json
#--Imports the basic concurrency modules, data structure reset modules
#--By using this file to track the architecture of our program,
#--we can decrease the probability of a bad release.   

#import modules
import sys
import json
import rusty_pipes

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

from utils import reset_model
from utils import concurrent_state as cs
from networking import db_tools as dbt

#get latest code from designated repository
def git_pull():
    gitpull = rusty_pipes.Open(["git", "pull"],"git_pull") #should be whatever branch the code was installed from
    gitpull.wait()

    print("Pulled most recent code changes from repository (you stayed on the original branch, defaults to the master)")

#save existing data into temps
def save_old_configs():
    savefeatures = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/configs/feature_toggles.json", "/home/pi/oasis-rpi/configs/feature_toggles_temp.json"],"cp")
    savefeatures.wait()
    
    savehardware = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/configs/hardware_config.json", "/home/pi/oasis-rpi/configs/hardware_config_temp.json"],"cp")
    savehardware.wait()

    saveaccess = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/configs/access_config.json", "/home/pi/oasis-rpi/configs/access_config_temp.json"],"cp")
    saveaccess.wait()

    savestate = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/configs/device_state.json", "/home/pi/oasis-rpi/configs/device_state_temp.json"],"cp")
    savestate.wait()

    saveparams = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/configs/control_params.json", "/home/pi/oasis-rpi/configs/control_params_temp.json"],"cp")
    saveparams.wait()

    savesensors = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/configs/sensor_data.json", "/home/pi/oasis-rpi/configs/sensor_data_temp.json"],"cp")
    savesensors.wait()

    savepower = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/configs/power_data.json", "/home/pi/oasis-rpi/configs/power_data_temp.json"],"cp")
    savepower.wait()

    print("Saved existing configs to temporary files")

#transfer compatible configs which we save before getting the new code and default files
def transfer_compatible_configs(config_path,temp_config_path):

    with open(config_path) as x: #get new format
        config = json.load(x)

    with open(temp_config_path) as x_temp: #get old data
        config_temp = json.load(x_temp)

    #persist old data into new format
    old_data_keys = list(config_temp.keys())
    new_format_keys = list(config.keys())
    common_keys = set(old_data_keys) & set(new_format_keys) #common ones between them
    new_keys = set(new_format_keys) - set(old_data_keys)

    #loop through common keys, change values to temp
    for key in common_keys:
        config[key] = config_temp[key]

    with open(config_path, "r+") as x: #write data to config
        x.seek(0)
        json.dump(config, x)
        x.truncate()
    
    cs.load_state()
    
    for key in new_keys:
        dbt.patch_firebase(cs.structs["access_config"], key, config[key])

    remove_temp = rusty_pipes.Open(["rm", temp_config_path],"rm")
    remove_temp.wait()

def get_update(test=False):
    print("Fetching over-the-air update...")
    git_pull()

    #back up the configs & state that can survive update
    save_old_configs()
    
    #reset all configs
    reset_model.reset_feature_toggles()
    reset_model.reset_hardware_config()
    reset_model.reset_access_config()
    reset_model.reset_device_state()
    reset_model.reset_control_params()
    reset_model.reset_sensor_data()
    reset_model.reset_power_data()

    transfer_compatible_configs('/home/pi/oasis-rpi/configs/feature_toggles.json', '/home/pi/oasis-rpi/configs/feature_toggles_temp.json')
    transfer_compatible_configs('/home/pi/oasis-rpi/configs/hardware_config.json', '/home/pi/oasis-rpi/configs/hardware_config_temp.json')
    transfer_compatible_configs('/home/pi/oasis-rpi/configs/access_config.json', '/home/pi/oasis-rpi/configs/access_config_temp.json')
    transfer_compatible_configs('/home/pi/oasis-rpi/configs/device_state.json', '/home/pi/oasis-rpi/configs/device_state_temp.json')
    transfer_compatible_configs('/home/pi/oasis-rpi/configs/control_params.json', '/home/pi/oasis-rpi/configs/control_params_temp.json')
    transfer_compatible_configs('/home/pi/oasis-rpi/configs/sensor_data.json', '/home/pi/oasis-rpi/configs/sensor_data_temp.json')
    transfer_compatible_configs('/home/pi/oasis-rpi/configs/power_data.json', '/home/pi/oasis-rpi/configs/power_data_temp.json')
    print("Transfered compatible state & configs, removing temporary files")

    #run external update commands
    sh_stage = rusty_pipes.Open(["sudo", "chmod" ,"+x", "/home/pi/oasis-rpi/setup_scripts/update_patch.sh"],"chmod")
    sh_stage.wait()

    sh_patch = rusty_pipes.Open(["sudo", "/home/pi/oasis-rpi/setup_scripts/update_patch.sh"],"patch")
    sh_patch.wait()

    #load state to get configs & state
    cs.load_state()

    #change awaiting_update to "O" in firebase and locally
    cs.write_state("/home/pi/oasis-rpi/configs/device_state.json", "awaiting_update", "0", db_writer = dbt.patch_firebase)

    print("Update complete.")

    if not test:
        #reboot
        print("Rebooting...")
        reboot = rusty_pipes.Open(["sudo", "systemctl", "reboot"],"reboot")
        reboot.wait()

if __name__ == '__main__':
    get_update()