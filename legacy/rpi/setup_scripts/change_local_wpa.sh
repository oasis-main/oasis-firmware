#/bin/sh -e

read -sp "Enter old password: " oldpwd
printf "\n"
pwdline=`grep wpa_passphrase /etc/hostapd/hostapd.conf`

if [ "wpa_passphrase=$oldpwd" = "$pwdline" ]; then
    read -sp "Enter new password: " newpwd
    printf "\n"
    read -sp "Confirm new password: " newpwdconf
    printf "\n"

    if [ "$newpwd" = "$newpwdconf" ]; then
        sudo sed -i "s/$oldpwd/$newpwd/" /etc/hostapd/hostapd.conf
        echo "Password changed."
    else
        echo "Passwords do not match."
    fi
else
    echo "Incorrect password."
fi
