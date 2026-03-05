from cgi import test
import sys

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

import main
from core import core
from utils import concurrent_state as cs
from imaging import camera as cam
from utils import update
from imaging import make_timelapse
from networking import db_tools as dbt

def test_connect():
    print("Testing connect function...")
    main.connect_firebase()

def test_rtdb_patch():
    print("Testing realtime database...")
    cs.load_state()
    dbt.patch_firebase(cs.structs["access_config"], "device_error", "Test Field,Value Patch: Success")
    data = {"device_error": "Test Field,Value Patch: Success"}
    dbt.patch_firebase(cs.structs["access_config"], data)
    dbt.patch_firebase(cs.structs["access_config"], "device_error", "Test Field,Value Patch: Success")

'''
def send_image_test():
    print("Testing image transfer...")
    cam.send_image("/home/pi/oasis-rpi/tests/test.jpg")

def send_csv_test():
    print("Testing csv transfer...")
    core.send_csv("/home/pi/oasis-rpi/tests/test.csv", "test_csv.csv")

def send_timelapse_test():
    print("Testing video transfer...")
    make_timelapse.send_timelapse("/home/pi/oasis-rpi/tests/test.avi")

'''

def test_update():
    print("Testing update functionality...")
    update.get_update()

if __name__ == '__main__':  
    test_connect()
    test_rtdb_patch()
    #send_image_test()
    #send_csv_test()
    #send_timelapse_test()
    test_update()
  
