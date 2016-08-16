#!/bin/bash

# This script returns all the authorized keys for the specified
# user (which should be called dummy)

# The script reads raw keys from the sqlite database, and adds
# some extra configs to restrict what the probes can do on the host
# (ideally they should be able to do nothing but open the ssh tunnel)

# NB: This script must be owned and only writeable by root, or else
# sshd will refuse to use it

USAGE="${0} <user to authenticate>"
if [[ $# != 1 ]]; then
    echo "${USAGE}"
    exit
fi

USER="${1}"
DATABASE=$(cat /etc/wifi_probing/db_path.txt)

# This needs to be altered if the dummy user has a different username
if [[ "${USER}" == "dummy" ]]; then
    keys=$(sqlite3 "${DATABASE}" 'SELECT pub_key FROM probes')
    restrictions='command="/bin/false",no-agent-forwarding,no-pty,no-X11-forwarding'
    echo "${keys}" | sed "s|ssh-rsa|${restrictions} ssh-rsa|g"
fi
