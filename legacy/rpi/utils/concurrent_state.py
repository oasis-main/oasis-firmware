#This file contains tools for managing shared state in a python multiprocessing application
#Used in:
##main.py
##core.py
##update.py
##camera.py
##connect_oasis(offline only)
##detect_db_events(offline only)

#import modules
import os
import sys
import time

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

#rust modules
import orjson #fast data interchange / and json parsing (read and write byte file objects)
import rusty_pipes #rust concurrency modules (fast mutual exclusion for arbitrarily named resources) 

#oasis utilities
from utils import reset_model
from utils import error_handler as err

#___________________________________________________________________
#Declare Structs

#...cloud-synced:
#device_state #describes the current state of the system
#control_params #describes the grow configuration of the system
#hardware_config #nested structs for pins config and hw variables   IMPORTANT: ALL WRITES TO hardware_config MUST BE NESTED  
                                                                    #Use cs.write_nested_state() etc. for hw updates
#...cloud-touching
#sensor_data #tells the system which features are in use (data only goes out)
#power_data #holds the energy consumption over some time for various processes in kwh 
#feature_toggles #tells the system which features are in use (we do fetch this, but in a manually actuated flow)

#...locally-kept
#access_config #contains credentials for connecting to firebase
#locks #multiprocessing mutex
#signals #child process termination & acknowledgement

structs = {"device_state": {}, #any struct holding shared state
"control_params": {},          #must be declared here, as this is where 
"sensor_data": {},             #the state machine stores values for access for example
"access_config" : {},          # from utils import concurrent_state as cs
"hardware_config": {},         # cs.structs["device_state"]["running"]
"feature_toggles": {},
"power_data": {},}

#declare state locking varibles
locks = {}
lock_filepath = "/home/pi/oasis-rpi/configs/locks.json"

#declare process signaling variables for those than need root & cannot terminate with SIGTERM
signals = {}
signal_filepath = "/home/pi/oasis-rpi/configs/signals.json"

def load_state(loop_limit = 1000): 
    global structs

    for struct in structs: #now we're going to load an populate the data    
        for i in list(range(int(loop_limit)+1)): #attempt to load, pass and try again if fails
            try:
                config_filepath = "/home/pi/oasis-rpi/configs/" + struct + ".json"

                if not os.path.exists(config_filepath):
                    print(config_filepath + " does not exist. Have you run the setup scripts?")
                    return

                with open(config_filepath, "rb") as x: #open the config filepath with bytes
                        structs[struct] = orjson.loads(x.read()) #try to parse bytes to json -> dict
                        #print(struct)

                for k in structs[struct]: 
                    #print(k)
                    if structs[struct][k] is None:
                        print("Read NoneType in " + struct + "!")
                        print("Resetting " + struct + "...") 
                        reset_model.reset_config_path(config_filepath)
                    else: 
                        pass
            
                break #exits the loop upon success
                
            except Exception:
                if i >= int(loop_limit): #give up if starved
                    print("Tried to read " + struct + " max # of times. File is corrupted, resetting " + config_filepath+ "...")
                    reset_model.reset_config_path(config_filepath)
                else:
                    #print(err.full_stack())
                    print("Waiting on " + struct + "...")
                    time.sleep(0.01)
                    pass

#gets the mutex
def load_locks(loop_limit = 1000): #leave this alone since it's the python bridge to ramport locks
    global locks
            
    if not os.path.exists(lock_filepath):
        print("Lockfile does not exist. Have you run the setup scripts?")
        return
    
    for i in list(range(int(loop_limit)+1)): #try to load, check if available, make unavailable if so, write state if so, write availabke iff so,  
        try:
            with open(lock_filepath, "rb") as l:
                locks = orjson.loads(l.read()) #get locks

            for k,v in locks.items():
                if locks[k] is None:
                    print("Read NoneType in locks")
                    print("Resetting lock...")
                    rusty_pipes.unlock(lock_filepath,k, loop_limit)  
                else: 
                    pass
             
            break #exit the loop on success
    
        except Exception:
            if i >= int(loop_limit):
                print("Tried to load locks max number of times. File is corrupted. Resetting locks...")
                rusty_pipes.reset_locks(lock_filepath, loop_limit)
                print(err.full_stack())
            else:
                print("Waiting on lockfile...")
                time.sleep(0.5)
                pass

def wrapped_sys_exit(*args):
    print("See ya!")
    sys.exit()

#gets the signals which cannot be process with signals.signal(SIGTERM, some_func)
def load_custom_signals(loop_limit = 1000): #leave this alone since it's the python bridge to ramport locks
    global signals

    if not os.path.exists(signal_filepath):
        print("Signal file does not exist. Have you run the setup scripts?")
        return
    
    for i in list(range(int(loop_limit)+1)): #try to load, check if available, make unavailable if so, write state if so, write availabke iff so,  
        try:
            with open(signal_filepath, "rb") as s:
                signals = orjson.loads(s.read()) #get locks

            for k,v in signals.items():
                if signals[k] is None:
                    print("Read NoneType in signals")
                    print("Resetting signals...")
                    reset_model.reset_signals() 
                else: 
                    pass
             
            break #exit the loop on success
    
        except Exception:
            if i < int(loop_limit):
                print("Waiting on signal file...")
                time.sleep(0.01)
                pass
            else:
                print("Tried to load locks max number of times. File is corrupted. Resetting signals...")
                reset_model.reset_signals()

#save key values to .json
def write_state(path, field, value, db_writer = None, loop_limit = 1000): #Depends on: load_state()
    
    if not os.path.exists(path):
        print(path + " does not exist. Have you run the setup scripts?")
        return
    
    if db_writer is not None: #Accepts(path, field, value, custom timeout, db_writer function); Modifies: path
        if structs["device_state"]["connected"] == "1": #write state to cloud
            try:
                db_writer(structs["access_config"],field,value) #will be loaded in by listener, so is best represent change db first
            except Exception:
                print(err.full_stack())
                pass        
    
    try:
        rusty_pipes.lock(lock_filepath, path, loop_limit)

        with open(path, "rb+") as x:
            data = orjson.loads(x.read())
            data[field] = value #write the desired value
            x.seek(0)
            x.write(orjson.dumps(data))
            x.truncate()
    
    finally:
        rusty_pipes.unlock(lock_filepath, path, loop_limit)
        load_state()

            
#save key values to .json
def write_dict(path, dictionary, db_writer = None, loop_limit = 1000): #Depends on: load_state(), dbt.patch_firebase, 'json'; Modifies: path

    if not os.path.exists(path):
        print(path + " does not exist. Have you run the setup scripts?")
        return
    
    if db_writer is not None:
        #these will be loaded in by the listener, so best to make sure we represent the change in firebase too
        if structs["device_state"]["connected"] == "1": #write state to cloud
            try:
                db_writer(structs["access_config"], dictionary)
            except Exception:
                print(err.full_stack())
                pass

    try:
        #Now write safely
        rusty_pipes.lock(lock_filepath, path, loop_limit)
        
        with open(path, "rb+") as x:
            data = orjson.loads(x.read())
            data.update(dictionary) #write the desired values
            x.seek(0)
            x.write(orjson.dumps(data))
            x.truncate()
    
    finally:    
        rusty_pipes.unlock(lock_filepath, path, loop_limit)
        load_state()
               

def write_nested_state(path: str, group: str, field: str, value: str, db_writer = None, loop_limit = 100): #listener needs this for patching hardware config
    
    if not os.path.exists(path):
        print(path + " does not exist. Have you run the setup scripts?")
        return
    
    if db_writer is not None: #Accepts(path, field, value, custom timeout, db_writer function); Modifies: path
        if structs["device_state"]["connected"] == "1": #write state to cloud
            try:
                db_writer(structs["access_config"],field,value) #will be loaded in by listener, so is best represent change db first
            except Exception as e:
                print(err.full_stack())
                pass
            
    try: #try to safely execute a write
        rusty_pipes.lock(lock_filepath, path, loop_limit)

        with open(path, "rb+") as x:
            data = orjson.loads(x.read())
            data[group][field] = value #write the desired value
            x.seek(0)
            x.write(orjson.dumps(data))
            x.truncate()
    
    finally:
        rusty_pipes.unlock(lock_filepath, path, loop_limit)
        load_state()
                
def write_nested_dict(path: str, group: str, dictionary: dict, db_writer = None, loop_limit = 1000): #may even come in handy later, you never know
    
    if not os.path.exists(path):
        print(path + " does not exist. Have you run the setup scripts?")
        return    
    
    if db_writer is not None:
        #these will be loaded in by the listener, so best to make sure we represent the change in firebase too
        if structs["device_state"]["connected"] == "1": #write state to cloud
            try:
                db_writer(structs["access_config"], dictionary)
            except Exception:
                print(err.full_stack())
                pass
     
    try:
        rusty_pipes.lock(lock_filepath, path, loop_limit)

        with open(path, "rb+") as x: # open the file.
            data = orjson.loads(x.read()) # can we load a valid json?
            data[group] = dictionary #write the desired values
            x.seek(0)
            x.write(orjson.dumps(data))
            x.truncate()
        
    finally:
        rusty_pipes.unlock(lock_filepath, path, loop_limit)
        load_state()
            

#Higher-order device_state checker with reaction and alternative, no params
def check_state(value, function = None, alt_function = None):# = None, args = None, kwargs = None, alt_args = None, alt_kwargs = None):
    load_state()
    if (function is not None) and (structs["device_state"][value] == "1"):
        function()
    else:
        pass
    
    if (alt_function is not None) and (structs["device_state"][value] == "0"):
        alt_function()
    else:
        pass

def check_lock(resource): #any program that calls this MUST unlock itself before exiting
    load_locks()
    y_lock_path = resource + "_y"
    if locks[y_lock_path] != 0: #if resource is locked
        print(resource + " is currently in use by another process.")
        sys.exit() #termiating for safety
    else:
        rusty_pipes.lock(lock_filepath, resource)

def check_signal(resource: str, signal: str, reaction, loop_limit = 1000):
    load_custom_signals()
    if signals[resource] == signal:
        
        for i in range(loop_limit+1):
            if i < loop_limit:
                try:
                    with open(signal_filepath, "rb+") as x:
                        data = orjson.loads(x.read())
                        data[resource] = "acknowledged" #write the desired value
                        x.seek(0)
                        x.write(orjson.dumps(data))
                        x.truncate()
                    break
                except Exception:
                    print("Signal store accessed while being written. Waiting to try again...")
                    pass
            else:
                print("Process signals are starved of acknowledgement. Something is wrong.")
                print(err.full_stack())
        
        reaction() #call the function to react to the signal eg. check_signal("led","terminated", reaction.clean_up)

if __name__ == '__main__':
    print("This is a unit test:")
    load_state()
    load_locks()
    load_custom_signals()
    write_state("/home/pi/oasis-rpi/configs/device_state.json", "running", "1")
    write_dict("/home/pi/oasis-rpi/configs/device_state.json", {"running": "1"})
    write_nested_state("/home/pi/oasis-rpi/configs/hardware_config.json", "sensor_calibration", "temperature_offset", "1")
    write_nested_dict("/home/pi/oasis-rpi/configs/hardware_config.json", "sensor_calibration", {"tds_offset": "1"})
    
    def test():
        print("Hello World")
    
    check_state("running", test)
    check_signal("led", "None", test)

    if str(sys.argv[1]) == "online":
        from networking import db_tools as dbt
        write_state("/home/pi/oasis-rpi/configs/device_state.json", "running", "1", db_writer = dbt.patch_firebase)
        write_dict("/home/pi/oasis-rpi/configs/device_state.json", {"running": "1"}, db_writer = dbt.patch_firebase_dict)