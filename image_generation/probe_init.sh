#!/bin/bash

# This script should be run once (and as root), when the probe boots up for the first time

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


echo "[+] Installing wifi driver"
depmod
modprobe 8812au


echo "[+] Installing necessary programs"
export DEBIAN_FRONTEND=noninteractive

# DO NOT continue if this doesn't update properly. It will cause
# dependency issues with curl!!!
apt-get update

apt-get --yes --allow-unauthenticated install autossh curl


if [[ ! -f ~/.ssh/id_rsa ]]; then
    echo "[+] Generating ssh keys"
    echo "y" | ssh-keygen -q -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
fi
echo "[+] Adding server ssh keys as auth and known"
cp "/root/init/main_key.pub" "/root/.ssh/authorized_keys"
cp "/root/init/host_key" "/root/.ssh/known_hosts"


echo "[+] Gathering wlan MAC address"
mac=$(ifconfig wlan0 | grep -oE '([[:xdigit:]]{1,2}:){5}[[:xdigit:]]{1,2}' | sed 's/://g')
# The REALTEK check is to prevent selection of the interval wifi card on the rpi3
if [[ "${mac}" == "" || $(iwconfig wlan0 | grep REALTEK) == "" ]]; then
    mac=$(ifconfig wlan1 | grep -oE '([[:xdigit:]]{1,2}:){5}[[:xdigit:]]{1,2}' | sed 's/://g')
    if [[ "${mac}" == "" || $(iwconfig wlan1 | grep REALTEK) == "" ]]; then
        log_error "Unable to read wlan MAC"
        exit 1
    fi
fi


pub_key=$(cat /root/.ssh/id_rsa.pub)
host_key=$(ssh-keyscan -t rsa localhost)

while true; do
    echo "[~] Attempting to register ssh key with server"
    resp=$(curl -s "http://${SERVER_ADDRESS}/register_key" --data-urlencode "mac=${mac}" --data-urlencode "pub_key=${pub_key}" --data-urlencode "host_key=${host_key}")

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
    ssh_port=$(curl -s "http://${SERVER_ADDRESS}/get_port?mac=${mac}")
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


# echo "[+] Adding autossh cmd to crontab"
echo "[+] Generating autossh systemd unit file & enabling it"
# Separate host & port (line in 192.168.0.1:12345)
server_host=$(echo "${SERVER_ADDRESS}" | sed 's/:.*//g')
autossh_cmd="autossh -M 0 -N -T -R${ssh_port}:localhost:22 ${SERVER_USER}@${server_host}"

cat << EOF > /etc/systemd/system/reverse_ssh.service
[Unit]
Description=Starts a reverse ssh connection to the ansible server
Wants=network-online.target
After=network.target network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/autossh -M 0 -N -T -R${ssh_port}:localhost:22 ${SERVER_USER}@${server_host}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl enable reverse_ssh


# Prevent this script from running on subsequent boots
echo "[+] Disabling this init script"
systemctl disable probe_init


echo "[+] Starting a reverse ssh connection with autossh"
systemctl start reverse_ssh
