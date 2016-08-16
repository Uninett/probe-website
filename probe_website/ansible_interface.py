from probe_website import settings, util, app
import yaml
import os.path
from os import makedirs
import shutil
from subprocess import Popen
import re
from flask import flash


def load_default_config(username, config_name):
    filename = os.path.join(settings.ANSIBLE_PATH, 'group_vars', username, config_name)
    # Change to global default if there is no group default
    if not os.path.isfile(filename):
        filename = os.path.join(settings.ANSIBLE_PATH, 'group_vars', 'all', config_name)
        if not os.path.isfile(filename):
            # There is no default config with that name
            return ''

    with open(filename, 'r') as f:
        # Should probably check for malformed config file here
        return yaml.safe_load(f)


# Data is a normal python data structure consisting of lists & dicts
def export_group_config(username, data, filename):
    dir_path = os.path.join(settings.ANSIBLE_PATH, 'group_vars', username)
    _write_config(dir_path, data, filename)


def export_host_config(probe_id, data, filename):
    probe_id = util.convert_mac(probe_id, mode='storage')
    dir_path = os.path.join(settings.ANSIBLE_PATH, 'host_vars', probe_id)
    _write_config(dir_path, data, filename)


# Make a hosts file for this user at <ansible_root>/inventories/username/hosts
def export_to_inventory(username, database):
    from probe_website.database import Probe

    dir_path = os.path.join(settings.ANSIBLE_PATH, 'inventory')
    if not os.path.exists(dir_path):
        makedirs(dir_path)

    user = database.get_user(username)
    with open(os.path.join(dir_path, username), 'w') as f:
        f.write('[{}]\n'.format(username))
        for probe in database.session.query(Probe).filter(Probe.user_id == user.id).all():
            if probe.associated and util.is_probe_connected(probe.port):
                entry = '{} ansible_host=localhost ansible_port={} probe_name="{}"'.format(
                            probe.custom_id,
                            probe.port,
                            probe.name)
                f.write(entry + '\n')


def export_known_hosts(database):
    from probe_website.database import Probe

    path = os.path.join(settings.ANSIBLE_PATH, 'known_hosts')

    with open(path, 'w') as f:
        for key, port in database.session.query(Probe.host_key, Probe.port).all():
            if key != '':
                key = key.replace('localhost', '[localhost]:{}'.format(port))
                f.write(key + '\n')


def remove_host_config(probe_id):
    probe_id = util.convert_mac(probe_id, mode='storage')
    dir_path = os.path.join(settings.ANSIBLE_PATH, 'host_vars', probe_id)
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)


def _write_config(dir_path, data, filename):
    if not os.path.exists(dir_path):
        makedirs(dir_path)

    with open(os.path.join(dir_path, filename), 'w') as f:
        f.write('---\n')
        f.write(yaml.dump(data))


def make_certificate_default(probe_id, username):
    src = os.path.join(app.config['UPLOAD_FOLDER'], 'host_certs', probe_id)
    dst = os.path.join(app.config['UPLOAD_FOLDER'], 'group_certs', username)

    if os.path.exists(dst):
        shutil.rmtree(dst)

    shutil.copytree(src, dst)


def load_default_certificate(username, probe_id):
    src = os.path.join(app.config['UPLOAD_FOLDER'], 'group_certs', username)
    dst = os.path.join(app.config['UPLOAD_FOLDER'], 'host_certs', probe_id)

    if not os.path.exists(src):
        return
    if os.path.exists(dst):
        shutil.rmtree(dst)

    shutil.copytree(src, dst)


def remove_host_cert(probe_id):
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'host_certs', probe_id)
    if os.path.exists(path):
        shutil.rmtree(path)


def get_certificate_data(username, probe_id):
    data = {'any': '', 'two_g': '', 'five_g': ''}
    src = os.path.join(app.config['UPLOAD_FOLDER'], 'host_certs', probe_id)
    if not os.path.exists(src):
        src = os.path.join(app.config['UPLOAD_FOLDER'], 'group_certs', username)
        if not os.path.exists(src):
            return data

    for freq in ['any', 'two_g', 'five_g']:
        path = os.path.join(src, freq)
        if os.path.exists(path):
            files = os.listdir(path)
            # There should in theory only be one file  in this directory
            if len(files) > 0:
                data[freq] = files[0]

    return data


def run_ansible_playbook(username):
    inventory = os.path.join(settings.ANSIBLE_PATH, 'inventory', username)
    command = ['ansible-playbook',
               '-i', inventory,
               os.path.join(settings.ANSIBLE_PATH, 'probe.yml'),
               '--vault-password-file', os.path.join(settings.ANSIBLE_PATH, 'vault_pass.txt'),
               "--ssh-common-args='-o UserKnownHostsFile={}/known_hosts'".format(settings.ANSIBLE_PATH)]

    with open(inventory, 'r') as f:
        # Do not run Ansible if the inventory file is empty
        # (the first line will be the username)
        if len(f.readlines()) <= 1:
            return

    dir_path = os.path.join(settings.ANSIBLE_PATH, 'logs')
    if not os.path.exists(dir_path):
        makedirs(dir_path)
    log_file = open(os.path.join(dir_path, username), 'w')
    log_file.write('')  # Be sure to clear the file

    # This will run in parallel with the web application. stdout will
    # be logged to the log_file, so to check the status of the command,
    # just check that file (if the 'PLAY RECAP' string is in the log,
    # the command has been completed)
    Popen(command, stdout=log_file)


# Reads the log from running the ansible-playbook command (done in func
# run_ansible_playbook), and returns:
#   * Not started (no log file or empty):       None
#   * Unfinished (No 'PLAY RECAP' in log file): 'running'
#   * Finished ('PLAY RECAP' in log file):      dictionary of each probe's state, like:
#       status = {'123456abcdef': 'succeeded',
#                 'abcdef123456': 'failed'}
def get_playbook_status(username):
    log_file = os.path.join(settings.ANSIBLE_PATH, 'logs', username)
    if not os.path.isfile(log_file):
        return None

    with open(log_file, 'r') as f:
        cont = f.read()
        if 'PLAY RECAP' not in cont:
            return 'running'
        elif 'PLAY RECAP' in cont:
            # Matches lines like this, and extracts the numbers:
            # '12af4521deee               : ok=0    changed=0    unreachable=1    failed=0' 
            regex = '([a-zA-Z0-9_-]+)\s+:\s+ok=([0-9]+)+\s+changed=([0-9]+)\s+unreachable=([0-9]+)+\s+failed=([0-9]+)+'
            probes = re.findall(regex, cont)
            status = {name: int(unreachable)+int(failed) for name, ok, changed, unreachable, failed in probes}
            for key, value in status.items():
                status[key] = 'succeeded' if value == 0 else 'failed'

            flash(settings.INFO_MESSAGE['shutdown_warning'], 'info')
            return status

    return None
