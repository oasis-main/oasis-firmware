#!/bin/sh -e

echo "Creating local directories..."
mkdir /home/pi/oasis-rpi/configs
mkdir /home/pi/oasis-rpi/data_out
mkdir /home/pi/oasis-rpi/data_out/image_feed
mkdir /home/pi/oasis-rpi/data_out/sensor_feed
mkdir /home/pi/oasis-rpi/data_out/resource_use
mkdir /home/pi/oasis-rpi/data_out/logs

echo "Moving configuration files..."
cp /home/pi/oasis-rpi/defaults/hardware_config_default_template.json /home/pi/oasis-rpi/configs/hardware_config.json
cp /home/pi/oasis-rpi/defaults/access_config_default_template.json /home/pi/oasis-rpi/configs/access_config.json
cp /home/pi/oasis-rpi/defaults/feature_toggles_default_template.json /home/pi/oasis-rpi/configs/feature_toggles.json
cp /home/pi/oasis-rpi/defaults/device_state_default_template.json /home/pi/oasis-rpi/configs/device_state.json
cp /home/pi/oasis-rpi/defaults/control_params_default_template.json /home/pi/oasis-rpi/configs/control_params.json
cp /home/pi/oasis-rpi/defaults/sensor_data_default_template.json /home/pi/oasis-rpi/configs/sensor_data.json
cp /home/pi/oasis-rpi/defaults/power_data_default_template.json /home/pi/oasis-rpi/configs/power_data.json

#Rusty Pipes will create lockfiles and entries automatically when called
#Should still leave the config setup here so Python can access a default set of keys+values. 
#The default lockfile is good because it'll help keep track of critical sections 
echo "Creating new lock file..."
cp /home/pi/oasis-rpi/defaults/locks_default_template.json /home/pi/oasis-rpi/configs/locks.json
echo "Creating new signal file..."
cp /home/pi/oasis-rpi/defaults/signals_default_template.json /home/pi/oasis-rpi/configs/signals.json

#Permissions for writing
sudo chmod 777 -R /home/pi/oasis-rpi/data_out