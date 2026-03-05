import os
import sys
import rusty_pipes
from subprocess import Popen

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')
sys.path.append('/usr/lib/python37.zip')
sys.path.append('/usr/lib/python3.7')
sys.path.append('/usr/lib/python3.7/lib-dynload')
sys.path.append('/home/pi/.local/lib/python3.7/site-packages')
sys.path.append('/usr/local/lib/python3.7/dist-packages')
sys.path.append('/usr/lib/python3/dist-packages')

#all functions depend on subprocess module
def reset_device_state():
    reset_d = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/defaults/device_state_default_template.json", "/home/pi/oasis-rpi/configs/device_state.json"],"cp")
    reset_d.wait()

def reset_control_params():
    reset_c = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/defaults/control_params_default_template.json", "/home/pi/oasis-rpi/configs/control_params.json"],"cp")
    reset_c.wait()
    
def reset_sensor_data():
    reset_s = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/defaults/sensor_data_default_template.json", "/home/pi/oasis-rpi/configs/sensor_data.json"],"cp")
    reset_s.wait()

def reset_access_config():
    reset_a = rusty_pipes.Open([ "cp", "/home/pi/oasis-rpi/defaults/access_config_default_template.json", "/home/pi/oasis-rpi/configs/access_config.json"],"cp")
    reset_a.wait()

def reset_hardware_config():
    reset_h = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/defaults/hardware_config_default_template.json", "/home/pi/oasis-rpi/configs/hardware_config.json"],"cp")
    reset_h.wait()

def reset_feature_toggles():
    reset_f = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/defaults/feature_toggles_default_template.json", "/home/pi/oasis-rpi/configs/feature_toggles.json"],"cp")
    reset_f.wait()

def reset_power_data():
    reset_p = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/defaults/power_data_default_template.json", "/home/pi/oasis-rpi/configs/power_data.json"],"cp")
    reset_p.wait()

#new generic function for working on arbitrary structs with defaults
def reset_config_path(path: str):
    filename = os.path.basename(path)
    f_name, f_ext = os.path.splitext(filename)
    default_path = "/home/pi/oasis-rpi/defaults/" + f_name + "_default_template.json"
    
    if os.path.exists(default_path):
        reset_path = rusty_pipes.Open(["cp", default_path, path],"cp")
        reset_path.wait()
    else:
        print("Cannot reset struct because a default config file does not exist.")

#will be deprecated for rust implementation    
def reset_locks():
    reset_lox = rusty_pipes.Open(["cp", "/home/pi/oasis-rpi/defaults/locks_default_template.json", "/home/pi/oasis-rpi/configs/locks.json"],"cp")
    reset_lox.wait()

#will be deprecated for rust implementation    
def reset_signals():
    reset_sigz = Popen(["cp", "/home/pi/oasis-rpi/defaults/signals_default_template.json", "/home/pi/oasis-rpi/configs/signals.json"])
    reset_sigz.wait()

def reset_nonhw_configs():
    reset_device_state()
    reset_control_params() #Why don't we keep these?
    reset_access_config()
    reset_data_out() 

def reset_data_out():
    clear_image_feed = rusty_pipes.Open(["rm", "-rf", "/home/pi/oasis-rpi/data_out/image_feed"],"rm")
    clear_image_feed.wait()
    clear_sensor_feed = rusty_pipes.Open(["rm", "-rf", "/home/pi/oasis-rpi/data_out/sensor_feed"],"rm")
    clear_sensor_feed.wait()
    clear_power_data = rusty_pipes.Open(["rm", "-rf", "/home/pi/oasis-rpi/data_out/resource_use"],"rm")
    clear_power_data.wait()
    clear_dir = rusty_pipes.Open(["rm", "-rf", "/home/pi/oasis-rpi/data_out"],"rm")
    clear_dir.wait()
    
    new_dir = rusty_pipes.Open(["mkdir", "/home/pi/oasis-rpi/data_out"],"mkdir")
    new_dir.wait()
    new_image_feed = rusty_pipes.Open(["mkdir", "/home/pi/oasis-rpi/data_out/image_feed"],"mkdir")
    new_image_feed.wait()
    new_sensor_feed = rusty_pipes.Open(["mkdir", "/home/pi/oasis-rpi/data_out/sensor_feed"],"mkdir")
    new_sensor_feed.wait()
    new_power_data = rusty_pipes.Open(["mkdir", "/home/pi/oasis-rpi/data_out/resource_use"],"mkdir")
    new_power_data.wait()

def reset_image_feed():
    clear_image_feed = rusty_pipes.Open(["rm", "-rf", "/home/pi/oasis-rpi/data_out/image_feed"],"rm")
    clear_image_feed.wait()
    new_image_feed = rusty_pipes.Open(["mkdir", "/home/pi/oasis-rpi/data_out/image_feed"],"mkdir")
    new_image_feed.wait()
    
#function that runs all the other functions
def reset_all():
    clear_data_dir = rusty_pipes.Open(["rm", "-rf", "/home/pi/oasis-rpi/data_out"],"rm data")
    clear_data_dir.wait()

    clear_configs_dir = rusty_pipes.Open(["rm", "-rf", "/home/pi/oasis-rpi/data_out"],"rm configs")
    clear_configs_dir.wait()

    clear_configs_dir = rusty_pipes.Open([".", "/home/pi/oasis-rpi/setup_scripts"], "reset_configs")
    clear_configs_dir.wait()

if __name__ == '__main__':
    reset_all()

