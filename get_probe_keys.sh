#!/bin/bash

USAGE="$0 <user to authenticate>"
if [[ $# != 1 ]]; then
    echo "$USAGE"
    exit
fi

USER="$1"
DATABASE=$(cat /etc/wifi_probing/db_path.txt)

# This needs to be altered if the dummy user has a different username
if [[ "$USER" == "dummy" ]]; then
    sqlite3 "$DATABASE" 'SELECT pub_key FROM probes'
fi
