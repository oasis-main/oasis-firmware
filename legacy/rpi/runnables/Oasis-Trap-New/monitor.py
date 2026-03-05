#Program to wait for a PIR signal, record a video, and send it to the cloud

import time
import sys

sys.path.append("/home/pi/oasis-rpi/")

import rusty_pipes

from imaging import camera
from networking import db_tools as dbt
from networking import firebase_manager
from peripherals import digital_sensors
from utils import concurrent_state as cs

def launch_access_point(): 
    #launch server subprocess to accept credentials over Oasis wifi network, does not wait
    server_process = rusty_pipes.Open(["sudo", "streamlit", "run", "/home/pi/oasis-rpi/networking/connect_oasis.py", "--server.headless=true", "--server.port=80", "--server.address=192.168.4.1", "--server.enableCORS=false", "--server.enableWebsocketCompression=false"],"access_point")
    print("Access Point Mode enabled")

if __name__ == "__main__":
	cs.load_state()
	
	pir = digital_sensors.input(pin = 23, debounce_count=10) #Set up digital PIR sensor

	if cs.structs["access_point"]: #See if we are in access point mode
		launch_access_point()#checks whether system is booting in Access Point Mode, launches connection script if so
		while True:
			time.sleep(1)
			pass #hang forever
	else:
		connected = firebase_manager.connect_to_firebase() #Attempt to connect to wifi/firebase

	connect_timer = time.time()
	reboot_timer = time.time()

	while True: #While true: (there should be minimal loop lag here to interfere with polling)
		if pir.read(): #If PIR is activated
			filename = "motion_captured_at_" + str(time.time()) + ".avi"
			path = "/home/pi/oasis-rpi/data_out/"
			filepath = filename+path
			camera.take_video(filepath, 15) #Start 15s video
			if connected:
				user, db, storage = dbt.initialize_user(cs.structs["access_config"]["refresh_token"])
			dbt.store_file(user, storage, filepath, cs.structs["access_config"]["device_name"], filename) #Post to cloud when done under filename with datetime

		if time.time()-connect_timer >= 3600:
			connect_timer = time.time()
			connected = firebase_manager.connect_to_firebase()

		if time.time()-reboot_timer >=86400:
			reboot_timer = time.time()
			reboot = rusty_pipes.Open[["sudo","reboot"],"reboot"]
		