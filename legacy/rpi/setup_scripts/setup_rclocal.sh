#!/bin/sh -e

sudo chmod +w /etc/rc.local
sudo sed -ie "/^fi/a . /home/pi/oasis-rpi/start.sh &" /etc/rc.local
sudo sed -ie "/^fi/a sleep 15" /etc/rc.local
sudo sed -ie "/^fi/a chmod +x /home/pi/oasis-rpi/start.sh" /etc/rc.local
sudo sed -ie "/^fi/a hwclock -s" /etc/rc.local
