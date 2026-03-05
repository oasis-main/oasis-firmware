import sys
import os.path
import multiprocessing

#set proper path for modules
sys.path.append("/home/pi/oasis-rpi")

import main
from networking import connect_oasis

if __name__ == '__main__':

    print("Testing local setup server to receive creds...")
    server_test = multiprocessing.Process(target = main.launch_access_point)
    server_test.start()

    print("Testing credential-adding functionality")
    email = input("Enter Oasis-X user email: ")
    password = input("Enter Oasis-X user password: ")
    wifi_name = input("Enter wifi name: ")
    wifi_pass = input("Enter wifi password: ")
    device_name = input("Name this device: ")

    connect_oasis.save_creds_exit(email, password, wifi_name, wifi_pass, device_name, cmd = True)

    server_test.kill()
