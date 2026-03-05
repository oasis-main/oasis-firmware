# Oasis Firmware

**Configuration-driven firmware generation for IoT devices with KiCAD integration.**

Oasis Firmware is a unified hardware management framework that supports:
- **Multi-platform**: ESP32, Raspberry Pi, Arduino, STM32
- **Declarative config**: Define devices in YAML, generate firmware code
- **Simulation**: Wokwi simulation configs for ESP32
- **KiCAD integration**: Import PCB designs, export scaffolds, junction advisor
- **Legacy support**: Preserved Python RPi toolkit and Arduino sensor templates

## Architecture

```
oasis-firmware/
├── src/                    # Rust firmware generator (oasis-build CLI)
├── examples/               # device.yaml examples (greenhouse, drone)
├── docs/                   # Schema docs, deployment guide, desktop app design
├── kicad_bridge/           # Python KiCAD integration tools
└── legacy/
    ├── rpi/                # Original Python RPi toolkit (oasis-grow)
    └── ino/                # Arduino sensor templates (oasis-ino)
```

## Quick Start

### New Projects (Recommended)

1. Define your device in YAML (see `examples/`):
```yaml
device:
  id: my-greenhouse
  board: { platform: mcu, model: esp32_devkit }
sensors:
  - name: temp_humidity
    type: dht22
    pins: { data: 4 }
```

2. Validate and generate firmware:
```bash
cargo run --bin oasis-build -- validate --config device.yaml
cargo run --bin oasis-build -- generate --config device.yaml --output ./build/
```

3. Flash to device (see `docs/DEPLOYMENT.md`)

### KiCAD Integration

```bash
cd kicad_bridge && pip install -e .

# Import existing PCB to device.yaml
oasis-kicad import ./my-project.kicad_pro --output device.yaml

# Generate KiCAD scaffold from device.yaml
oasis-kicad scaffold --config device.yaml --output ./kicad/

# Get connector/cable/enclosure recommendations
oasis-kicad review --config device.yaml
```

### Legacy RPi Toolkit

The original Python-based RPi toolkit is preserved in `legacy/rpi/`:

```bash
cd legacy/rpi
. install.sh
. start.sh
```

See `legacy/rpi/README.md` for full documentation.

## Documentation

- [Device Schema](docs/DEVICE_SCHEMA.md) - YAML configuration reference
- [Deployment Guide](docs/DEPLOYMENT.md) - Flashing and deployment techniques
- [Desktop App Design](docs/DESKTOP_APP_DESIGN.md) - Planned egui desktop application

## Supported Platforms

| Platform | Generator | Simulation | Deployment |
|----------|-----------|------------|------------|
| ESP32    | Rust (embassy) | Wokwi | espflash, OTA |
| RPi      | Rust (tokio) | mock_gpio | SSH, systemd |
| Arduino  | C++ templates | - | arduino-cli |
| STM32    | Rust (embassy) | - | probe-rs |

## Contributing

We encourage users to contribute data, projects, and technical expertise. Open-source contributors are welcome!

## Legacy Documentation

  - [Introduction](#introduction)
  - [Raspberry Pi Setup](#raspberry-pi-setup)
    - [Using pre-built image](#using-pre-built-image)
    - [Using setup scripts](#using-setup-scripts)
  - [Hardware Setup](#hardware-setup)
    - [Arduino Setup](#arduino-setup)
    - [DIY Wiring](#diy-wiring)
  - [Usage](#Usage)
    - [Button Interface](#button-interface)
  - [Configuration](#configuration)
  - [Sample Projects](#sample-projects)
  - [Contributing](#contributing)

## Raspberry Pi Setup
Users may using the [setup scripts](scripts) to build the repository and its requirements onto a fresh install of Raspbian Buster Lite (Release 05/07/2021). A pre-built image will be released alongside our next generation of devices for easier setup and deployment.

### Using Setup Scripts

Install Raspbian Lite onto your Raspberry Pi:
1. Download Buster Lite from [official download site](https://www.raspberrypi.org/software/operating-systems/). The firmware will not work on newer releases which utilize LibCamera instead of raspi-still.
2. Download [Balena Etcher](https://www.balena.io/etcher/).
3. Connect a microSD card to your personal computer.
4. Format the microSD card in the MS-DOS (FAT) style using your operating system's disk formatting utility.
5. Open Balena Etcher and follow the on-screen instructions to flash the image to your microSD.
6. Place the SD card into the front slot of the Raspberry Pi.
7. Connect a keyboard, monitor, and sufficient power supply to the Pi.
   
Wait for the Pi to boot, then enter the following when prompted for a username and password:
```
raspberrypi login: pi
Password: raspberry
```
When the prompt appears, enter `sudo raspi-config`. Using the arrow keys to navigate, set `Localisation Options > WLAN Country` according to your locale. Next, select `Interface Options > Camera` and turn the camera on. Finally, select `System Options > Wireless LAN` and enter the name and password for your home WiFi network.

**1. Setup Rasppberry Pi**

Download 32-bit Raspberry Pi OS Lite and double click to uncompress: 
https://downloads.raspberrypi.org/raspios_lite_armhf/images/raspios_lite_armhf-2022-04-07/2022-04-04-raspios-bullseye-armhf-lite.img.xz

Use Disk Utility or an equivalent tool to format a micro SD card to MS-DOS(FAT), download the Raspberry Pi Imager (https://www.raspberrypi.com/software/), open the application, and follow onscreen instructions to flash the OS image obtained in step 1. 

Connect to the Raspberry Pi via HDMI monitor & keyboard (or your preferred setup), plug it in, and log in with the default password ('pi', 'raspberry') on RPiOS Buster or set your own password (default in RPiOS Bullseye). Enter:

1. Setup your Raspberry Pi:


```
sudo raspi-config
```


**2. Install oasis-rpi**

- Set up your internet: System Options -> Wireless LAN -> follow prompt
- Set up your camera: Interface Options -> Legacy Camera  -> Yes
- (Optional, recommended) security: System Options -> Password  -> follow prompt
- (Optional) remote access: Interface Options -> SSH  -> Yes
- (Optional) remote access: Interface Options -> Remote GPIO  -> Enable
- (Optional) on-device peripherals: Interface Options -> I2C  -> Yes  
- (Optional) on-device peripherals: Interface Options -> SPI  -> Yes  


```
sudo apt-get update -y
sudo apt-get install git -y
git clone https://github.com/oasis-main/oasis-rpi.git 
cd oasis-rpi
. install.sh
```

To test if the installation went smoothly:

```
cd oasis-rpi
. start.sh
```

If successful, the above should run a second setup flow that ends with a statement indicating the "core process is deactivated."

**3. Configure Microcontroller, Peripheral Devices, Activated Features, and Startup**

If you plan on using sensors, then the microcontroller (usually an arduino) should manage them and print the data it collects to serial as a dict/json, which is received by the RPi.

For example:
'''
{"temperature": "0",
"humidity": "0",
"vpd": "0",
"water_low": "0",
"co2": "0",
"lux": "0",
"ph": "0",
"substrate_moisture": "0",
"tds": "0"}
'''

is a valid data format for the arduino to output. It can alo take a command from the RPi to control Neopixel LEDs as the headless status indicator. All valid measurement types can be found in the "sensor_data.json" file that was created in the "configs" folder on install.

You can configure all of this yourself, or follow these instructions and use one of our example programs in the 'minions' folder.
1. Download the Arduino IDE (on your personal computer) from the [official download site](www.arduino.cc/en/software).
2. Plug the Arduino into your personal computer via USB.
3. Select and download one of the c++ sketch folders found in the "minions" directory. The functions of each are indicated with the naming convention "Oasis_component1_component2.ino"
4. Install the required libraries using Arduino IDE or your tool of choice, the compile upload your sketch onto the board.
5. Plug the Arduino into the Pi via USB. The Pi will automatically establish a connection and communicate with the arduino on program startup.

The oasis-rpi software is configured to use GPIO Pins for interfacing with relays and push buttons. The pin mapping is given in hardware_config.json:

'''
{"equipment_gpio_map": {
                   "heat_relay": 14,
                   "humidifier_relay": 15,
                   "fan_relay": 18,
                   "light_relay": 23,
                   "water_relay": 24,
                   "air_relay": 25,
                   "dehumidifier_relay": 8
                   },
"button_gpio_map": {
                 "start_stop_button": 17,
                 "connect_internet_button": 27,
                 "action_button": 22
                 }
}
'''

Capable makers can wire this up themselves as described in the [prototype wiring diagram](https://docs.google.com/presentation/d/1E4D3Sl3dR-raVRRaoH5YC-TudYASd4O9N7d49p5N9X8/edit?usp=sharing), or purchase specialty ready-to-go hardware from us directly.

Note: We focus on integrating a faily standard set of popular AC relays for powering high-power electronic appliances. Assemble the AC Relay & Power Circuit at your own risk. Wiring up alternating current from power mains is extremely dangerous, so much that a single mistake can lead to serious injury or even death! Because of this, we recommend doing the AC part of this project only if you are an INTERMEDIATE to ADVANCED engineer only. If you or someone on your team does not have experience working with high voltage, please consult a professional electrician before doing so. You can also sub out any normally-closed DC relay which will take a digital, or simply deploy the camera and sensor modules separately for data collection without power control. You can choose what you use!

oasis-rpi comes with imaging capabilities that make us of the Raspberry Pi's built-in camera stack. You can view these utilities in the "imaging" folder, and toggle the NDVI in feature_toggles,json(more on this next), which is an image analysis technique that can be used to diagnose plant health in the near-infrared using the Pi Noir Camera. 

Finally, edit "feature_toggles.json" in 'configs' to tell the system what capabilities you are using (and which ones you are not, as they are not set up). The ones listed here are currently available. Please see the minions folder for compatible microcontroller programs.

'''
{"temperature_sensor": "1",
"humidity_sensor": "1",
"vpd_calculation": "1",
"water_level_sensor": "1",
"co2_sensor": "1",
"lux_sensor": "1",
"ph_sensor": "0",
"tds_sensor": "0",
"substrate_moisture_sensor": "0",
"heater": "1",
"heat_pid": "1",
"humidifier": "1",
"hum_pid": "1",
"dehumidifier": "1",
"dehum_pid": "1",
"fan": "1",
"fan_pid": "1",
"light": "1",
"water": "1",
"water_pid": "1",
"air": "1",
"camera": "1",
"ndvi": "1",
"save_images": "1",
"save_data": "1",
"onboard_led": "0",
"debug": "0",
"action_button": "1",
"action_water": "1",
"action_camera": "0"}
'''

Now run your configuration of the core program with

'''
cd oasis-rpi
source oasis_venv_pi/bin/activate
python3 main.py run
'''

You should see the core process start and run without error, with the exception of a single python 'requests' dependency conflict. Check to make sure everything is functioning as expected.

Now that we know the main and core process can run without errors, let's create an background process to run when the Pi boots up (runs through systemd):

```
. setup_scripts/optimize_boot.sh
. setup_scripts/setup_systemd.sh
sudo reboot
```

Alternatively, use these commands (runs through rc.local):

```
. setup_scripts/optimize_boot.sh
. setup_scripts/setup_rclocal.sh
sudo reboot
```

**4. Use with Local API & Button Interface (internet not required)**

To start the core process and begin collecting data + contolling your environment, you can press the 'start_stop' button on your system.
Alternatively, open up a python3 shell in the oasis-rpi directory and run:

```
import api
api.start_core()
api.stop_core()
```

You can use this api to change device settings, fetch data, and connect to the Oasis Network. To view all available features, take a look at api.py or open a python terminal and run:
'''
import api
dir(api)
'''

**5. Use with Oasis Network for Dashboard, Remote Monitoring, & AI (internet required)**

Press the 'connect_internet' button on your system. Alternatively, you may open up a python3 shell in the oasis-rpi directory and run:

```
import api
api.connect_device()
```

The device will reboot as an access point, at which point you may connect to the 'Oasis-X' local wifi network. The password is 'community' and can be changed by running /setup_scripts/change_local_wpa.sh

Once connected, open up a new tab and navigate to http://192.168.4.1/ Enter your oasis email, oasis password, local wifi name, local wifi password, and hit the launch button. You'll get a success message and the wifi network should dissapear within a minute

Rejoin your normal internet and go to https://dashboard.oasis-x.io/ to view and control your device.

## Sample Projects
oasis-rpi provides a highly modular interface with countless possible applications as well as a gallery of existing oasis-rpi applications:
- time-lapse cameras
- incubators
- mushroom growing chambers
- hydroponic gardens
- outdoor environmental monitoring
- petri desh habitats
- automated irrigation
- much more!

If successful, the above should run a setup flow that ends with a statement indicating the "core process is deactivated."

## Contributing

We encourage users to contribute data, projects, and technical expertise. Open-source contributors are welcome, and we are currently accepting pull requests! Contact hello@oasis-x.com with questions or proposals.
