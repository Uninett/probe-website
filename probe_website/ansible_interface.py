from probe_website import settings, util
import yaml
import os.path
from os import makedirs
from subprocess import Popen
import shutil

# What needs to be done:
#
# a) Convert probe specific config to yaml
# b) Save this config in the host_groups directory
# c) Run ansible-playbook with all the (user's) probes

def load_default_config(username, config_name):
    filename = '{}/group_vars/{}/{}'.format(settings.ANSIBLE_PATH, username, config_name)
    # Change to global default if there is no group default
    if not os.path.isfile(filename):
        filename = '{}/group_vars/{}/{}'.format(settings.ANSIBLE_PATH, 'all', config_name)
        if not os.path.isfile(filename):
            # There is no default config with that name
            return ''

    with open(filename, 'r') as f:
        # Should probably check for malformed config file here
        return yaml.safe_load(f)


# Data is a normal python data structure consisting of lists & dicts
def export_group_config(username, data, filename):
    dir_path = '{}/group_vars/{}/'.format(settings.ANSIBLE_PATH, username)
    _write_config(dir_path, data, filename)


def export_host_config(probe_id, data, filename):
    probe_id = util.convert_mac(probe_id, mode='storage')
    dir_path = '{}/host_vars/{}/'.format(settings.ANSIBLE_PATH, probe_id)
    _write_config(dir_path, data, filename)


def remove_host_config(probe_id):
    probe_id = util.convert_mac(probe_id, mode='storage')
    dir_path = '{}/host_vars/{}/'.format(settings.ANSIBLE_PATH, probe_id)
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)


def _write_config(dir_path, data, filename):
    if not os.path.exists(dir_path):
        makedirs(dir_path)

    with open(dir_path + filename, 'w') as f:
        f.write('---\n')
        f.write(yaml.dump(data))


def update_hosts_file():
    pass


def run_ansible_playbook(username):
    command = ['ansible-playbook', '-i', settings.ANSIBLE_PATH + 'hosts',
               settings.ANSIBLE_PATH + 'probe.yml', '--vault-password-file',
               settings.ANSBILE_PATH + 'vault_pass.txt']
