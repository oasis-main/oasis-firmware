#import shell modules
import os
import sys

#set custom module path
sys.path.append('/home/pi/oasis-rpi')

#concurrency

from utils import concurrent_state as cs

#networking
from networking import db_tools as dbt

#data
import csv

#housekeeping
from utils import reset_model

#check if the device is waiting to be added to firebase, if it is then add it, otherwise skip
def add_new_device():
    cs.load_state()

    #assemble data to initialize firebase
    setup_dict = {} #Access & hardware config will be kept private, not shared with cloud 
    setup_dict.update(cs.structs["device_state"])
    setup_dict.update(cs.structs["control_params"])
    setup_dict.update(cs.structs["hardware_config"]) #nested dict, make sure to hangle appropriately
    setup_dict.update(cs.structs["feature_toggles"])
    setup_dict.update(cs.structs["sensor_data"])
    setup_dict.update(cs.structs["power_data"])
    setup_dict_named = {cs.structs["access_config"]["device_name"] : setup_dict}
    my_data = setup_dict_named
    #print(my_data)
    #print(type(my_data))

    #add box data to firebase (replace with send_dict)
    patch_request = dbt.firebase_add_device(cs.structs["access_config"],my_data) #this is really just a dict patch 
    
    if patch_request.ok:
        cs.write_state("/home/pi/oasis-rpi/configs/device_state.json","new_device","0", db_writer = dbt.patch_firebase)
        print("New device added to firebase.")
    else:
        print("Failed to add new device.")

#deletes a box if the cloud is indicating that it should do so
def delete_device(exists = True):    
    print("Removing device from Oasis Network...")
    
    if exists:
        cs.write_state("/home/pi/oasis-rpi/configs/device_state.json","connected","0", db_writer = dbt.patch_firebase) 
    else:
        cs.write_state("/home/pi/oasis-rpi/configs/device_state.json","connected","0")

    print("Disconnected from remote database & cloud authentication.")
    reset_model.reset_nonhw_configs()
    
    #print("Device has been reset to default configuration")
    #systemctl_reboot = rusty_pipes.Open(["sudo", "systemctl", "reboot"],"reboot")
    #systemctl_reboot.wait()

#write some data to a .csv, takes a dictionary and a path
def write_sensor_csv(filename, dict): #Depends on: "os" "csv"
    file_exists = os.path.isfile(filename)

    with open (filename, 'a') as csvfile:
        headers = ["time"]

        if cs.structs["feature_toggles"]["temperature_sensor"] == "1":
            headers.append("temperature")
        if cs.structs["feature_toggles"]["humidity_sensor"] == "1":
            headers.append("humidity")
        if cs.structs["feature_toggles"]["co2_sensor"] == "1":
            headers.append("co2")
        if cs.structs["feature_toggles"]["substrate_moisture_sensor"] == "1":
            headers.append("substrate_moisture")
        if cs.structs["feature_toggles"]["vpd_calculation"] == "1":
            headers.append("vpd")
        if cs.structs["feature_toggles"]["water_level_sensor"] == "1":
            headers.append("water_low")
        if cs.structs["feature_toggles"]["lux_sensor"] == "1":
            headers.append("lux")
        if cs.structs["feature_toggles"]["ph_sensor"] == "1":
            headers.append("ph")
        if cs.structs["feature_toggles"]["tds_sensor"] == "1":
            headers.append("tds")

        writer = csv.DictWriter(csvfile, delimiter=',', lineterminator='\n',fieldnames=headers)

        if not file_exists:
            writer.writeheader()  # file doesn't exist yet, write a header

        variables = {}

        for variable in dict.keys():
            if variable in headers:
                variables[variable] = dict[variable]

        writer.writerow(variables)

        writer = None

    return

#write some data to a .csv, takes a dictionary and a path
def write_power_csv(filename, dict): #Depends on: "os" "csv"
    file_exists = os.path.isfile(filename)

    with open (filename, 'a') as csvfile:
        headers = ["time"]
        
        headers.append("boards_kwh")

        if cs.structs["feature_toggles"]["heater"] == "1":
            headers.append("heater_kwh")
        if cs.structs["feature_toggles"]["humidifier"] == "1":
            headers.append("humidifier_kwh")
        if cs.structs["feature_toggles"]["dehumidifier"] == "1":
            headers.append("dehumidifier_kwh")
        if cs.structs["feature_toggles"]["fan"] == "1":
            headers.append("fan_kwh")
        if cs.structs["feature_toggles"]["light"] == "1":
            headers.append("lights_kwh")
        if cs.structs["feature_toggles"]["water"] == "1":
            headers.append("water_pump_kwh")
        if cs.structs["feature_toggles"]["air"] == "1":
            headers.append("air_pump_kwh")

        headers.append("total_kwh") #always remember to add headers for any csv field

        writer = csv.DictWriter(csvfile, delimiter=',', lineterminator='\n',fieldnames=headers)

        if not file_exists: 
            print("Creating headers for new file...")
            writer.writeheader()  # file doesn't exist yet, write a header

        variables = {}

        for variable in dict.keys():
            if variable in headers:
                variables[variable] = dict[variable]

        writer.writerow(variables)

        writer = None

    return

def send_csv(path, cloud_name):
    #send new image to firebase
    cs.load_state()
    user, db, storage = dbt.initialize_user(cs.structs["access_config"]["refresh_token"])
    dbt.store_file(user, storage, path, cs.structs["access_config"]["device_name"], cloud_name)
    print("Sent csv timeseries")

    #tell firebase that there is a new time series
    dbt.patch_firebase(cs.structs["access_config"], "csv_sent", "1")
    print("Firebase has a csv in waiting")

#connects system to firebase
def connect_to_firebase(): #depends on: cs.load_state(), cs.write_state(), dbt.patch_firebase(), 'requests'; Modifies: access_config.json, device_state.json
    
    #load state so we can use access credentials
    cs.load_state()
    wak = cs.structs["access_config"]["wak"]
    email = cs.structs["access_config"]["e"]
    password = cs.structs["access_config"]["p"]

    print("Checking for connection...")

    try:
        print("FireBase verification:")

        #fetch refresh token
        refresh_token = dbt.get_refresh_token(wak, email, password)
        #fetch refresh token and save to access_config
        cs.write_state("/home/pi/oasis-rpi/configs/access_config.json","refresh_token", refresh_token, db_writer = None)

        #bring in the refresh token for use further down
        cs.load_state()
        refresh_token = cs.structs["access_config"]["refresh_token"]
        print("Obtained a refresh token!")

        #fetch a new id_token & local_id
        id_token, user_id = dbt.get_local_credentials(wak, refresh_token)
        #write local credentials to access config
        cs.write_state("/home/pi/oasis-rpi/configs/access_config.json","id_token", id_token, db_writer = None)
        cs.write_state("/home/pi/oasis-rpi/configs/access_config.json","local_id", user_id, db_writer = None)
        print("Devie authorized with local credentials.")

        #launch new_device check at network startup
        cs.check_state("new_device", add_new_device)

        #now check the database to make sure it hasn't been deleted
        if dbt.fetch_device_data(cs.structs["access_config"]) is not None:
            #start listener to bring in db changes on startup
            #Main setup always sets 'connected' == "0"
            cs.write_state('/home/pi/oasis-rpi/configs/device_state.json',"connected","1", db_writer = dbt.patch_firebase)
            #update the device state to "connected"
            print("Device is connected over HTTPS to the Oasis Network")
            return True 
        else:
            delete_device(exists=False)
            return False

    except Exception as e:
        #print(err.full_stack()) #display error
        #write state as not connected
        cs.write_state("/home/pi/oasis-rpi/configs/device_state.json","connected","0", db_writer = dbt.patch_firebase)
        print("Could not establish an HTTPS connection to Oasis Network")
        return False

if __name__ == "__main__":
    connect_to_firebase()