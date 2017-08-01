 #!/bin/bash

# This script customizes a generic Raspbian Linux ARM image for use for
# wifi monitoring probes. The generated differs from the original one
# by containing:
#   - An init script that should be run at a probe's first config.txt
#     (the init script makes the probe able to connect to the main server)
#   - An enabled systemd unit file for the init script
#   - The main server user's public ssh key and the server's host key
#   - The server's hostname/address


USAGE="Usage: ${0}
<image file (.img)>
<web server address/hostname>
<(unprivileged) server user used for reverse ssh>
<main (privileged) user's public ssh key>"

if [[ ${#} != 4 ]]; then
    echo "${USAGE}"
    exit
fi

if [[ "${EUID}" != 0 ]]; then
    echo "[!] Script must be run as root"
    exit
fi

ORIG_FILENAME="${1}"
SERVER_ADDRESS="${2}"
SERVER_USER="${3}"
MAIN_PUBKEY="${4}"


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

cp "probe_init_raspbian.sh" "${MOUNT_DIR}/root/init/probe_init_raspbian.sh"
chmod +x "${MOUNT_DIR}/root/init/probe_init_raspbian.sh"
cp "create_ssh_tunnel.sh" "${MOUNT_DIR}/root/init/create_ssh_tunnel.sh"
chmod +x "${MOUNT_DIR}/root/init/create_ssh_tunnel.sh"

cp "${MAIN_PUBKEY}" "${MOUNT_DIR}/root/init/main_key.pub"


echo "[+] Transferring server host key (for known_hosts)"
# Remove port part
server_host=$(echo "${SERVER_ADDRESS}" | sed 's/:.*//g')
ssh-keyscan -t rsa ${server_host} > "${MOUNT_DIR}/root/init/host_key"


echo "[+] Generating systemd unit file for init script"
cat << EOF > ${MOUNT_DIR}/etc/systemd/system/probe_init.service
[Unit]
Description=Probe init script
Wants=network-online.target
After=network.target network-online.target

[Service]
Type=simple
ExecStart=/root/init/probe_init_raspbian.sh ${SERVER_ADDRESS} ${SERVER_USER}
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# This is the same as 'systemctl enable reverse_ssh', just that we don't need
# to run systemctl (we aren't running chroot)
ln -s ${MOUNT_DIR}/etc/systemd/system/probe_init.service ${MOUNT_DIR}/etc/systemd/system/multi-user.target.wants/probe_init.service

echo "[+] Transferring script for installing wifi driver"
cp "install-wifi" "${MOUNT_DIR}/usr/bin/install-wifi"


echo "[+] Blacklist the internal wifi driver"
cat << EOF >> /etc/modprobe.d/wlan_blacklist.conf
blacklist brcmfmac
blacklist brcmutil
EOF


echo '[+] Adding connection status script'
cat << 'EOF' > ${MOUNT_DIR}/root/connection_status.sh
#!/bin/bash

eth=$([[ $(ifconfig eth0 | awk '/inet /{print $2}') == "" ]] && echo 0 || echo 1)
wlan=$([[ $(ifconfig wlan0 | awk '/inet /{print $2}') == "" ]] && echo 0 || echo 1)

printf '{"eth0":%d,"wlan0":%d}\n' $eth $wlan
EOF


echo "[+] Unmounting image"
umount "${MOUNT_DIR}"


echo "Done!"
