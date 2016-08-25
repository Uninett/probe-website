#!/bin/bash

# This script customizes a generic Kali Linux ARM image for use for
# wifi monitoring probes. The generated differs from the original one
# by containing:
#   - An init script that should be run at a probe's first boot
#     (the init script makes the probe able to connect to the main server)
#   - An enabled systemd unit file for the init script
#   - The main server user's public ssh key and the server's host key
#   - The server's hostname/address
#   - WiFi driver (8812au)
#   - udev script for shutting down probe when wifi dongle is yanked out


USAGE="Usage: ${0} 
<image file (.img)> 
<wifi dongle driver (.ko)> 
<web server address/hostname> 
<(unprivileged) server user used for reverse ssh> 
<main (privileged) user's public ssh key>"

if [[ ${#} != 5 ]]; then
    echo "${USAGE}"
    exit
fi

if [[ "${EUID}" != 0 ]]; then
    echo "[!] Script must be run as root"
    exit
fi

ORIG_FILENAME="${1}"
WIFI_DRIVER="${2}"
SERVER_ADDRESS="${3}"
SERVER_USER="${4}"
MAIN_PUBKEY="${5}"


echo "[~] Copying image..."
FILENAME="modified_${ORIG_FILENAME}"
cp "${ORIG_FILENAME}" "${FILENAME}"
echo "[+] Done"


echo "[+] Getting image offset"
sector_size=$(fdisk -lu "${FILENAME}" | grep -oP '(?<=Sector size \(logical/physical\): )[0-9]{1,4}')
fs_start=$(fdisk -lu "${FILENAME}" | grep -v '^$' | tail -n 1 | awk '{print $2}')
offset=$((sector_size * fs_start))


echo "[+] Making mount point ${MOUNT_DIR}"
MOUNT_DIR="mnt/"
if [[ ! -d "${MOUNT_DIR}" ]]; then
    mkdir "${MOUNT_DIR}"
fi


echo "[+] Mounting image ${FILENAME} at ${MOUNT_DIR}"
mount -o loop,offset=${offset} "${FILENAME}" "${MOUNT_DIR}"

echo "[+] Transferring init script & pub ssh key"
mkdir -p "${MOUNT_DIR}/root/init/"
cp "probe_init.sh" "${MOUNT_DIR}/root/init/probe_init.sh"
chmod +x "${MOUNT_DIR}/root/init/probe_init.sh"
cp "${MAIN_PUBKEY}" "${MOUNT_DIR}/root/init/main_key.pub"


echo "[+] Transferring server host key (for known_hosts)"
# Remove port part
server_host=$(echo "${SERVER_ADDRESS}" | sed 's/:.*//g')
ssh-keyscan -t rsa localhost | sed "s/localhost/${server_host}/g" > "${MOUNT_DIR}/root/init/host_key"


echo "[+] Transferring wifi driver"
cp "${WIFI_DRIVER}" "8812au.ko"
mv "8812au.ko" ${MOUNT_DIR}/lib/modules/*/kernel/drivers/net/wireless/
if [[ $(grep '8812au' ${MOUNT_DIR}/etc/modules) == "" ]]; then
    echo "8812au" >> "${MOUNT_DIR}/etc/modules"
fi


echo "[+] Generating systemd unit file for init script"
cat << EOF > ${MOUNT_DIR}/etc/systemd/system/probe_init.service
[Unit]
Description=Probe init script
Wants=network-online.target
After=network.target network-online.target

[Service]
Type=simple
ExecStart=/root/init/probe_init.sh ${SERVER_ADDRESS} ${SERVER_USER}
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# This is the same as 'systemctl enable reverse_ssh', just that we don't need
# to run systemctl (we aren't running chroot)
ln -s ${MOUNT_DIR}/etc/systemd/system/probe_init.service ${MOUNT_DIR}/etc/systemd/system/multi-user.target.wants/probe_init.service


# This script makes the rpi shut down when the wifi dongle is ejected.
# This is necessary because the rpi has no on/off switch, but just
# directly cutting the power can cause file corruption, and will
# not close the SSH tunnel properly.
echo "[+] Adding wifi dongle shutdown script"
# These values are specific to the D-Link DWA-171 dongle. To get the
# values, run the command 'udevadm monitor --udev --property' with the
# dongle connected, and then disconnect it. The values will pop up
# at stdout
ID_MODEL_ID=3314
ID_VENDOR_ID=2001
echo 'ACTION=="remove", ENV{ID_VENDOR_ID}=="'"${ID_VENDOR_ID}"'", ENV{ID_MODEL_ID}=="'"${ID_MODEL_ID}"'", RUN+="/sbin/shutdown -h now"' > ${MOUNT_DIR}/etc/udev/rules.d/00-dongle_shutdown.rules


echo "[+] Unmounting image"
umount "${MOUNT_DIR}"


echo "Done!"
