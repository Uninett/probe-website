#!/usr/bin/env python3
from sys import argv
from probe_website import settings
from sqlalchemy import create_engine

# This script returns all the authorized keys for the specified
# user (which should be called dummy)

# The first and only argument is the username of the user
# to get authorized keys for. sshd will automatically send
# this as an argument

# The script reads raw keys from the database specified in settings.py,
# and adds some extra configs to restrict what the probes can do on the host
# (they should be able to do nothing but open the ssh tunnel)

# NB: This script must be owned and only writeable by root, or else
# sshd will refuse to use it


def check_args():
    """Make sure the user to get keys for is sent as an argument.

    For the moment only allow a user called 'dummy', because those keys
    should not be authorized for any other user.
    """
    if len(argv) != 2 or argv[1] != 'dummy':
        USAGE = '{} <user to authenticate>'.format(argv[0])
        print(USAGE)
        exit(1)


def get_keys():
    """Query the database through SQLAlchemy and return the authorized keys.

    Each key will have additional restrictions, which essentially makes
    the authorized users (i.e. probes) only able to start degenrate ssh tunnels.
    """
    engine = create_engine(settings.DATABASE_URL, convert_unicode=True)
    connection = engine.connect()
    results = connection.execute('SELECT pub_key FROM probes')

    restrictions = 'command="/bin/false",no-agent-forwarding,no-pty,no-X11-forwarding'
    return [restrictions + ' ' + row[0] for row in results if row[0] != '']


if __name__ == '__main__':
    check_args()
    for key in get_keys():
        print(key)
