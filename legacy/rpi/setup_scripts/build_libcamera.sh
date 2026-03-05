#[Development] For Building the Libcamera OS if using Debian RPi OS Buster or Earlier 

#Activate the python virtual environment
. /home/pi/oasis-rpi/oasis_venv_pi/bin/activate

#Install dependencies to operating system
pip3 install meson
pip3 install --upgrade meson
pip3 install pyyaml
sudo apt install -y libyaml-dev python3-yaml python3-ply python3-jinja2 ninja-build pkg-config libgnutls28-dev openssl libdw-dev libunwind-dev libboost-dev libevent-dev libdrm-dev libsdl2-dev libsdl2-image-dev

#Get, Build & Install Libcamera for Raspberry Pi
git clone https://git.libcamera.org/libcamera/libcamera.git
cd libcamera
meson build
ninja -C build install
