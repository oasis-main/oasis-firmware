#import shell modules
import sys

#set proper path for modules
sys.path.append('/home/pi/oasis-rpi')

#data handling
import re
import time

#import custom modules
import subprocess
from utils import slow_concurrent_state as slow_cs
from utils import error_handler as err

#create a password-protected lan interface for accepting credentials
import streamlit as st

def enable_wifi(): #we're going to use subprocess here because the regular one uses rusty_piped, which is not availabe to root
#tell system that the access point should not be launched on next controller startup
    slow_cs.write_state("/home/pi/oasis-rpiconfigs/device_state.json","access_point","0", db_writer = None)

    #disable WiFi, enable AP, reboot
    config_wifi_dchpcd = subprocess.Popen(["sudo", "cp", "/etc/dhcpcd_wifi.conf", "/etc/dhcpcd.conf"])
    config_wifi_dchpcd.wait()
    config_wifi_dns = subprocess.Popen(["sudo", "cp", "/etc/dnsmasq_wifi.conf", "/etc/dnsmasq.conf"])
    config_wifi_dns.wait()
    disable_hostapd = subprocess.Popen(["sudo", "systemctl", "disable", "hostapd"])
    disable_hostapd.wait()
    systemctl_reboot = subprocess.Popen(["sudo", "systemctl", "reboot"])
    systemctl_reboot.wait()

#update wpa_supplicant.conf
def modWiFiConfig(SSID, password):
    if (SSID == "") or (password == ""):
        print("No wifi creds given, not touching the config file.")
        pass
    else:
        config_lines = [
        'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev',
        'update_config=1',
        'country=US',
        '\n',
        'network={',
        '\tssid="{}"'.format(SSID),
        '\tpsk="{}"'.format(password),
        '\tkey_mgmt=WPA-PSK',
        '}'
        ]

        config = '\n'.join(config_lines)
        #print(config)

        with open("/etc/wpa_supplicant/wpa_supplicant.conf", "r+") as w:
            w.seek(0)
            w.write(config)
            w.truncate()

        print("WiFi configs added")

#update access_config.json
def modAccessConfig(name, e, p):
    if (name == "") or (e == "") or (p == ""):
        print("No access creds given, not touching the config file.")
        return
    else:
        slow_cs.structs["access_config"] = {}
        slow_cs.structs["access_config"]["device_name"] = str(name)
        slow_cs.structs["access_config"]["wak"] = "AIzaSyBPuJwU--0ZlvsbDV9LmKJdYIljwNwzmVk"
        slow_cs.structs["access_config"]["e"] = str(e)
        slow_cs.structs["access_config"]["p"] = str(p)
        slow_cs.structs["access_config"]["refresh_token"] = ""
        slow_cs.structs["access_config"]["id_token"] = ""
        slow_cs.structs["access_config"]["local_id"] = ""

        slow_cs.write_dict("/home/pi/oasis-rpi/configs/access_config.json", slow_cs.structs["access_config"], db_writer = None)

        print("Access configs added")


def save_creds_exit(email, password, wifi_name, wifi_pass, device_name, cmd = False):
    
    device_name = re.sub('[^a-zA-Z0-9\n\.]', ' ', device_name) #sub all non-alphaneumeric characters with spaces
    device_name = device_name.replace(" ","-") #sub all spaces with dashes

    #place credentials in proper locations
    modWiFiConfig(wifi_name, wifi_pass)
    print("Wifi creds added")
    modAccessConfig(device_name, email, password)
    print("Access creds added")
    
    if (email == "") or (password == "") or (wifi_name == "") or (wifi_pass == "") or ( device_name == ""):
        st.warning("You missed some information! Wait until the device reboots, place it back in access point mode, and try again.")
        return
    else:
        st.success("Added WiFi & access credentials to device. Please reconnect computer to internet, leave this page, and log back into https://dashboard.oasis-x.io. If successful, you will see the device name appear under 'Your Fleet.'")
        #set new_device to "1" before rebooting
        slow_cs.write_state("/home/pi/oasis-rpi/configs/device_state.json", "new_device", "1", db_writer = None)

    if cmd == False: #pass this argument as true to save creds without rebooting
        #stand up wifi and reboot
        enable_wifi() #turns off the access point flag, no need to do it here.

if __name__ == '__main__':

        default = "" #empty string

        st.title('Oasis Device Setup')

        email = st.text_input('Oasis Email', default)

        password = st.text_input('Oasis Password', default, type="password")

        wifi_name = st.text_input('Wifi Name', default)

        wifi_pass = st.text_input('Wifi Password', default, type="password")

        device_name = st.text_input('Name this device:', default)

        #st.button('Launch', on_click=save_creds_exit, args=[email, password, wifi_name, wifi_pass, device_name]) #only for recent streamlit versions

        if st.button("Launch"):
            try:
                save_creds_exit(email, password, wifi_name, wifi_pass, device_name)
                time.sleep(5)
            except:
                print(err.full_stack())
                sys.exit()

        slow_cs.check_signal("access_point", "terminated", slow_cs.wrapped_sys_exit)
        