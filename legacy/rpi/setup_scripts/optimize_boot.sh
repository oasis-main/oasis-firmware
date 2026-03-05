#!/bin/sh -e

echo "Disabling non-essential services at boot..."

sudo systemctl disable apt-daily.service
sudo systemctl disable apt-daily-upgrade.service
sudo systemctl disable man-db.service
echo "Removed apt-daily, apt-daily-upgrade, & man-db."

sudo systemctl disable dphys-swapfile.service
sudo systemctl disable avahi-daemon.service
sudo systemctl disable triggerhappy.service
echo "Removed dphys-swapfile, avahi-daemon, & triggerhappy."

echo "'Use systemd-analyze blame' & 'systemd-analyze critical-chain' to identify time-consuming processes on boot"
echo "Make edits to /boot/config.txt, /boot/cmdline.txt, and /etc/fstab to enable further optimizations"
echo "Editing configuration files carelessly may ruin your system. If making further edits, be warned!"

#References
#https://panther.software/configuration-code/raspberry-pi-3-4-faster-boot-time-in-few-easy-steps/
#https://www.samplerbox.org/article/fastbootrpi
