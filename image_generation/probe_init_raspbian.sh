#!/bin/bash

# This script should be run once (and as root), when the probe boots up for the first time
# It does the following things:
#    - Install wifi driver
#    - Enable ssh and permit remote root login (this is disabled on Raspbian by default)
#    - Install curl & autossh
#    - Generate SSH key pair
#    - Gather wlan0 MAC address
#    - Register pub SSH key with server (identify with MAC)
#    - If registration successful, receive a port number
#    - Generate an autossh command (rev. SSH) with the received port, and
#      wrap it in a systemd unit file
#    - Initiate SSH tunnel to dummy user on server and idle (the tunnel
#      will be degenerate -> /bin/false as shell)


USAGE="${0} <web/ansible server adress> <(unprivileged) user on server used for reverse SSH>"

SERVER_ADDRESS="${1}"
SERVER_USER="${2}"

function log_error {
    echo "[!] ${0}: ${1}"
    logger "[!] ${0}: ${1}"
}

if [[ $# != 2 ]]; then
    echo "${USAGE}"
    exit
fi


echo "[+] Make connection status script executable"
chmod +x /root/connection_status.sh


echo "[+] Installing necessary programs"
# To avoid being presented with stuff like ncurses dialogs, that
# will halt the installation
export DEBIAN_FRONTEND=noninteractive

# DO NOT continue if this doesn't update properly. It will cause
# dependency issues with curl!!!
if [[ ! $(apt-get update) ]]; then
    exit 1
fi

apt-get --yes --allow-unauthenticated install curl dnsutils jq

# Sometimes required when apt-get fails to update and install correctly
apt-get update --yes --fix-missing
apt-get --yes --allow-unauthenticated install curl dnsutils jq

echo "[+] Configure boot to fully disable internal wifi card"
echo "dtoverlay=pi3-disable-wifi"  > ${MOUNT_DIR}/boot/config.txt


echo "[+] Installing wifi driver"
chmod +x /usr/bin/install-wifi
install-wifi


echo "[+] Enable ssh and permit remote acess to root user"
# Configure ssh to permit root login
sed -i 's/PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config

# Deny ssh for the "pi" user to prevent security issues with using default password to connect with ssh
echo "DenyUsers pi" >> /etc/ssh/sshd_config

# ssh must be enabled because it is disabled by default
systemctl enable ssh

# Restart ssh to ensure changes are applied, and to ensure that ssh is running.
service ssh restart


if [[ ! -f ~/.ssh/id_rsa ]]; then
    echo "[+] Generating ssh keys"
    echo "y" | ssh-keygen -q -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
fi
echo "[+] Adding server ssh keys as auth and known"
cp "/root/init/main_key.pub" "/root/.ssh/authorized_keys"
cp "/root/init/host_key" "/root/.ssh/known_hosts"


echo "[+] Gathering wlan MAC address"
mac=$(ifconfig wlan0 | grep -oE '([[:xdigit:]]{1,2}:){5}[[:xdigit:]]{1,2}' | sed 's/://g')
# The test checks wether this is the internal wireless card
if [[ "${mac}" == "" || -e /sys/class/net/wlan0/phy80211/device/driver/module/drivers/usb\:brcmfmac ]]; then
    mac=$(ifconfig wlan1 | grep -oE '([[:xdigit:]]{1,2}:){5}[[:xdigit:]]{1,2}' | sed 's/://g')
    if [[ "${mac}" == "" ]]; then
        log_error "Unable to read wlan MAC"
        exit 1
    fi
fi


pub_key=$(cat /root/.ssh/id_rsa.pub)
host_key=$(ssh-keyscan -t rsa localhost)

while true; do
    echo "[~] Attempting to register ssh key with server"
    resp=$(curl -s "https://${SERVER_ADDRESS}/register_key" --data-urlencode "mac=${mac}" --data-urlencode "pub_key=${pub_key}" --data-urlencode "host_key=${host_key}")

    if [[ ${?} -eq 35 ]]; then
        # SSL is not available
        resp=$(curl -s "http://${SERVER_ADDRESS}/register_key" --data-urlencode "mac=${mac}" --data-urlencode "pub_key=${pub_key}" --data-urlencode "host_key=${host_key}")
    fi

    if [[ "${resp}" != "success" ]]; then
        log_error "Error when registering key: ${resp}"
        # Continue if the probe has already been registered
        if [[ "${resp}" == "already-registered" ]]; then
            echo "[*] Already registered"
            break
        # Start over if some values are invalid (systemd will restart the script for us)
        elif [[ "${resp}" == "invalid-pub-key" || "${resp}" == "invalid-host-key" ]]; then
            exit 1
        fi
        # Otherwise wait and try again (e.g. if the rpi couldn't contact the server,
        # or the association time had expired)
        sleep 20
    else
        echo "[+] Success"
        break
    fi
done


while true; do
    echo "[~] Asking server for available ssh port"
    ssh_port=$(curl -s "https://${SERVER_ADDRESS}/get_port?mac=${mac}")
    if [[ ! "${ssh_port}" =~ [0-9]{1,5} ]]; then
        log_error "Error when querying for port: ${ssh_port}"
        if [[ "${ssh_port}" == "invalid-mac" ]]; then
            exit 1
        fi
        sleep 20
    else
        echo "[+] Port received"
        break
    fi
done


echo "[+] Generating autossh systemd unit file & enabling it"
# Separate host & port (for address like 192.168.0.1:12345)
server_host=$(echo "${SERVER_ADDRESS}" | sed 's/:.*//g')

cat << EOF > /etc/systemd/system/reverse_ssh.service
[Unit]
Description=Starts a reverse ssh connection to the ansible server
Wants=network-online.target
After=network.target network-online.target

[Service]
Type=simple
ExecStart=/root/init/create_ssh_tunnel.sh ${SERVER_USER} ${server_host} ${ssh_port}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl enable reverse_ssh

echo "[+] Add shutdown script for the wifi adapter"
adapter=$(lsusb | grep -i '2357:010C\|056E:4008\|2001:3311\|0DF6:0076\|2001:3310\|2001:330F\|07B8:8179\|0BDA:0179\|0BDA:8179\|0411:025D\|2019:AB32\|7392:A813\|056E:4007\|0411:0242\|0846:9052\|056E:400F\|056E:400E\|0E66:0023\|2001:3318\|2001:3314\|04BB:0953\|7392:A812\|7392:A811\|0BDA:0823\|0BDA:0820\|0BDA:A811\|0BDA:8822\|0BDA:0821\|0BDA:0811\|2357:0122\|148F:9097\|20F4:805B\|050D:1109\|2357:010D\|2357:0103\|2357:0101\|13B1:003F\|2001:3316\|2001:3315\|07B8:8812\|2019:AB30\|1740:0100\|1058:0632\|2001:3313\|0586:3426\|0E66:0022\|0B05:17D2\|0409:0408\|0789:016E\|04BB:0952\|0DF6:0074\|7392:A822\|2001:330E\|050D:1106\|0BDA:881C\|0BDA:881B\|0BDA:881A\|0BDA:8812\|2357:0109\|2357:0108\|2357:0107\|2001:3319\|0BDA:818C\|0BDA:818B\|148F:7650\|0B05:17D3\|0E8D:760A\|0E8D:760B\|13D3:3431\|13D3:3434\|148F:6370\|148F:7601\|148F:760A\|148F:760B\|148F:760C\|148F:760D\|2001:3D04\|2717:4106\|2955:0001\|2955:1001\|2955:1003\|2A5F:1000\|7392:7710\|0E8D:7650\|0E8D:7630\|2357:0105\|0DF6:0079\|0BDB:1011\|7392:C711\|20F4:806B\|293C:5702\|057C:8502\|04BB:0951\|07B8:7610\|0586:3425\|2001:3D02\|2019:AB31\|0DF6:0075\|0B05:17DB\|0B05:17D1\|148F:760A\|148F:761A\|7392:B711\|7392:A711\|0E8D:7610\|13B1:003E\|148F:7610\|0E8D:7662\|0E8D:7632\|0B05:17C9\|0E8D:7612\|045E:02E6\|0B05:17EB\|0846:9053\|0B05:180B\|0846:9014')
if [[ $adapter ]]; then
    id=$(echo $adapter | awk '{ print$6 }')
    ID_VENDOR_ID=$(echo $id | cut -d ':' -f 1)
    ID_MODEL_ID=$(echo $id | cut -d ':' -f 2)
    echo 'ACTION=="remove", ENV{ID_VENDOR_ID}=="'"${ID_VENDOR_ID}"'", ENV{ID_MODEL_ID}=="'"${ID_MODEL_ID}"'", RUN+="/sbin/shutdown -h now"' > /etc/udev/rules.d/00-dongle_shutdown.rules
fi


# Prevent this script from running on subsequent boots
echo "[+] Disabling this init script"
systemctl disable probe_init


echo "[+] Starting a reverse ssh connection with autossh"
systemctl start reverse_ssh
