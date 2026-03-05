#/bin/sh -e

echo "Checking Python 3.7 Venv Install..."
/usr/bin/env python3.7 --version
if ! [ $? -eq 0  ]; then
    echo "python3.7 virtualenv not found"
fi

echo "Checking Python 3.7 Venv Packages..."
for packageName in pyserial, python-jwt, requests, Pyrebase, pickle5, Pillow, RPi.GPIO, opencv-python, streamlit, orjson, maturin; do
    if ! [ -d "/home/pi/oasis-rpi/oasis_venv_pi/lib/python3.7/site-packages/$packageName" ]; then
        echo "package '$packageName' not found"
    fi
done

