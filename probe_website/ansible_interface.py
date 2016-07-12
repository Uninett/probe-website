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

def load_default_script_configs(username):
    filename = '{}/group_vars/{}/script_configs'.format(settings.ANSIBLE_PATH, username)
    # Change to global default if there is no group default
    if not os.path.isfile(filename):
        filename = '{}/group_vars/{}/script_configs'.format(settings.ANSIBLE_PATH, 'all')

    with open(filename, 'r') as f:
        # Should probably check for malformed config file here
        return yaml.safe_load(f)['default_script_configs']


# Data is a normal python data structure consisting of lists & dicts
def export_script_config_as_default(username, script_data):
    dir_path = '{}/group_vars/{}/'.format(settings.ANSIBLE_PATH, username)
    _write_script_config(dir_path, script_data, 'default_script_configs')


def export_script_config(probe_id, script_data):
    probe_id = util.convert_mac(probe_id, mode='storage')
    dir_path = '{}/host_vars/{}/'.format(settings.ANSIBLE_PATH, probe_id)
    _write_script_config(dir_path, script_data, 'host_script_configs')


def remove_script_config(probe_id):
    probe_id = util.convert_mac(probe_id, mode='storage')
    dir_path = '{}/host_vars/{}/'.format(settings.ANSIBLE_PATH, probe_id)
    shutil.rmtree(dir_path)


def _write_script_config(dir_path, script_data, entry_name):
    if not os.path.exists(dir_path):
        makedirs(dir_path)

    script_data = {entry_name: script_data}

    with open(dir_path + 'script_configs', 'w') as f:
        f.write('---\n')
        f.write(yaml.dump(script_data))


def update_hosts_file():
    pass


def run_ansible_playbook(username):
    command = ['ansible-playbook', '-i', settings.ANSIBLE_PATH + 'hosts',
               settings.ANSIBLE_PATH + 'probe.yml', '--vault-password-file',
               settings.ANSBILE_PATH + 'vault_pass.txt']
