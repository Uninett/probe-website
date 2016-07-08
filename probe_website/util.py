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
