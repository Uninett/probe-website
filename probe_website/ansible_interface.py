from probe_website import settings
import yaml
import os.path
from os import makedirs

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
    if not os.path.exists(dir_path):
        makedirs(dir_path)

    script_data = {'default_script_configs': script_data}

    with open(dir_path + 'script_configs', 'w') as f:
        f.write('---\n')
        f.write(yaml.dump(script_data))


def export_script_config(probe_id, script_data):
    dir_path = '{}/host_vars/{}/'.format(settings.ANSIBLE_PATH, probe_id)
    if not os.path.exists(dir_path):
        makedirs(dir_path)

    script_data = {'host_script_configs': script_data}

    with open(dir_path + 'script_configs', 'w') as f:
        f.write('---\n')
        f.write(yaml.dump(script_data))
