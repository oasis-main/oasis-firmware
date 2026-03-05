import sys

#peripherals
import RPi.GPIO as GPIO

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')
sys.path.append('/home/pi/oasis-rpi/core')
sys.path.append('/home/pi/oasis-rpi/utils')

from utils import concurrent_state as cs

#declare UI variables
start_stop_button = None #holds GPIO object for starting and stopping core process
connect_internet_button = None #holds GPIO object for connecting device to internet
action_button = None #holds GPIO object for triggering the desired action

#setup buttons for the main program interface
def setup_button_interface(): #depends on: , 'RPi.GPIO'; modifies: start_stop_button, connect_internet_button, run_action_button, state variables
    global start_stop_button, connect_internet_button, action_button
    
    print("Setting up button interface...")

    #specify gpio pin number mode
    GPIO.setmode(GPIO.BCM)

    #set button pins
    start_stop_button = int(cs.structs["hardware_config"]["button_gpio_map"]["start_stop_button"])
    connect_internet_button = int(cs.structs["hardware_config"]["button_gpio_map"]["connect_internet_button"])
    action_button = int(cs.structs["hardware_config"]["button_gpio_map"]["action_button"])

    #Setup buttons
    GPIO.setup(start_stop_button, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(connect_internet_button,GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(action_button, GPIO.IN, pull_up_down=GPIO.PUD_UP)

#gets the state of a button (returns 1 if not pressed, 0 if pressed)
def get_button_state(button): #Depends on: RPi.GPIO; Modifies: None
    state = GPIO.input(button)
    return state

def test():
    print("This is a unit test for buttons.")
    import time 
    cs.load_state()
    setup_button_interface()
    while True:
        if get_button_state(start_stop_button) == 1:
            print("Core process start/stop button is not pressed...")
        if get_button_state(start_stop_button) == 0:
            print("Core process start/stop button pressed!")
        
        if get_button_state(connect_internet_button) == 1:
            print("Connect internet button is not pressed...")
        if get_button_state(connect_internet_button) == 0:
            print("Connect internet button pressed!")

        if get_button_state(action_button) == 1:
            print("Action (water OR camera) button is not pressed...")
        if get_button_state(action_button) == 0:
            print("Action (water OR camera) button pressed!")

        time.sleep(0.5)

    