#!/bin/sh -e

echo "Creating systemd unit file..."
printf "
[Unit]
Description= oasis-rpi Firmware

[Service]
ExecStart= /bin/sh /home/pi/oasis-rpi/start.sh  #in this line specify the path to the script.
StandardOutput=journal+console
StandardError=inherit

[Install]
WantedBy=multi-user.target
" | sudo tee /etc/systemd/system/oasis-rpi.service

sudo systemctl enable oasis-rpi
sudo systemctl start oasis-rpi
sudo systemctl status oasis-rpi

#References
#https://stackoverflow.com/questions/37585758/how-to-redirect-output-of-systemd-service-to-a-file
#
#DefaultDependencies=false
#Type=simple
