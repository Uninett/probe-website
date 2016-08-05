#!/bin/bash

# This script does the following:
#     - Takes a FILENAME as an argument
#         * The file is the (Kali) RPi ARM image
#     - Adds the public SSH key of this computer to
#       the image (so the image must be generated on
#       the same computer that will host the website)
#     - Adds a script to the image that when the rpi
#       boots does:
#         * apt-get update
#         * apt-get install autossh
#         * get wlan mac adress and query web server
#           for port
#         * construct autossh command for reverse ssh
#           with the received port
#         * when all this is done, the probe is ready
#           to be updated with Ansible from the server

USAGE="Usage: $0 <image file (.img)> <wifi dongle driver (.ko)> <(unprivileged) server user used for reverse ssh> <main (privileged) user's public ssh key>"

# Read FILENAME
if [[ $# != 4 ]]; then
    echo "$USAGE"
    exit
fi

if [[ "$EUID" != 0 ]]; then
    echo "[!] Script must be run as root"
    exit
fi

### THIS MUST BE CHANGED ###
SERVER_ADDRESS="localhost:5000"
############################
ORIG_FILENAME="$1"
WIFI_DRIVER="$2"
SERVER_USER="$3"
PUBKEY="$4"


echo "[+] Copying image..."
# FILENAME="modified_$1"
FILENAME="$ORIG_FILENAME"
# cp $1 $FILENAME


echo "[+] Getting image offset"
sector_size=$(fdisk -lu "$FILENAME" | grep -oP '(?<=Sector size \(logical/physical\): )[0-9]{1,4}')
fs_start=$(fdisk -lu "$FILENAME" | tail -n 1 | awk '{print $2}')
offset=$((sector_size * fs_start))


echo "[+] Making mount point $MOUNT_DIR"
MOUNT_DIR="mnt/"
if [[ ! -d "$MOUNT_DIR" ]]; then
    mkdir "$MOUNT_DIR"
fi


echo "[+] Mounting image $FILENAME at $MOUNT_DIR"
mount -o loop,offset=$offset "$FILENAME" "$MOUNT_DIR"

echo "[+] Transferring init script & pub ssh key"
mkdir -p "${MOUNT_DIR}/root/init/"
cp "probe_init.sh" "${MOUNT_DIR}/root/init/probe_init.sh"
chmod +x "${MOUNT_DIR}/root/init/probe_init.sh"
cp "$PUBKEY" "${MOUNT_DIR}/root/init/server_key.pub"


echo "[+] Transferring wifi driver"
cp "$WIFI_DRIVER" ${MOUNT_DIR}/lib/modules/*/kernel/drivers/net/wireless/8812.ko
echo "8812au" >> "${MOUNT_DIR}/etc/modules"


echo "[+] Generating systemd unit file for init script"
echo "
[Unit]
Description=Probe init script

[Service]
Type=simple
ExecStart=/root/init/probe_init.sh ${SERVER_ADDRESS} ${SERVER_USER}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target" > ${MOUNT_DIR}/etc/systemd/system/probe_init.service

# This is the same as 'systemctl enable reverse_ssh', just that we don't need
# to run systemctl (we aren't running chroot)
ln -s ${MOUNT_DIR}/etc/systemd/system/probe_init.service ${MOUNT_DIR}/etc/systemd/system/multi-user.target.wants/probe_init.service

# echo "[+] Adding init script to crontab"
# echo "@reboot root /root/init/probe_init.sh ${SERVER_ADDRESS} ${SERVER_USER}" >> "${MOUNT_DIR}/etc/crontab"


# Unmount the image
echo "[+] Unmounting image"
sudo umount "$MOUNT_DIR"


echo "Done!"
