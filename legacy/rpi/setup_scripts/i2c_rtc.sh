#!/bin/sh -e

#load module on boot
echo rtc-pcf85363 | sudo tee -a /etc/modules

#bind rtc to i2c bus
echo rtc-pcf85363 0x51 | sudo tee /sys/class/i2c-adapter/i2c-1/new_device
