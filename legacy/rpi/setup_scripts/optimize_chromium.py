#This is a python script, not a bash file
from webbrowser import open
open("chrome://settings/")
open("chrome://flags/")

print('''Instructuions:

Enable Hardware Acceleration
Access chrome://settings/
On Advanced>System set Use hardware acceleration when available
And click on Restart

GPU Rasterization
Access chrome://flags/
Set GPU Rasterization to Force-enabled for all layers
And click on Relaunch Now''')
