#!/bin/sh -e

sudo chmod +x /home/pi/oasis-rpi/setup_scripts

. /home/pi/oasis-rpi/setup_scripts/setup_env.sh
. /home/pi/oasis-rpi/setup_scripts/setup_config.sh
. /home/pi/oasis-rpi/setup_scripts/setup_network.sh

echo "Returning to WiFi mode..."
sudo cp /etc/dhcpcd_wifi.conf /etc/dhcpcd.conf
sudo cp /etc/dnsmasq_wifi.conf /etc/dnsmasq.conf
sudo systemctl disable hostapd
sudo systemctl reboot