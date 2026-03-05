#/bin/sh -e

echo "Checking Network connectivity..."
wget -q --spider http://google.com

if [ $? -eq 0 ]; then

   echo "Network is online."

else
    echo "Network is offline."
fi
