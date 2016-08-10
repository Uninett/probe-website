from re import fullmatch
from probe_website import settings
from subprocess import call


def is_mac_valid(mac):
    if type(mac) is not str or mac == '':
        return False

    return fullmatch('(([0-9a-fA-F]:?){2}){5}[0-9a-fA-F]{2}', mac) is not None


def is_pub_ssh_key_valid(key):
    try:
        mode, key, comment = key.split()
    except:
        return False

    return (mode == 'ssh-rsa' and
            'AAAAB3NzaC1yc2EA' in key and
            len(comment.split('@')) == 2)

def is_ssh_host_key_valid(key):
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
    mac = mac.lower().replace(':', '')

    # format: 123456abcdef
    if mode == 'storage':
        return mac
    # format: 12:34:56:AB:CD:EF
    elif mode == 'display':
        return ':'.join([mac[i:i+2] for i in range(0, len(mac), 2)]).upper()


# The raw config is in the format ImmutableMultiDict([('script.6.enabled', 'on'),
# ('script.7.interval', '10'), ... ]) etc.
# where each element is (<type>.<id>.attribute, value). The list will also
# include configs not in this format, so ignore those.
# This function converts it to this format: {id1: {'name': 'name', ..}, id2: { ... }, ... } i.e.
# groups values for each id together
# configs contains all the config data, while config_type is the
# content we want to extract
def parse_configs(configs, config_type):
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
    return '.' in filename and filename.rsplit('.', 1)[1] in \
            settings.ALLOWED_CERT_EXTENSIONS


# Uses nc (netcat) to check whether a probe is connected to
# the specified port
def is_probe_connected(port):
    try:
        port = str(port)
        if not fullmatch('[0-9]{1,5}', port):
            raise Exception
    except:
        print('Invalid port number')
        return -1

    command = ['nc', '-z', 'localhost', port]
    ret_code = call(command)

    return True if ret_code == 0 else False
