#!/bin/sh -e

#Overclock
#https://magpi.raspberrypi.com/articles/how-to-overclock-raspberry-pi-4

#Add overclocking to /boot/config.txt
sudo chmod +w /boot/config.txt
sudo sed -ie "/^fi/a arm_freq=1750" /boot/config.txt
sudo sed -ie "/^fi/a over_voltage=2" /boot/config.txt

#Reboot
sudo reboot
