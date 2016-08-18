#!/bin/bash

# NB: THIS SCRIPT IS COMPLETELY UNTESTED.
#     Stuff may/will break if it is run directly

# This script will set up the current computer as a WiFi probe server
# (i.e. both a web server and and Ansible server). It is assumed to be
# running a Debian based distro.

USAGE="Usage: ${0}
<full path to preferred sql db location (without the filename itself)>"

if [[ ${#} != 1 ]]; then
    echo "${USAGE}"
    exit
fi

if [[ "${EUID}" != 0 ]]; then
    echo "[!] Script must be run as root"
    exit
fi

DB_PATH="${1}"

echo '[+] Installing required programs'
# NB: Must have ansible 2.x (I think...)
apt-get install python3 python3-pip ansible netcat
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


echo '[+] Make sure root owns get_probe_keys.sh & copy it to proper location'
chown root get_probe_keys.sh
chmod +x get_probe_keys.sh
cp get_probe_keys.sh /usr/bin/


if [[ ! $(grep 'Match User dummy' /etc/ssh/sshd_config) ]]; then
    echo '[+] Adding sshd_config entry for dummy user'
cat << EOF >> /etc/ssh/sshd_config
Match User dummy
    ForceCommand /bin/false
    AuthorizedKeysCommand /usr/bin/get_probe_keys.sh
    AuthorizedKeysCommandUser nobody
EOF
fi


# The get_probe_keys.sh script needs to know where the db is located, so
# it can query it.
echo '[+] Make file with location of sql db location'
mkdir /etc/wifi_probing
echo "${DB_PATH}/database.db" > /etc/wifi_probing/db_path.txt
