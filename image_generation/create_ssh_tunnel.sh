#!/bin/bash

# dig requires dnsutils to be installed

USAGE="$0 <server_user> <server_hostname> <ssh_port>"

if [[ $# != 3 ]]; then
    echo "$USAGE"
    exit 1
fi

server_user="$1"
server_host="$2"
ssh_port=$3

# Find IP of default gateway for eth0, and IP for host to connect to
default_eth_gateway=$(ip route | awk '/default.*eth0/{ print $3 }')
server_addr=$(dig +short A $server_host @158.38.0.1 | grep -oE '^([0-9]{1,3}.){3}[0-9]{1,3}$')
if [[ "$server_addr" != "" ]]; then
    echo -n "$server_addr" > /root/init/server_addr
elif [[ -f /root/init/server_addr ]]; then
    server_addr=$(</root/init/server_addr)
else
    echo "Unable to fetch server address"
    exit 1
fi

# Create a hook that prevents dhclient from overwriting resolv.conf,
# if it is running for eth0 (wlan0 can overwrite)
dhclient_hook="/etc/dhcp/dhclient-enter-hooks.d/nodnsupdate"
if [ ! -f $dhclient_hook ]; then
cat << 'EOF' > $dhclient_hook
#!/bin/bash
if [ "$interface" = "eth0" ]; then
make_resolv_conf(){
	:
}
fi
EOF
chmod +x $dhclient_hook
fi

# Change the ip routing tables such that the only possible outgoing connection done
# via eth0 is to the server
if [[ "$default_eth_gateway" != "" && "$server_addr" != "" ]]; then
    ip route add $server_addr via $default_eth_gateway dev eth0
    route del default gw $default_eth_gateway
fi

# If the user has selected the uninett elasticsearch server, do port
# forwarding to it
tunnel=""
if [[ $(find . -name db_configs.json -exec jq -r .elastic.status "{}" \; -quit) == "uninett" ]]; then
    tunnel="-L 9200:wifiprobeelk.labs.uninett.no:9200"
fi

# Start the ssh connection
ssh -N -T -o "ExitOnForwardFailure yes" -o "StrictHostKeyChecking no" ${tunnel} -R${ssh_port}:localhost:22 ${server_user}@${server_addr}                                                                
