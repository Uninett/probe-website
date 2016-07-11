from re import fullmatch


def is_mac_valid(mac):
    if type(mac) is not str or mac == '':
        return False

    return fullmatch('(([0-9a-fA-F]:?){2}){5}[0-9a-fA-F]{2}', mac) is not None


def convert_mac(mac, mode):
    mac = mac.lower().replace(':', '')

    # format: 123456abcdef
    if mode == 'storage':
        return mac
    # format: 12:34:56:AB:CD:EF
    elif mode == 'display':
        return ':'.join([mac[i:i+2] for i in range(0, len(mac), 2)]).upper()


# The raw config is in the format ImmutableMultiDict([('6.enabled', 'on'), ('7.interval', '10'), ... ])
# where each element is (<script_id>.attribute, value). The list will also
# include configs not for scripts, so ignore those.
# This function converts it to this format: {id1: {'name': 'name', ..}, id2: { ... }, ... } i.e.
# groups values for each script together
def parse_script_configs(configs):
    parsed = {}
    for tup in configs:
        try:
            script_id, attribute = tup[0].split('.')
            script_id = int(script_id)
        except ValueError:
            # Probably not a script attribute, so ignore it
            continue

        value = tup[1]

        parsed.setdefault(script_id, {})
        parsed[script_id].setdefault(attribute, value)

    return parsed
