#import shell modules
import os
import os.path
import sys

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

import main
from utils import concurrent_state as cs
from utils import reset_model as r
from networking import wifi
from networking import db_tools as dbt

def start_core():
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/device_state.json","running","1", db_writer = dbt.patch_firebase)
    print("Started system core.")
    return

def stop_core():
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/device_state.json","running","0", db_writer = dbt.patch_firebase)
    print("Stopped system core.")
    return

def connect_device():
    cs.load_state()
    wifi.enable_access_point(dbt.patch_firebase)
    return

def set_temperature_target(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "target_temperature", str(value), db_writer = dbt.patch_firebase)
    print("Temperature target was set to: " + str(value) + " degrees farenheit.")
    return

def set_humidity_target(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "target_humidity", str(value), db_writer = dbt.patch_firebase)
    print("Relative humidity target was set to: " + str(value) + " percent.")
    return

def set_light_timer(time_start_light, time_stop_light, lighting_interval):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "time_start_light", str(time_start_light), db_writer = dbt.patch_firebase)
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "time_stop_light", str(time_stop_light), db_writer = dbt.patch_firebase)
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "lighting_interval", str(lighting_interval), db_writer = dbt.patch_firebase)
    print("Lights will turn on at " + str(time_start_light) + ":00.")
    print("Lights will turn off at " + str(time_stop_light) + ":00.")
    print("Lights will refresh every " + str(lighting_interval) + " seconds.")
    return

def set_picture_frequency(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "picture_frequency", str(value), db_writer = dbt.patch_firebase)
    print("Camera will take a picture every " + str(value) + " seconds.")
    return

def set_watering_cycle(watering_duration, watering_interval):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "watering_duration", str(watering_duration), db_writer = dbt.patch_firebase)
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "watering_interval", str(watering_interval), db_writer = dbt.patch_firebase)
    print("Watering pump will run for " + str(watering_duration) + " seconds, once every " + str(watering_interval) + " hours.")
    return

def set_air_timer(time_start_air,time_stop_air, air_interval):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "", str(time_start_air), db_writer = dbt.patch_firebase)
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "", str(time_stop_air), db_writer = dbt.patch_firebase)
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "", str(air_interval), db_writer = dbt.patch_firebase)
    print("Air pump will turn on at " + str(time_start_air) + ":00.")
    print("Air pump will turn off at " + str(time_stop_air) + ":00.")
    print("Air pump will refresh every " + str(air_interval) + " seconds.")
    return

def read_temperature():
    cs.load_state()
    temperature = cs.structs["device_state"]["temperature"]
    return temperature

def read_humidity():
    cs.load_state()
    humidity = cs.structs["device_state"]["humidity"]
    return humidity
    
def read_water_level():
    cs.load_state()
    water_low = cs.structs["device_state"]["water_low"]
    return water_low


def set_heater_response(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "P_heat", str(value), db_writer = dbt.patch_firebase)
    print("Heater response gain set to: " + str(value))
    return

def set_heater_damping(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "D_heat", str(value), db_writer = dbt.patch_firebase)
    print("Heater damping gain set to: " + str(value))
    return

def set_humidifier_response(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "P_hum", str(value), db_writer = dbt.patch_firebase)
    print("Humidifier response gain set to: " + str(value))
    return

def set_humidifier_damping(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "D_hum", str(value), db_writer = dbt.patch_firebase)
    print("Humidifier damping gain set to: " + str(value))
    return

def set_fan_response_temp(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "Pt_fan", str(value), db_writer = dbt.patch_firebase)
    print("Fan temperature response gain set to: " + str(value))
    return    

def set_fan_damping_temp(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "Dt_fan", str(value), db_writer = dbt.patch_firebase)
    print("Fan temperature damping gain set to: " + str(value))
    return

def set_fan_response_hum(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "Ph_fan", str(value), db_writer = dbt.patch_firebase)
    print("Fan humidity response gain set to: " + str(value))
    return

def set_fan_damping_temp(value):
    cs.load_state()
    cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "Dh_fan", str(value), db_writer = dbt.patch_firebase)
    print("Fan humidity response gain set to: " + str(value))
    return

def show_state():
    cs.load_state()
    print(cs.structs["device_state"])
    return

def show_parameters():
    cs.load_state()
    print(cs.structs["control_params"])
    return

def show_active_features():
    cs.load_state()
    print(cs.structs["feature_toggles"])
    return

def show_hardware_pins():
    cs.load_state()
    print(cs.structs["hardware_config"])
    return

def reset_state():
    r.reset_device_state()
    return

def reset_parameters():
    r.reset_control_params()
    return

def reset_creds():
    r.reset_access_config()
    return

def reset_hardware():
    r.reset_hardware_config()
    return

def reset_features():
    r.reset_feature_toggles()
    return

def reset_data_out():
    r.reset_data_out()

def reset_all():
    r.reset_all()
    return