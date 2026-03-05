#import shell modules
import sys

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

import board
import neopixel
import time

from utils import slow_concurrent_state as slow_cs
from utils import error_handler as err

resource_name = "led"
slow_cs.check_lock(resource_name) #anything GPIO-touching should check the lock before the object is declared

#get hardware config & device state
slow_cs.load_state()
num_leds = int(slow_cs.structs["hardware_config"]["led_settings"]["num_leds"])
pixels = neopixel.NeoPixel(board.D21, num_leds) #NeoPixels must be connected to GPIO10, GPIO12, GPIO18 or GPIO21 to work!

def check_led_status():

    if slow_cs.structs["device_state"]["led_status"] == "off":
        for x in range(0, num_leds):
            pixels[x] = (0, 0, 0)

    #Connected, Running (green, looping)
    if slow_cs.structs["device_state"]["led_status"] == "connected_running":
        for x in range(0, num_leds):
            pixels[x] = (0, 10, 0)
            time.sleep(0.04)
        for x in range(0, num_leds):
            pixels[x] = (0, 5, 0)
            time.sleep(0.04)   
        return

    #Connected, Idle (green, still)
    if slow_cs.structs["device_state"]["led_status"] == "connected_idle":
        for x in range(0, num_leds):
            pixels[x] = (0, 5, 0)
            time.sleep(0.04)
        return

    #Offline, Running (white, looping)
    if slow_cs.structs["device_state"]["led_status"] == "offline_running":
        for x in range(0, num_leds):
            pixels[x] = (10, 10, 10)
            time.sleep(0.04)
        for x in range(0, num_leds):
            pixels[x] = (5, 5, 5)
            time.sleep(0.04)   
        return

    #Offline, Idle (white, still)
    if slow_cs.structs["device_state"]["led_status"] == "offline_idle":
        for x in range(0, num_leds):
            pixels[x] = (5, 5, 5)
            time.sleep(0.04)
        return

    #Master sends error message (red, still)
    if slow_cs.structs["device_state"]["led_status"] == "error":
        for x in range(0, num_leds):
            pixels[x] = (5, 0, 0)
            time.sleep(0.04)
        return

    #AP-mode, Server accepting connections (blue, looping)
    if slow_cs.structs["device_state"]["led_status"] == "accepting_wifi_connection":
        for x in range(0, num_leds):
            pixels[x] = (0, 0, 10)
            time.sleep(0.04)
        for x in range(0, num_leds):
            pixels[x] = (0, 0, 5)
            time.sleep(0.04)   
        return

def clean_up(final = True): #signal is not used to terminate this, rather a flag is set from the outside
    for x in range(0, num_leds): #kill the neopixels (turn all off)
        pixels[x] = (0, 0, 10)
        time.sleep(0.04)
    for x in range(0, num_leds):
        pixels[x] = (0, 0, 5)
        time.sleep(0.04)   
    
    slow_cs.unlock(slow_cs.lock_filepath, resource_name) #free the leds for system
    
    if final:
        slow_cs.wrapped_sys_exit()

def run():
    while True:
        print("Checking signal...")
        slow_cs.check_signal("led","terminated", clean_up) #the custom termination signal must ALWAYS be acknowledged otherwise we will get repeat behavior
        print("Adjustibg led to status...")
        check_led_status()
        print("Loading concurrent state (slow)...")
        slow_cs.load_state()
        time.sleep(1)

if __name__ == '__main__':
    try:
        run()
    except SystemExit:
        print("LED was terminated.")
    except KeyboardInterrupt:
        print("Shutting down LED...")
        clean_up(final=False)
        slow_cs.write_state("/home/pi/oasis-rpi/configs/signals.json","led","acknowleged")
    except Exception:
        print("LED encountered an error!")
        print(err.full_stack())
