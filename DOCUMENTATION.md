---
title: WiFi probe system documentation
author: Written by Fredrik Strupe
date: Last updated 2016-08-19
---

# About this document

This document is meant as a technical documentation on how the WiFi probing
system works as a whole. It is meant to give an overview of the system, and not
necessarily explain the minute details of each operation. For that you can
check out the code, as it also contains some documentation. Also check out the
latest presentation uploaded together with this document, as it contains a good
bit of documentation too, especially in the form of flowcharts and pictures.

The project mainly consists of the following parts:

- Linux image generation
- Various scripts for probe initialization
- Website for adding and administering probes
- Ansible setup for pushing configs inserted in website
- Scripts for probing the WiFi, and a program for controlling the scripts and
  submitting measured data

Each of these parts are explained below. Except when otherwise noted, all file
references will be relative to the root directory of the probe website 
project / git repository.

# Image generation
A custom Linux ARM image is generated from a generic Kali Linux ARM image. To
generate the image, you use the script `image_generation/generate_image.sh`.
`generate_image.sh` takes five arguments:

1. The generic Kali Linux ARM image. You must use either the Raspberry Pi 1
or 2/3 version. Links to these images are in
`image_generation/image_url.txt`.
2. Driver for the WiFi dongle. This needs to be compiled for the correct
kernel beforehand. Ansible can later update the driver, but the probe needs a
preloaded driver so it can read the dongle's MAC address. See [Driver
compilation][] for how to do that.
3. The hostname/address of the web server the probe will connect to. This can
either be a DNS record or an IP address, but make sure to include the port
number if the web server listens on a port other than 80 (format:
`127.0.0.1:12345`).
4. The name of the unprivileged user the probe will start a connection to. If
you used/are going to use the server setup script ([Website Setup][]), this
user will be named `dummy`.
5. The public ssh key of the user that will connect to the probes via
Ansible -> SSH. This will most likely be the same user that runs the web
server.

The script will copy the supplied image to a file with prefix `modified_`. The
modified image differs from the original in that it contains the following
components:

- Probe init script & systemd unit file
- Server user's pub ssh key & server's host key
- Server's hostname/address 
- WiFi driver (for MAC retrieval)
- WiFi dongle shutdown script (see [The WiFi dongle shutdown script][])
- Connection status script (used to show probe's connection status on the website)

After the image has been generated, it can be burned to an SD card by doing
something like:
```
dd if=modified_<original-image-name> of=/dev/sdf bs=1M conv=sync
```
Given `/dev/sdf` is the name of the SD card. This can be found by runing
`lsblk`.

## Driver compilation
The currently used WiFi dongle, "D-Link DWA-171", needs the rtl8812au driver to
work on linux. The driver needs to be compiled for each kernel version. Because
you need to compile the whole Linux kernel before compiling the driver, the
compilation will be very slow on the Raspberry Pi (RPi). Therefore it is best
to cross compile. To do this you can use the script located at 
`ansible-probes/roles/driver/files/compile_driver.sh`.

This script will download the required cross compilation toolchain, collect the
required files from a running RPi and compile the WiFi driver for it. It needs
the following arguments:

1. The address of the RPi running the kernel version you want to compile the
 driver for. This will be the same address as the one you use to SSH into it,
so either a DNS record or IP address.
2. The kernel version the RPi is running. This can be retrieved by running
 `uname -r` on the RPi itself. The output it gives should be the argument.
3. The location where you want the script to save the compiled driver.

Do note that the compilation can take some time. On my (average) laptop it
takes about 1 hour.

Also, there should already be a compiled driver for the 4.1.9 (4.1.9-v7 for
rpi2/3) kernel version in the image_generation directory. So if that is the 
kernel version being used, you can just use that instead of compiling a new one.

## The WiFi dongle shutdown script
Because the Raspberry Pi has no off-switch, there's no easy way to shut it down
when not connected to a monitor, and when a tty is not available. It is still
important to shut it down properly though, to firstly avoid file corruption,
but also to make sure the SSH tunnel to the server is closed properly.

To achieve this, the WiFi dongle itself is used as an off-switch. With the help
of a udev script, the RPi will shut down when a USB device with a specific
combination of IDs is *physically ejected*. Those IDs are set to the model ID
and vendor ID of the D-Link DWA-171 WiFi dongle. For information on how to
retrieve these IDs, and what the script looks like, consult the
generate_image.sh script file.

So in essence: to shut the probe down, physically eject the WiFi dongle and
wait until the green light shines constantly (ususally takes 10-15 seconds).

# Probe initialization
When a probe boots up for the first time, it will run the initialization (bash)
script preloaded into the Linux image. This script can be found in
image_generation/probe_init.sh. It essentially does the following things:

- Activate WiFi driver
- Install curl & dnsutils (for dig)
- Generate SSH key pair
- Gather wlan0 MAC address
- Register pub SSH key with server (identify with MAC) (see [Association][])
- If registration is successful, receive a port number (see [SSH port query][])
- Generate an autossh command (rev. SSH) with the received port, and 
  wrap it in a systemd unit file
- Generate a systemd unit file that runs the create_ssh_tunnel.sh script
    - In addition to connecting to the server via ssh, this script also modifies
      the network routing table to make sure only the connection to the server
      goes over eth0 (if available), while everything else goes over wlan0
      (measurements etc.)
- Initiate SSH tunnel to dummy user on server by starting systemd unit file and idle 
  (the tunnel will be degenerate -> /bin/false as shell) (see [The SSH tunnel procedure][])

If association with the server is not successful (e.g. if the probe has not
been registered yet), the probe will just keep on trying.

At this stage the probe *must* be connected to the internet via ethernet,
because it currently has no WiFi credentials to use.

# Website
The website is the front-end a regular user will use to add and administer his
probes and information like database credentials (for the database(s) the probe
will send measurement results to). The website's uses are roughly:

For administrators:

- Add new users
- Edit/remove existing users

For regular users:

- Download probe image
- Add new probes, more specifically:
    - Name, wlan0 MAC address, location
    - Network configuration (SSID, anonymous ID, username, password, wpa
      certificate)
    - Script/test configurations (For each script: the interval they should be
    run at (in minutes), and whether they are enabled or not, i.e. whether they
    should be run at all)
- Edit/remove probes
- Add database information
    - Only necessary if the user does not want to use UNINETT's provided elastic
      search instance
- Follow link to see data in Kibana

For probes (see [Probe association API][]):

- Register their public SSH key and host key
- Receive a port for SSH tunnel

The website's back-end is written in Python 3 and uses the Flask web framework. The
front-end uses templated HTML files (Jinja2) and the Bootstrap CSS framework.
All data submitted to the website will be saved in an SQLite3 database.

## Website Setup
The server requires some configuration before it can be used as a server for
the probes. To do this setup, you can run the script `setup_server.sh`. Note
that this script has only been tested in a Ubuntu environment, and only makes
the server ready to run a development sever, i.e. the one built into Flask. So
for apache/nginx, further configuration will be needed.

The script needs no arguments, but must be run as root (pretty much everything
is does requires root priveliges). The script does the following tasks:

- Install required programs (NB: At least Ansible 2.x is needed. If only Ansible
  1.x is in the repo, Ansible 2.x will need to be manually installed).
- Make a system user called Dummy
- Generate SSH keys for Dummy and move them to his home directory
- Copy get_probe_keys.sh to /usr/bin that will read the web sites SQL database to
  determine known hosts.
- Change sshd_config to make all SSH connections to Dummy only unable to start
  a shell (i.e. forces /bin/false to be run instead)
- Make a config file with the location of the website's SQL database
- Make a config file with the location of Ansible certificate dir

### Default user
When the database is first made, an admin user is automatically added. This
user must then add other users. At the moment it's not possible to make admin
users via the web interface, but it can be done by manually editing the SQL
database and setting a user's 'admin' attribute to 1.

The default admin username/password combination is `admin`/`admin`. The
password can be changed after logging in.

## Probe association API
New probes must associate with the web server before it will push Ansible
configs to them. This is done in a two step process. The main reason for this
process is that probes will most likely be behind NAT, and must therefore
send the server keys - and the server must send the probe an available port
for SSH - before it can start a reverse SSH tunnel (see [The SSH tunnel
procedure][]). Ansible will not be able to push its configuration without this
tunnel.

### Association
In the first step, the probe sends a POST request to the server (the Probe's
init script does this, see [Probe initialization][]), with it's newly
generated SSH public key and its host key. It uses its wlan0 MAC address to
identify itself. If a probe with the attached MAC address exists in the
database (i.e. has been added through the web interface) and has not already
been registered, the server will save the keys and associate them with that MAC
address from now on.

NB: All references to MAC addresses in this document refer to the WiFi dongle's
MAC address, which will be seen as the MAC address of the wlan0 interface in
Linux. Also note that the internal WiFi card present on the RPi 3 is disabled to
avoid conflicts.

The probe sends a POST request with the following key/value pairs:

- pub_key=[pub_key]
- host_key=[host_key]

The server will return one of the following responses:

| Return value                | Explanation 
| :-------------------------- | :-------------------------------------------------
| invalid-mac                 | The supplied MAC was invalid (in form)
| unknown-mac                 | The MAC was valid, but is not in the database
| invalid-pub-key             | The pub key was invalid (in form)
| invalid-host-key            | The host key was invalid (in form)
| already-registered          | There already exists keys associated with this MAC
| assocation-period-expired   | The assocation period has expired and needs
|                             | to be renewed through the web site
| success                     | The keys were successfully registered/associated
|                             | with the corresponding MAC address

When a probe is added through the web interface, it gets an initial 40 minutes
of association time. If no probe associates with the corresponding MAC address
within that time, then the association time will expire, and the server will not
accept any keys sent afterwards. This is to prevent a potentially malicious
person from registering his own probe before the real user has gotten time to do it,
e.g. if the user waits a long time before connecting the RPi to the internet
after having registered it.

### SSH port query
The second step will be performed after the probe has been associated, and
consists of a GET request with the probe's MAC address attached in a mac=vale
attribute pair. If an associated probe with that MAC exists in the database,
the server will return a port number from 50000 to 65000 (inclusive). This
port number will be used by the probe to initiate an SSH tunnel.

The probe sends a GET request with the following key/value pair:

- mac=[mac]

The server will return one of the following responses:

| Return value                | Explanation 
| :-------------------------- | :-------------------------------------------- 
| invalid-mac                 | The supplied MAC was invalid (in form)
| unknown-mac                 | The MAC was valid, but is not in the database 
| no-registered-key           | No SSH key has been associated with this MAC,
|                             | and therefore no port will be sent            
| [port]                      | Returns the queried port (a valid MAC was     
|                             | received)                                     

Wher the probe receives the network port, it will construct an SSH command with
it. This command ill be wrapped in a systemd unit file that automatically restarts 
if the script fails, to prevent the SSH tunnel from breaking (as far as possible).

### The SSH tunnel procedure
This section explains the complete procedure the server and probe goes
through to be able to successfuly initiate an SSH connection. It is assumed
that the main server user (the user that will run Ansible) is called MAIN, the
dummy user on the server is called DUMMY, and the main user on the probe is
called PROBE (in reality it will be root for Kali Linux).

1. MAIN's public SSH key is preloaded on a Kali Linux ARM image as an
*authorized key*, and the server's host key is added as a *known host*
2. PROBE generates a key pair on first boot
3. PROBE sends its public SSH key and hosts key to MAIN, together with its
wlan0 MAC address for identification.
4. The received host key is saved as a *known host*, and the received public
key is saved as an *authorized key* for DUMMY

In the end: both machines will be known to each other. PROBE will be
authorized to start a degenerate SSH tunnel to DUMMY (no tty allowed), 
while MAIN will be authorized to use the SSH tunnel to login to PROBE.

## Probe status
After adding a probe through the web interface, three statuses will appear (see
image in presentation mentioned in introduction, or just log in to the website).

The first status is for association. It will be green if the probe has been
associated, i.e. has sent it's SSH key and host key. It will be yellow if it
has not been associated and the server is waiting for association. It will be
red if the association time has expired.

The second status show whether the probe is connected to the server, i.e. there
exists an SSH tunnel at the port designated to the probe. It will also show
whether eth0 or wlan0 is up. If only eth0 is up, something is wrong as the probe
will not be able to make measurements. If only wlan0 is up, that's okay, as the
probe doesn't have to connect to the server through eth0 (it can use wlan0 too).

The third status tells whether a probe has been updates or not, and if it is
currently updating. It will show "Not updated" if the probe has never been
updates. It will show "Updating..." if an update is currently in progress.
Otherwise it will show the time since the probe was last updated. If an update
fails, it will say "Failed". This will in most cases make the probe stop doing
measurements.

## Complete registration procedure
See the Instructions tab on the website for instructions on the how register
probes.

## View collected data
If the default database is used (UNINETT's ElasticSearch instance), users can
view the collected data in Kibana by clicking on the MAC address in the Probes
tab on the website. This will redirect them to Kibana.

# Ansible
Ansible is what actually converts the RPis to WiFi probes (i.e. installs the
required programs, transfers scripts etc.). When an SSH tunnel
has been established, and the user presses the "Push configuration to probes" button on
the website, the data saved in the SQL database will first be converted to
Ansible-friendly YAML config files, and then Ansible is run.

All file and directory references will be relative to the Ansible project
directory (i.e. the ansible-probes directory in the root directory of the
website project).

## Data exporting
When the button is pressed, the web server first checks which probes are
connected. From that it will generate an Ansible inventory file (a file containing
information about each probe to be updated) in inventory/, and a known_hosts file
for use with SSH. After that it will export some configs for the probes that are
connected and are going to be updated.

Ansible will first look in group_vars/all for config files, before checking
group_vars/[username] and at last host_vars/[probe MAC]. For example will the
default script configs be in group_vars/all, database information will be in
group_vars/username (because db info is local to each user), and probe
specific network configs may be in host_vars/mac (but also in group_vars if the
user has saved the settings as default values).

The data in the SQL database is converted to the following files (and can as
mentioned above be both group and host specific):

| Config filename  | Explanation
| :--------------  | :------------
| database_configs | information about the databases the probe will
|                  | send data to
| network_configs  | information used by wpa_supplicant to connect to WiFi
| script_configs   | information about which script should be run, how often, and
|                  | some other attributes. This file will be merged and
|                  | converted to a JSON file on the probe

WPA certificates are also saved in the certs/ directory, which is divided up into
group_certs and host_certs. Certs saved as default will be saved in the
certs/group_certs/ directory, while host specific certs are saved in the certs/host_certs/
directory.

## Starting Ansible
After the Ansible inventory, known_hosts and configuration files have been
exported, the web server will start Ansible in a subprocess, and tell it to
pipe all its ouput to a logfile in logs/, with the filename equal to the
username of the logged in user. The server will parse this file each time the
probes webpage loads, and will display the current status.

## Ansible tasks
The Ansible setup is split into two roles (kind of like two parts);
*driver* and *common*. The driver role makes sure the driver is loaded, and
will either load it, install it or compile it, depending on the current state.
The common role is what does everything else. More specifically, it mainly does
the following:

- Install required programs
- Transfer probing scripts & script control program
- Fill in templated configs (WPA etc.) using the previously mentioned Ansible configs
- Transfer WPA certificates
- Transfer systemd unit files for control program and ramdisk creation & enable
  them

# Probing/measuring scripts
When the probe has gone through the initialization steps and Ansible has pushed an
update to it, it will be ready to do WiFi measurements/probing.

## Booting the probe
After being shutdown as described in [The WiFi dongle shutdown script][], the
probe will automatically begin measuring. The WiFi dongle must logically
be connected, but an ethernet cable can also be connected if desired. This
can be useful as a safe-guard if e.g. an erroneous config is pushed, which
locks the probe out from the WiFi.

When booting, the probe will first make a ramdisk and copy the WiFi scripts to
it. After that has been done, the control program will start. This is to
mitigate tear on the SD card.

## The control program
The control program is a Python 3 program whose main purpose is to call the
WiFi scripts and specified intervals, and send their results to the specified
database(s). It will read the script_configs file exported by Ansible (see
[Data exporting][]), and from that make an instance of a Script class for each
entry in the configuration. It mainly contains information about the script
name, the interval it should be run at, and whether it should be run at all (is
enabled or not).


The program first does some initialization (e.g. makes sure the probe is
connected to the internet), before running this endless loop:

- Run all ready scripts (scripts whose inner timer has an elapsed time higher
  or equal to the interval specified in the config). NB: The scripts are run
serially (i.e. not in parallel).
- Read the results_report file. If it is not empty:
    - Parse its content to a database friendly format
      (for the moment ElasticSearch is used) and send it to the database.
    - Clear the results_report file
- Wait for 2 seconds and repeat.

## Logging
Information like errors, what scripts have been called, and whether the sent data
was successfully received, is logged to the file control_program.log. At the
moment it is just saved locally, and not sent to any external server.

A typical log output may look like this:

```
2016-08-19 08:14:39,055 INFO | Initializing script and io manager
2016-08-19 08:14:39,059 INFO | Connecting wlan0 to the internet
2016-08-19 08:14:39,060 INFO | Calling: ['/root/scripts/probefiles/connect_8812.sh', 'any']
2016-08-19 08:15:13,069 INFO | Sending results to influxdb
2016-08-19 08:15:13,129 INFO | Results successfully received by influxdb.
```

## The WiFi scripts
The WiFi testing scripts reside in
ansible-probes/roles/common/files/wifi_scripts/. All scripts write results to a
file called results_report, in the format 'key value', e.g. 'dhcp_time_any
2.35'. The file is emptied each time the results are sent.

The following scripts are available. As default, all of them are enabled:

| Filename          | Description
| :---------------- | :-----------------
| connect_8812.sh   | AP & dhcp connection time
| scan.sh           | Scan for number of cells
| collect.sh        | Measure link quality & bitrate
| check_ipv6.sh     | Check if IPv6 is available
| check_http_v4.sh  | Measure HTTP and DNS request time for IPv4
| check_http_v6.sh  | Measure HTTP and DNS request time for IPv6
| rtt4.sh           | Measure round trip time for IPv4
| rtt6.sh           | Measure round trip time for IPv6
| run_owping4.sh    | Measure one-way connection time for IPv4
| run_owping6.sh    | Measure one-way connection time for IPv6
| run_bwctl4.sh     | Measure throughput for IPv4
| run_bwctl6.sh     | Measure throughput for IPv6
