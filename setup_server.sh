#!/bin/bash

# This script will set up the current computer as a WiFi probe server
# (i.e. both a web server and and Ansible server). It is assumed to be
# running a Debian based distro.

# USAGE="Usage: ${0}"

# if [[ ${#} != 1 ]]; then
#     echo "${USAGE}"
#     exit
# fi

if [[ "${EUID}" != 0 ]]; then
    echo "[!] Script must be run as root"
    exit
fi


echo '[+] Installing required programs'
# NB: Must have ansible 2.x
apt-get update
apt-get install --yes python3 python3-pip ansible netcat

# These programs are required for the python cryptography module to compile
# (when installed with pip)
apt-get install --yes build-essential libssl-dev libffi-dev python-dev

pip3 install -r requirements.txt


if [[ ! $(grep 'dummy' /etc/passwd) ]]; then
    echo '[+] Making dummy user for SSH tunneling'
    useradd -m dummy
fi


if [[ ! -f /home/dummy/.ssh/id_rsa ]]; then
    echo '[+] Generating SSH keys for dummy user'
    ssh-keygen -t rsa -b 4096 -f dummy_key -N ""
    mkdir /home/dummy/.ssh/

    sed -i 's/\w\+@/dummy@/g' dummy_key
    mv dummy_key /home/dummy/.ssh/id_rsa
    chown dummy /home/dummy/.ssh/id_rsa

    sed -i 's/\w\+@/dummy@/g' dummy_key.pub
    mv dummy_key.pub /home/dummy/.ssh/id_rsa.pub
    chown dummy /home/dummy/.ssh/id_rsa.pub
fi


echo '[+] Make sure root owns get_probe_keys.py & the web root dir'
chown root get_probe_keys.py
chown root .


CURR_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [[ ! $(grep 'Match User dummy' /etc/ssh/sshd_config) ]]; then
    echo '[+] Adding sshd_config entry for dummy user'
cat << EOF >> /etc/ssh/sshd_config
Match User dummy
    ForceCommand /bin/false
    AuthorizedKeysCommand ${CURR_DIR}/get_probe_keys.py
    AuthorizedKeysCommandUser nobody
EOF
fi


echo '[+] Add paths to config files'
sed -i "s|ADD_PROJECT_PATH_HERE|${CURR_DIR}|g" "${CURR_DIR}/probe_website/settings.py"
sed -i "s|ADD_CERT_DIR_HERE|${CURR_DIR}/ansible-probes/certs|g" "${CURR_DIR}/ansible-probes/group_vars/all/locations"
