#!/bin/bash

# This script should be run once (and as root), when the probe boots up for the first time

USAGE="${0} <web/ansible server adress> <(unprivileged) user on server used for reverse SSH>"

SERVER_ADDRESS="$1"
SERVER_USER="$2"

function log_error {
    echo "[!] $0: $1"
    logger "[!] $0: $1"
}

if [[ $# != 2 ]]; then
    echo "$USAGE"
    exit
fi


echo "[+] Running depmod & installing necessary programs"
depmod
apt-get update
apt-get --yes install autossh curl


if [[ ! -f ~/.ssh/id_rsa ]]; then
    echo "[+] Generating ssh keys"
    echo "y" | ssh-keygen -q -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
fi
cp "/root/init/main_key.pub" "/root/.ssh/authorized_keys"
cp "/root/init/host_key" "/root/.ssh/known_hosts"


echo "[+] Gathering wlan MAC address"
mac=$(ifconfig wlan0 | grep -oE '([[:xdigit:]]{1,2}:){5}[[:xdigit:]]{1,2}' | sed 's/://g')
# The REALTEK check is to prevent selection of the interval wifi card on the rpi3
if [[ "$mac" == "" || $(iwconfig wlan0 | grep REALTEK) == "" ]]; then
    mac=$(ifconfig wlan1 | grep -oE '([[:xdigit:]]{1,2}:){5}[[:xdigit:]]{1,2}' | sed 's/://g')
    if [[ "$mac" == "" || $(iwconfig wlan1 | grep REALTEK) == "" ]]; then
        log_error "Unable to read wlan MAC"
        exit
    fi
fi


echo "[+] Registering ssh key with server"
pub_key=$(cat /root/.ssh/id_rsa.pub)
host_key=$(ssh-keyscan -t rsa localhost)
reg_resp=$(curl -s "http://${SERVER_ADDRESS}/register_key" --data-urlencode "mac=${mac}" --data-urlencode "pub_key=${pub_key}" --data-urlencode "host_key=${host_key}")

if [[ "$reg_resp" != "success" ]]; then
    log_error "Error when registering key: $reg_resp"
    # Continue if the error is already-registered; otherwise quit
    if [[ "$reg_resp" != "already-registered" ]]; then
        exit
    fi
fi


echo "[+] Asking server for available ssh port"
ssh_port=$(curl -s "http://${SERVER_ADDRESS}/get_port?mac=${mac}")
if [[ ! "$ssh_port" =~ [0-9]{1,5} ]]; then
    log_error "Error when querying for port: $ssh_port"
    exit
fi


# echo "[+] Adding autossh cmd to crontab"
echo "[+] Generating autossh systemd unit file & enabling it"
# Separate host & port (line in 192.168.0.1:12345)
server_host=$(echo "$SERVER_ADDRESS" | sed 's/:.*//g')
autossh_cmd="autossh -M 0 -N -T -R${ssh_port}:localhost:22 ${SERVER_USER}@${server_host}"

echo "
[Unit]
Description=Starts a reverse ssh connection to the ansible server

[Service]
Type=simple
ExecStart=/usr/bin/autossh -M 0 -N -T -R${ssh_port}:localhost:22 ${SERVER_USER}@${server_host}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target" > /etc/systemd/system/reverse_ssh.service

systemctl enable reverse_ssh


# Prevent this script from running on subsequent boots
# (removes the last line in the crontab)
echo "[+] Disabling this init script"
# sed -i '$d' "/etc/crontab"
systemctl disable probe_init


echo "[+] Starting a reverse ssh connection with autossh"
systemctl start reverse_ssh
