#For setting up binary sensors (Water Level, PIR, Pressure Plate, Switch, etc.)
#Handle the high and low for each sensor case

import sys

sys.path.append("/home/pi/oasis-rpi")

import rusty_pins

def input(pin: int, debounce_count: int):
    input = rusty_pins.GpioIn(pin, debounce_count)
    return input

