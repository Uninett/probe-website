from re import fullmatch
from probe_website import settings
from subprocess import call, check_output, CalledProcessError
from datetime import timedelta
import json


def is_mac_valid(mac):
    """Return true if 'mac' is a non-empty string matching the MAC
    address format."""
    if type(mac) is not str or mac == '':
        return False

    return fullmatch('(([0-9a-fA-F]:?){2}){5}[0-9a-fA-F]{2}', mac) is not None


def is_pub_ssh_key_valid(key):
    """Return true if if 'key' has the correct public SSH key format

    (NB: It does not check if key/base64 part itself is valid, only
    that it has the correct prefix)
    """
    try:
        mode, key, comment = key.split()
    except:
        return False

    return (mode == 'ssh-rsa' and
            'AAAAB3NzaC1yc2EA' in key and
            len(comment.split('@')) == 2)


def is_ssh_host_key_valid(key):
    """Return true if 'key' is a valid SSH host key."""
    try:
        hostname, mode, key = key.split()
    except:
        return False

    # hostname should be localhost, because we are using reverse SSH
    # against localhost here
    return (hostname == 'localhost' and
            mode == 'ssh-rsa' and
            'AAAAB3NzaC1yc2EA' in key)


def convert_mac(mac, mode):
    """Converts 'mac' between two modes: 'display' or 'storage'

    Display mode looks like this: 12:34:56:AB:CD:EF
    Storage mode looks like this: 123456abcdef
    """
    mac = mac.lower().replace(':', '')

    # format: 123456abcdef
    if mode == 'storage':
        return mac
    # format: 12:34:56:AB:CD:EF
    elif mode == 'display':
        return ':'.join([mac[i:i+2] for i in range(0, len(mac), 2)]).upper()


def parse_configs(configs, config_type):
    """Parse data from HTTP POST forms into python datastructures.

    'configs' is in the format ImmutableMultiDict([('script.6.enabled', 'on'),
    ('script.7.interval', '10'), ... ]) etc.
    where each element is (<type>.<id>.<attribute>, <value>). The list may also
    include configs not in this format, so ignore those.

    This function converts 'configs' to this format:
    {id1: {'name': 'name', ..}, id2: { ... }, ... }
    i.e. groups values for each id together

    'configs' contains all the config data, while 'config_type' is the
    content we want to extract
    """

    parsed = {}
    for tup in configs:
        try:
            val_type, val_id, attribute = tup[0].split('.')
            val_id = int(val_id)
        except ValueError:
            # Probably an entry in another format, so ignore it
            continue

        if val_type != config_type:
            continue

        value = tup[1]

        parsed.setdefault(val_id, {})
        parsed[val_id].setdefault(attribute, value)

    return parsed


def allowed_cert_filename(filename):
    """Return true if filename looks like a filename and has a valid
    file extension"""
    return '.' in filename and filename.rsplit('.', 1)[1] in \
        settings.ALLOWED_CERT_EXTENSIONS


def is_probe_connected(port):
    """Return true if there is a probe connected at 'port', i.e.
    [localhost]:<port>.

    Uses nc (netcat) to check whether a probe is connected to
    the specified port
    """
    try:
        port = str(port)
        if not fullmatch('[0-9]{1,5}', port):
            raise Exception
    except:
        print('Invalid port number')
        return -1

    # From netcat manpage:
    # -z      Specifies that nc should just scan for listening daemons,
    #         without sending any data to them.
    command = ['nc', '-z', 'localhost', port]
    try:
        ret_code = call(command)
    except:
        return False

    return True if ret_code == 0 else False


def get_interface_connection_status(port):
    """Return a json string specifying whether the probe is connected
    to the interntet via eth0 or wlan0 (or both).

    Format of returned string: {"eth0": 0 or 1, "wlan0": 1 or 0}
    """
    command = ['ssh',
               '-p', str(port),
               '-o', 'UserKnownHostsFile={}/known_hosts'.format(settings.ANSIBLE_PATH),
               'root@localhost',
               '[ -f /root/connection_status.sh ] && /root/connection_status.sh']
    try:
        data = check_output(command, timeout=10).decode('utf-8')
    except CalledProcessError:
        return None

    # Make sure the returned status is correct
    status = json.loads(data)
    if 'wlan0' in status and 'eth0' in status:
        return data

    return None


def strip_id(data):
    """Remove all 'id' dictionary keys in 'data'.

    Merging of config files will not work properly if the id key/value pair is
    included, because it makes every entry unique.
    """
    for entry in data:
        if 'id' in entry:
            del entry['id']
    return data


def get_textual_timedelta(time):
    """Generates a textual representation of time passed for a timedelta object.

    E.g. will a timedelta with 120 seconds be converted to "2 mins ago"
    """
    if type(time) is not timedelta:
        return None

    seconds = (time.seconds, 'second')
    minutes = (seconds[0] / 60, 'minute')
    hours = (minutes[0] / 60, 'hour')
    days = (time.days, 'day')
    weeks = (days[0] / 7, 'week')
    months = (days[0] / 30, 'month')  # Estimate

    for t in [months, weeks, days, hours, minutes]:
        if t[0] >= 1:
            return '{} {}{} ago'.format(int(t[0]), t[1], 's' if int(t[0]) >= 2 else '')

    return 'just now'
