#FEATURE EXTRACTION:
#   Almost everything we do here can be put into groups of functionality & extracted into various modules.
#   We want the core to parse configs, load functions for each feature, and interatively run + chain for all enabled
#   The end result should be that it is easier to add a new metrics, data sources, analyses, reaction, and outputs to the core program  
#   An easier option would be to make everything in this file an imported module, and then manually note where each module group touches in the code :)

#system
import sys
import signal

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

#Process management
import rusty_pipes

#data handling
import orjson
import pprint

#dealing with specific times of the day
import time
import datetime

#import other oasis packages
from utils import concurrent_state as cs
from utils import physics
from utils import error_handler as err
from networking import db_tools as dbt
from networking import firebase_manager
from peripherals import serial_arduinos as minion

resource_name = "core"

#declare sensors
sensor_data = {}

#declare environmental variables 
temperature = float()
last_temperature = float()
last_target_temperature = float()
err_cum_temperature = float()

humidity = float()
last_humidity = float()
last_target_humidity = float()
err_cum_humidity = float()

co2 = float()
last_co2 = float()
last_target_co2 = float()
err_cum_co2 = float()

substrate_moisture = float()
last_substrate_moisture = float()
last_target_substrate_moisture = float()
err_cum_substrate_moisture = float()

vpd = float()
lux = float()
ph = float()
tds = float()
water_low = int()

#declare long-running process objects
heat_process = None
humidity_process = None
dehumidify_process = None
fan_process = None
light_process = None
camera_process = None
water_process = None
air_process = None

#declare our timekeeping stamp
data_timer = None #will be a timestamp object

def update_derivative_banks():
    global last_target_temperature, last_target_humidity, last_target_co2, last_target_substrate_moisture
    #save last temperature and humidity targets to calculate delta for PD controllers
    last_target_temperature = float(cs.structs["control_params"]["target_temperature"]) 
    last_target_humidity = float(cs.structs["control_params"]["target_humidity"])
    last_target_co2 = float(cs.structs["control_params"]["target_co2"])
    last_target_substrate_moisture = float(cs.structs["control_params"]["target_substrate_moisture"])

#gets data from serial, will parse a simple string or accept a dictionary
def listen_active_sensors(): #Depends on 'serial', start_serial()
    global sensor_data
    if minion.ser_in == None: #to add more devices, simply import more minions and make objects for them
        print("Primary sensor minion not connected.") #then set the mapping from sensor reading -> env variable throught globals
        return 
    try: #If you're having problems here, it's very likely from the hardware malfunctioning
        #print(minion.ser_in.readline()) #must pass a valid json in byte form
        #print(type(minion.ser_in.readline())) #multiple minions can be used to assemble different sensor data       
        sensor_data = orjson.loads(minion.ser_in.readline().strip(b'\n').strip(b'\r'))
        for key in sensor_data:
            if key == "water_low": #this is a bool represented as int, so no rounting required
                pass
            else:
                sensor_data[key] = round(sensor_data[key], 2)
        print(sensor_data)
        minion.ser_in.reset_input_buffer()
        return
    except Exception:
        print("Waiting on a valid sensor reading...")
        print(err.full_stack()) #uncomment to debug listener
        return

def get_temperature():
    global temperature, last_temperature #all PID enabled environmental variables must have historical values
    last_temperature = temperature
    
    try:
        temperature = float(cs.structs["hardware_config"]["sensor_calibration"]["temperature_drift"]) * float(sensor_data["temperature"]) + float(cs.structs["hardware_config"]["sensor_calibration"]["temperature_offset"])
    except Exception:
        print("Got faulty reading for temperature. Discarding...")
        #print(err.full_stack())

    cs.write_state("/home/pi/oasis-rpi/configs/sensor_data.json", "temperature", str(temperature), db_writer = None)      

def get_humidity():
    global humidity, last_humidity
    last_humidity = humidity
    
    try:
        humidity = float(cs.structs["hardware_config"]["sensor_calibration"]["humidity_drift"]) * float(sensor_data["humidity"]) + float(cs.structs["hardware_config"]["sensor_calibration"]["humidity_offset"])
    except Exception:
        print("Got faulty reading for relative humidity. Discarding...")
        #print(err.full_stack())

    cs.write_state("/home/pi/oasis-rpi/configs/sensor_data.json", "humidity", str(humidity), db_writer = None)

def get_co2():
    global co2, last_co2
    last_co2 = co2
    
    try:
        co2 = float(cs.structs["hardware_config"]["sensor_calibration"]["co2_drift"]) * float(sensor_data["co2"]) + float(cs.structs["hardware_config"]["sensor_calibration"]["co2_offset"])
    except Exception:
        print("Got faulty reading for co2. Discarding...")
        #print(err.full_stack())

    cs.write_state("/home/pi/oasis-rpi/configs/sensor_data.json", "co2", str(co2), db_writer = None)

def get_substrate_moisture():
    global substrate_moisture, last_substrate_moisture
    last_substrate_moisture = substrate_moisture
    
    try:
        substrate_moisture = float(cs.structs["hardware_config"]["sensor_calibration"]["substrate_moisture_drift"]) * float(sensor_data["substrate_moisture"]) + float(cs.structs["hardware_config"]["sensor_calibration"]["substrate_moisture_offset"])
    except Exception:
        print("Got faulty reading for substrate moisture. Discarding...")
        #print(err.full_stack())

    cs.write_state("/home/pi/oasis-rpi/configs/sensor_data.json", "substrate_moisture", str(substrate_moisture), db_writer = None)

def get_lux():
    global lux
    
    try:
        lux = float(cs.structs["hardware_config"]["sensor_calibration"]["lux_drift"]) * float(sensor_data["lux"]) + float(cs.structs["hardware_config"]["sensor_calibration"]["lux_offset"])
    except Exception:
        print("Got faulty reading for lux. Discarding...")
        #print(err.full_stack())

    cs.write_state("/home/pi/oasis-rpi/configs/sensor_data.json", "lux", str(lux), db_writer = None)

def get_ph():
    global ph
    
    try:
        ph = float(cs.structs["hardware_config"]["sensor_calibration"]["ph_drift"]) * float(sensor_data["ph"]) + float(cs.structs["hardware_config"]["sensor_calibration"]["ph_offset"])
    except Exception:
        print("Got faulty reading for pH. Discarding...")
        #print(err.full_stack())

    cs.write_state("/home/pi/oasis-rpi/configs/sensor_data.json", "ph", str(ph), db_writer = None)

def get_tds():
    global tds
    
    try:
        tds = float(cs.structs["hardware_config"]["sensor_calibration"]["tds_drift"]) * float(sensor_data["tds"]) + float(cs.structs["hardware_config"]["sensor_calibration"]["tds_offset"])
    except Exception:
        print("Got faulty reading for total disolved solids. Discarding...")
        #print(err.full_stack())

    cs.write_state("/home/pi/oasis-rpi/configs/sensor_data.json", "tds", str(tds), db_writer = None)

def get_vpd():
    global vpd
    
    try:
        vpd = physics.vpd(temperature, humidity)
    except Exception:
        print("Got error calculating vapor pressure deficit. Discarding...")
        #print(err.full_stack())

    cs.write_state("/home/pi/oasis-rpi/configs/sensor_data.json", "vpd", str(vpd), db_writer = None)

def get_water_level():
    global water_low
    
    try:
        water_low = int(sensor_data["water_low"]) #this is a boolean, so we won't discard it on the graph
    except Exception:
        print("Got faulty reading for water level. Discarding...")
        #print(err.full_stack())

    cs.write_state("/home/pi/oasis-rpi/configs/sensor_data.json", "water_low", str(water_low), db_writer = None)

def collect_environmental_data():
    if cs.structs["feature_toggles"]["temperature_sensor"] == "1":
        get_temperature()
    if cs.structs["feature_toggles"]["humidity_sensor"] == "1":
        get_humidity()
    if cs.structs["feature_toggles"]["co2_sensor"] == "1":
        get_co2()
    if cs.structs["feature_toggles"]["substrate_moisture_sensor"] == "1":
        get_substrate_moisture()
    if cs.structs["feature_toggles"]["lux_sensor"] == "1":
        get_lux()
    if cs.structs["feature_toggles"]["ph_sensor"] == "1":
        get_ph()
    if cs.structs["feature_toggles"]["tds_sensor"] == "1":
        get_tds()
    if cs.structs["feature_toggles"]["vpd_calculation"] == "1":
        get_vpd()
    if cs.structs["feature_toggles"]["water_level_sensor"] == "1":
        get_water_level()

#PID controller to modulate heater feedback
def heat_pid(temperature, target_temperature, last_temperature, last_target_temperature,
             P_heat, I_heat, D_heat):    
    
    global err_cum_temperature

    err_temperature = target_temperature-temperature    #If target is 70 and temperature is 60, this value = 10, more heat
                                                        #If target is 50 and temperature is 60, this value is negative, less heat

    temperature_dot = temperature-last_temperature  #If temp is increasing, this value is positive (+#)
                                                    #If temp is decreasing, this value is negative (-#)

    err_cum_temperature = max(min(err_cum_temperature + err_temperature, 50), -50)

    target_temperature_dot = target_temperature-last_target_temperature #When target remains the same, this value is 0
                                                                        #When adjusting target up, this value is positive (+#)
                                                                        #When adjusting target down, this value is negative (-#)

    err_dot_temperature = target_temperature_dot-temperature_dot    #When positive, boosts heat signal
                                                                    #When negative, dampens heat signal
    heat_level  = P_heat * err_temperature + I_heat * err_cum_temperature + D_heat * err_dot_temperature
    heat_level  = max(min(int(heat_level), 100), 0)
    #print(heat_level)

    return heat_level

#PID controller to modulate humidifier feedback, feedback pushes up towards target
def hum_pid(humidity, target_humidity, last_humidity, last_target_humidity, 
            P_hum, I_hum, D_hum):
    
    global err_cum_humidity
    
    err_humidity = target_humidity - humidity

    humidity_dot = humidity - last_humidity

    err_cum_humidity = max(min(err_cum_humidity + err_humidity, 50), -50)

    target_humidity_dot = target_humidity - last_target_humidity

    err_dot_humidity = target_humidity_dot - humidity_dot

    humidity_level  = P_hum*err_humidity + I_hum*err_cum_humidity + D_hum*err_dot_humidity #positive response
    humidity_level  = max(min(int(humidity_level),100),0)
    #print(humidity_level)

    return humidity_level

#PID controller to modulate dehumidifier feedback pushes down towards target
def dehum_pid(humidity, target_humidity, last_humidity, last_target_humidity,
              P_dehum, I_dehum, D_dehum):
    
    global err_cum_humidity

    err_humidity = target_humidity - humidity
                                                
    humidity_dot = humidity - last_humidity 

    if cs.structs["feature_toggles"]["hum_pid"] == "0":
        err_cum_humidity = max(min(err_cum_humidity + err_humidity, 50), -50) 

    target_humidity_dot = target_humidity - last_target_humidity

    err_dot_humidity = target_humidity_dot - humidity_dot

    dehumidify_level  = (0-P_dehum)*err_humidity + (0-I_dehum)*err_cum_humidity + (0-D_dehum)*err_dot_humidity
    dehumidify_level  = max(min(int(dehumidify_level), 100), 0)
    #print(dehumidify_level)

    return dehumidify_level

#PID controller to modulate fan feedback, pushes down temp, hum, & c02 towards target
def fan_pid(temperature, humidity, co2,
            target_temperature, target_humidity, target_co2,
            last_temperature, last_humidity, last_co2,
            last_target_temperature, last_target_humidity, last_target_co2,
            Pt_fan, It_fan, Dt_fan, Ph_fan, Ih_fan, Dh_fan, Pc_fan, Ic_fan, Dc_fan):
    
    global err_cum_temperature, err_cum_humidity, err_cum_co2
    
    err_temperature = target_temperature - temperature
    err_humidity = target_humidity - humidity
    err_co2 = target_co2 - co2

    temperature_dot = temperature-last_temperature
    humidity_dot = humidity-last_humidity
    co2_dot = co2 - last_co2

    if cs.structs["feature_toggles"]["heat_pid"] == "0":
        err_cum_temperature = max(min(err_cum_temperature + err_temperature, 50), -50)

    if (cs.structs["feature_toggles"]["hum_pid"] == "0") and (cs.structs["feature_toggles"]["dehum_pid"] == "0"):
        err_cum_humidity = max(min(err_cum_humidity + err_humidity, 50), -50)

    err_cum_co2 = max(min(err_cum_humidity + err_humidity, 50), -50)

    target_temperature_dot = target_temperature - last_target_temperature
    target_humidity_dot = target_humidity - last_target_humidity
    target_co2_dot = target_co2 - last_target_co2

    err_dot_temperature = target_temperature_dot - temperature_dot
    err_dot_humidity = target_humidity_dot - humidity_dot
    err_dot_co2 = target_co2_dot - co2_dot

    fan_level  = (0-Pt_fan)*err_temperature + (0-It_fan)*err_cum_temperature + (0-Dt_fan)*err_dot_temperature \
                +(0-Ph_fan)*err_humidity + (0-Ih_fan)*err_cum_humidity + (0-Dh_fan)*err_dot_humidity \
                +(0-Pc_fan)*err_co2 + (0-Ic_fan)*err_cum_co2 + (0-Dc_fan)*err_dot_co2    
    
    fan_level  = max(min(int(fan_level),100),0)
    #print(fan_level)

    return fan_level

#PID controller to modulate heater feedback
def water_pid(substrate_moisture, target_substrate_moisture, 
              last_substrate_moisture, last_target_substrate_moisture,
              P_moisture, I_moisture, D_moisture):    
    
    global err_cum_substrate_moisture

    err_substrate_moisture = target_substrate_moisture - substrate_moisture   #If target is 70 and temperature is 60, this value = 10, more heat
                                                        #If target is 50 and temperature is 60, this value is negative, less heat

    substrate_moisture_dot = substrate_moisture - last_substrate_moisture  #If temp is increasing, this value is positive (+#)
                                                    #If temp is decreasing, this value is negative (-#)

    err_cum_substrate_moisture = max(min(err_cum_substrate_moisture + err_substrate_moisture, 50), -50)

    target_substrate_moisture_dot = target_substrate_moisture-last_target_substrate_moisture #When target remains the same, this value is 0
                                                                        #When adjusting target up, this value is positive (+#)
                                                                        #When adjusting target down, this value is negative (-#)

    err_dot_substrate_moisture = target_substrate_moisture_dot-substrate_moisture_dot    #When positive, boosts heat signal
                                                                    #When negative, dampens heat signal
    water_level  = P_moisture * err_substrate_moisture \
                   + I_moisture * err_cum_substrate_moisture \
                   + D_moisture * err_dot_substrate_moisture
    
    water_level  = max(min(int(water_level), 100), 0)
    #print(water_level)

    return water_level

def update_pid_controllers(): #these should come with an accompanying option in feature_toggles_default_template.json
    
    if cs.structs["feature_toggles"]["heat_pid"] == "1": #computes a feedback value if PID is on
        heat_feedback = int(heat_pid(temperature,
                                        int(cs.structs["control_params"]["target_temperature"]),
                                        last_temperature,
                                        last_target_temperature,
                                        int(cs.structs["control_params"]["P_heat"]),
                                        int(cs.structs["control_params"]["I_heat"]),
                                        int(cs.structs["control_params"]["D_heat"])))

        cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "heat_feedback", str(heat_feedback), db_writer = None)

    if cs.structs["feature_toggles"]["hum_pid"] == "1":
        hum_feedback = int(hum_pid(humidity,
                                    int(cs.structs["control_params"]["target_humidity"]),
                                    last_humidity,
                                    last_target_humidity,
                                    int(cs.structs["control_params"]["P_hum"]),
                                    int(cs.structs["control_params"]["I_hum"]),
                                    int(cs.structs["control_params"]["D_hum"])))

        cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "hum_feedback", str(hum_feedback), db_writer = None)

    if cs.structs["feature_toggles"]["dehum_pid"] == "1":
        dehum_feedback = int(dehum_pid(humidity,
                                        int(cs.structs["control_params"]["target_humidity"]),
                                        last_humidity,
                                        last_target_humidity,
                                        int(cs.structs["control_params"]["P_dehum"]),
                                        int(cs.structs["control_params"]["I_dehum"]),
                                        int(cs.structs["control_params"]["D_dehum"])))

        cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "dehum_feedback", str(dehum_feedback), db_writer = None)

    if cs.structs["feature_toggles"]["fan_pid"] == "1":
        fan_feedback = int(fan_pid(temperature , humidity, co2,
                int(cs.structs["control_params"]["target_temperature"]), int(cs.structs["control_params"]["target_humidity"]), int(cs.structs["control_params"]["target_co2"]),
                last_temperature,last_humidity, last_co2,
                last_target_temperature,last_target_humidity, last_target_co2,
                int(cs.structs["control_params"]["Pt_fan"]), int(cs.structs["control_params"]["It_fan"]), int(cs.structs["control_params"]["Dt_fan"]),
                int(cs.structs["control_params"]["Ph_fan"]), int(cs.structs["control_params"]["Ih_fan"]), int(cs.structs["control_params"]["Dh_fan"]),
                int(cs.structs["control_params"]["Pc_fan"]), int(cs.structs["control_params"]["Ic_fan"]), int(cs.structs["control_params"]["Dc_fan"])))

        cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "fan_feedback", str(fan_feedback), db_writer = None)

    if cs.structs["feature_toggles"]["water_pid"] == "1":
        moisture_feedback = int(water_pid(substrate_moisture, int(cs.structs["control_params"]["target_substrate_moisture"]),
                            last_substrate_moisture, last_target_substrate_moisture,
                            int(cs.structs["control_params"]["P_moisture"]), int(cs.structs["control_params"]["I_moisture"]), int(cs.structs["control_params"]["D_moisture"])))
        
        cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "moisture_feedback", str(moisture_feedback), db_writer = None)

#Concurrency Hell:
#
#   Ok, so the subprocess will always relaunch itself on every loop right now, because
#   even when it exits the process will always retain some information in memory about its exit
#   because a reference still exists according to the python garbage collector. This does not happen
#   at first because the processes start as None, and because the memory is never cleared:
#   process.exited() sometimes returns True when queried even though there is something also running.
#   
#   Solution: Use the system level mutex you've already built, get rid of the global variable.
#   Simple Version: Check the lock, don't poll the process.
#
#   We're using a global "running" variable to turn off the core before it launches all the below when it shouldn't.
#

#poll heat subprocess if applicable and relaunch/update equipment
def run_heat():
    global heat_process
    resource_name =  "heater"
    cs.load_locks()
    if cs.locks[resource_name+"_y"] == 0:
        heat_process = rusty_pipes.Open(['python3', '/home/pi/oasis-rpi/equipment/heater.py'], "heater") #If process not free, then skips.

#poll humidityf subprocess if applicable and relaunch/update equipment
def run_hum():
    global humidity_process
    resource_name =  "humidifier"
    cs.load_locks()
    if cs.locks[resource_name+"_y"] == 0:
        humidity_process = rusty_pipes.Open(['python3', '/home/pi/oasis-rpi/equipment/humidifier.py'], "humidifier")
    
#poll dehumidify subprocess if applicable and relaunch/update equipment
def run_dehum():
    global dehumidify_process
    resource_name =  "dehumidifier"
    cs.load_locks()
    if cs.locks[resource_name+"_y"] == 0:
        dehumidify_process = rusty_pipes.Open(['python3', '/home/pi/oasis-rpi/equipment/dehumidifier.py'], "dehumidifier")

#poll fan subprocess if applicable and relaunch/update equipment
def run_fan(): #Depends on: 'subprocess'; Modifies: humidity_process
    global fan_process
    resource_name =  "fan"
    cs.load_locks()
    if cs.locks[resource_name+"_y"] == 0:
        fan_process = rusty_pipes.Open(['python3', '/home/pi/oasis-rpi/equipment/fan.py'], "fan")

#poll water subprocess if applicable and relaunch/update equipment
def run_water(): #Depends on: 'subprocess'; Modifies: water_process
    global water_process
    resource_name =  "water_pump"
    cs.load_locks()
    if cs.locks[resource_name+"_y"] == 0:
        water_process = rusty_pipes.Open(['python3', '/home/pi/oasis-rpi/equipment/water_pump.py'], "water_pump") #If running, then skips. If idle then restarts.
    
#poll light subprocess if applicable and relaunch/update equipment
def run_light():
    global light_process
    resource_name =  "lights"
    cs.load_locks()
    if cs.locks[resource_name+"_y"] == 0:
        light_process = rusty_pipes.Open(['python3', '/home/pi/oasis-rpi/equipment/lights.py'], "lights") #If running, then skips. If free then restarts.
   
#poll air subprocess if applicable and relaunch/update equipment
def run_air():
    global air_process
    resource_name =  "air_pump"
    cs.load_locks()
    if cs.locks[resource_name+"_y"] == 0:
        air_process = rusty_pipes.Open(['python3', '/home/pi/oasis-rpi/equipment/air_pump.py'], "air_pump") #If running, then skips. If idle then restarts.
    
#poll camera subprocess if applicable and relaunch/update equipment
def run_camera(): #Depends on: 'subprocess'; Modifies: camera_process
    global camera_process
    resource_name =  "camera"
    cs.load_locks()
    if cs.locks[resource_name+"_y"] == 0:
        camera_process = rusty_pipes.Open(['python3', '/home/pi/oasis-rpi/imaging/camera.py'], "camera") #If running, then skips. If idle then restarts.

def regulate_active_equipment():
    # calculate feedback levels and update equipment in use
    if (cs.structs["feature_toggles"]["heater"] == "1") and (heat_process is None):
        print("Turning on the heat...")
        run_heat()
    if (cs.structs["feature_toggles"]["humidifier"] == "1") and (humidity_process is None):
        print("Turning on the humidifier...")
        run_hum()
    if (cs.structs["feature_toggles"]["dehumidifier"] == "1") and (dehumidify_process is None):
        print("Turning on the dehumidifier...")
        run_dehum()
    if (cs.structs["feature_toggles"]["fan"] == "1") and (fan_process is None):
        print("Turning on the vent...")
        run_fan()
    if (cs.structs["feature_toggles"]["water"] == "1") and (water_process is None):
        print("Turning on the water...")
        run_water()
    if (cs.structs["feature_toggles"]["light"] == "1") and (light_process is None):
        print("Turning on the lights...")
        run_light()
    if (cs.structs["feature_toggles"]["air"] == "1") and (air_process is None):
        print("Turning on the water bubler...")
        run_air()
    if (cs.structs["feature_toggles"]["camera"] == "1") and (camera_process is None):
        print("Activating camera...")
        run_camera()

#unfinished
def console_log():
    sensors = cs.structs["sensor_data"]
    targets = cs.structs["control_params"]
    feedback = {}
    timers = {}

    if cs.structs["feature_toggles"]["heater"] == "1":
        if cs.structs["feature_toggles"]["heat_pid"] == "1":
            feedback.update({"Heater Intensity: ": cs.structs["control_params"]["heat_feedback"]})
        else:
            timers.update({"Heater Duration (seconds run for): ": cs.structs["control_params"]["heater_duration"]})
            timers.update({"Heater Interval (seconds between runs): ": cs.structs["control_params"]["heater_interval"]})
    
    if cs.structs["feature_toggles"]["humidifier"] == "1":
        if cs.structs["feature_toggles"]["heat_pid"] == "1":
            feedback.update({"Humidifier Intensity: ": cs.structs["control_params"]["hum_feedback"]})
        else:
            timers.update({"Humidifier Duration (seconds run for): ": cs.structs["control_params"]["humidifier_duration"]})
            timers.update({"Humidifier Interval (seconds between runs): ": cs.structs["control_params"]["humidifier_interval"]})
    
    if cs.structs["feature_toggles"]["dehumidifier"] == "1":
        if cs.structs["feature_toggles"]["heat_pid"] == "1":
            feedback.update({"Dehumidifier Intensity: ": cs.structs["control_params"]["dehum_feedback"]})
        else:
            timers.update({"Dehumidifier Duration (seconds run for): ": cs.structs["control_params"]["dehumidifier_duration"]})
            timers.update({"Dehumidifier Interval (seconds between runs): ": cs.structs["control_params"]["dehumidifier_interval"]})
    
    if cs.structs["feature_toggles"]["fan"] == "1":
        if cs.structs["feature_toggles"]["fan_pid"] == "1":
            feedback.update({"Fan Intensity: ": cs.structs["control_params"]["fan_feedback"]})
        else:
            timers.update({"Fan Duration (minutes run for): ": cs.structs["control_params"]["fan_duration"]})
            timers.update({"Fan Interval (minutes between runs): ": cs.structs["control_params"]["fan_interval"]})

    if cs.structs["feature_toggles"]["water"] == "1":
        if cs.structs["feature_toggles"]["water_pid"] == "1":
            feedback.update({"Irrigation Intensity: ": cs.structs["control_params"]["moisture_feedback"]})
        else:
            timers.update({"Irrigation Duration (seconds run for): ": cs.structs["control_params"]["watering_duration"]})
            timers.update({"Irrigation Interval (hours between runs): ": cs.structs["control_params"]["watering_interval"]})
    
    if cs.structs["feature_toggles"]["air"] == "1":
        timers.update({"Air Pump Turns On at (Hourly Time 0-23): ": cs.structs["control_params"]["time_start_air"]})
        timers.update({"Air Pump Turns Off at (Hourly Time 0-23): ": cs.structs["control_params"]["time_stop_air"]})
        timers.update({"Air Pump Interval (seconds between runs): ": cs.structs["control_params"]["air_interval"]})

    if cs.structs["feature_toggles"]["light"] == "1":
        timers.update({"Light Turns On at (Hourly Time 0-23): ": cs.structs["control_params"]["time_start_light"]})
        timers.update({"Light Turns Off at (Hourly Time 0-23): ": cs.structs["control_params"]["time_stop_light"]})
        timers.update({"Light Interval (seconds between runs): ": cs.structs["control_params"]["air_interval"]})

    if cs.structs["feature_toggles"]["camera"] == "1":
        timers.update({" Duration (seconds run for): ": cs.structs["control_params"]["heater_duration"]})
        if cs.structs["feature_toggles"]["ndvi"] == "1":
            timers.update({"Capture Mode": "NDVI"})
        else:
            timers.update({"Capture Mode": "Raw AWB Imaging"})
        timers.update({"Camera Interval (seconds between image capture): ": cs.structs["hardware_config"]["camera_settings"]["picture_frequency"]})

    
    if sensors:
        print("Sensor Data = ")
        pprint.pprint(sensors)
    if targets:
        print("")
    if feedback:
        print("Feedback Settings = ")
        pprint.pprint(feedback)
    if timers:
        print("Timer Settings = ")
        pprint.pprint(timers)

def data_out():
    global data_timer
    
    #write data and send to server after set time elapses
    if time.time() - float(cs.structs["control_params"]["last_sensor_log_time"]) > 300:
        #we log the last run time BEFORE any waiting or expensive comps
        cs.write_state("/home/pi/oasis-rpi/configs/control_params.json", "last_sensor_log_time", str(time.time()), db_writer = dbt.patch_firebase) 

        try:
            payload = cs.structs["sensor_data"]
            now = datetime.datetime.now()
            format = '%Y-%m-%d %H:%M:%S.%f'
            present_time = now.strftime(format)
            timestamp = {"time": present_time}
            payload.update(timestamp)

            if cs.structs["feature_toggles"]["save_data"] == "1":
                #save data to .csv
                print("Writing to csv")
                firebase_manager.write_sensor_csv('/home/pi/oasis-rpi/data_out/sensor_feed/sensor_data.csv', payload)

                if cs.structs["device_state"]["connected"] == "1":
                    #write data to disk and exchange with cloud if connected
                    dbt.patch_firebase_dict(cs.structs["access_config"],payload)

                    #send new time-series to firebase
                    firebase_manager.send_csv('/home/pi/oasis-rpi/data_out/sensor_feed/sensor_data.csv', 'sensor_data.csv')
        
        except Exception as e:
            print(err.full_stack())

def clean_up_processes():
    global heat_process, humidity_process, dehumidify_process, fan_process, light_process, camera_process, water_process, air_process        

    #clean up all processes
    

    if (cs.structs["feature_toggles"]["heater"] == "1") and (heat_process is not None): #go through toggles and kill active processes
        heat_process.terminate()
        heat_process.wait()
        heat_process = None
    if (cs.structs["feature_toggles"]["humidifier"] == "1") and (humidity_process is not None):
        humidity_process.terminate()
        humidity_process.wait()
        humidity_process = None
    if (cs.structs["feature_toggles"]["dehumidifier"] == "1") and (dehumidify_process is not None):
        dehumidify_process.terminate()
        dehumidify_process.wait()
        dehumidify_process = None
    if (cs.structs["feature_toggles"]["fan"] == "1") and (fan_process is not None):
        fan_process.terminate()
        fan_process.wait()
        fan_process = None
    if (cs.structs["feature_toggles"]["water"] == "1") and (water_process is not None):
        water_process.terminate()
        water_process.wait()
        water_process = None
    if (cs.structs["feature_toggles"]["light"] == "1") and (light_process is not None):
        light_process.terminate()
        light_process.wait()
        light_process = None
    if (cs.structs["feature_toggles"]["air"] == "1") and (air_process is not None):
        air_process.terminate()
        air_process.wait()
        air_process = None
    if (cs.structs["feature_toggles"]["camera"] == "1") and (camera_process is not None):
        camera_process.terminate()
        camera_process.wait()
        camera_process = None

#terminates the program and all running subprocesses
def terminate_program(): #Depends on: , 'sys', 'subprocess' #Modifies: heat_process, humidity_process, fan_process, light_process, camera_process, water_processs
    print("Cleaning up processes...")
    clean_up_processes()
    cs.write_state("/home/pi/oasis-rpi/configs/device_state.json", "running", "0", db_writer = dbt.patch_firebase) #flip "running" to 0
    cs.write_state("/home/pi/oasis-rpi/configs/device_state.json","led_status","connected_idle", db_writer = dbt.patch_firebase)
    time.sleep(1)
    cs.rusty_pipes.unlock(cs.lock_filepath,resource_name) #free the resource
    sys.exit()

def main_setup():
    global data_timer, minion 

    #Load state variables to start the main program
    cs.load_state()

    #Set up SIGTERM handler to throw a sys exit when signaled
    signal.signal(signal.SIGTERM, cs.wrapped_sys_exit)

    #attempt to make serial connection but only if there is a sensor active
    if ((cs.structs["feature_toggles"]["temperature_sensor"] == "1") \
                or (cs.structs["feature_toggles"]["humidity_sensor"] == "1") \
                    or (cs.structs["feature_toggles"]["water_level_sensor"] == "1") \
                        or (cs.structs["feature_toggles"]["co2_sensor"] == "1") \
                            or (cs.structs["feature_toggles"]["lux_sensor"] == "1") \
                                or (cs.structs["feature_toggles"]["ph_sensor"] == "1") \
                                    or (cs.structs["feature_toggles"]["tds_sensor"] == "1") \
                                        or (cs.structs["feature_toggles"]["substrate_moisture_sensor"] == "1") \
                                            or (cs.structs["feature_toggles"]["onboard_led"] == "0")):
        minion.start_serial_in()

    #start the clock for timimg .csv writes and data exchanges with server
    data_timer = time.time() - 300

def main_loop():
    #launch main program loop
    try:
        print("Begin environmental data collection and control")
        print("-----------------------------------------------------")
        while True:
            update_derivative_banks() #this occurs in near-realtime, as opposed to storage and exchange every 5 min
            cs.load_state() 
            listen_active_sensors()
            collect_environmental_data()
            update_pid_controllers()
            regulate_active_equipment()
            console_log()
            data_out()
            time.sleep(5)
    except SystemExit:
        print("Core was terminated.")
    except KeyboardInterrupt:
        print("Core interrupted by user.")
    except Exception:
        print("Core encoutered an error!")
        print(err.full_stack())
    finally:
        terminate_program()

if __name__ == '__main__':
    cs.check_lock(resource_name) #Convention should be to do the lock-check here, and signal handlers in loops
    main_setup()
    main_loop()