from probe_website import settings, util, app
import yaml
import os.path
from os import makedirs
import shutil
from subprocess import Popen
import re
from flask import flash
import time


def load_default_config(username, config_name):
    """Use 'username' and 'config_name' to locate and load a default YAML
    config file (used for Ansible)"""
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
    """Export 'data' as a user specific YAML config file under the name
    'filename' for the user 'username'"""
    dir_path = os.path.join(settings.ANSIBLE_PATH, 'group_vars', username)
    _write_config(dir_path, data, filename)


def export_host_config(probe_id, data, filename):
    """Export 'data' as a host/probe specific YAML config file under the name
    'filename' for the probe with 'probe_id' as custom id (a MAC)"""
    probe_id = util.convert_mac(probe_id, mode='storage')
    dir_path = os.path.join(settings.ANSIBLE_PATH, 'host_vars', probe_id)
    _write_config(dir_path, data, filename)


# Make a hosts file for this user at <ansible_root>/inventories/username/hosts
def export_to_inventory(username, database):
    """Export an Ansible hosts file for 'username' at
    <ansible_root>/inventory/<username> from the supplied SQL database

    Each inventory entry will be in the following format:
    [<username>]
    <mac> ansible_host=localhost ansible_port=<port> probe_name=<name>
    ...
    """
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
    """Export a known_hosts file from the host keys in 'database', for use
    with SSH when Ansible pushes configs

    Each entry will be in the format:
    [localhost]:<port> <host key>
    """
    from probe_website.database import Probe

    path = os.path.join(settings.ANSIBLE_PATH, 'known_hosts')

    with open(path, 'w') as f:
        for key, port in database.session.query(Probe.host_key, Probe.port).all():
            if key != '':
                key = key.replace('localhost', '[localhost]:{}'.format(port))
                f.write(key + '\n')


def remove_host_config(probe_id):
    """Remove all Ansible configs associated with 'probe_id'"""
    probe_id = util.convert_mac(probe_id, mode='storage')
    dir_path = os.path.join(settings.ANSIBLE_PATH, 'host_vars', probe_id)
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)


def _write_config(dir_path, data, filename):
    """Write the python data structure 'data' as a YAML config to the
    file 'filename', located at 'dir_path'"""
    if not os.path.exists(dir_path):
        makedirs(dir_path)

    with open(os.path.join(dir_path, filename), 'w') as f:
        f.write('---\n')
        f.write(yaml.dump(data))


def make_certificate_default(probe_id, username):
    """Make 'probe_id's uploaded wpa_supplicant certificate the default one for any
    new probes added by 'username'"""
    src = os.path.join(app.config['UPLOAD_FOLDER'], 'host_certs', probe_id)
    dst = os.path.join(app.config['UPLOAD_FOLDER'], 'group_certs', username)

    if os.path.exists(dst):
        shutil.rmtree(dst)

    shutil.copytree(src, dst)


def load_default_certificate(username, probe_id):
    """Load 'username's default wpa_supplicant certificate"""
    src = os.path.join(app.config['UPLOAD_FOLDER'], 'group_certs', username)
    dst = os.path.join(app.config['UPLOAD_FOLDER'], 'host_certs', probe_id)

    if not os.path.exists(src):
        return
    if os.path.exists(dst):
        shutil.rmtree(dst)

    shutil.copytree(src, dst)


def remove_host_cert(probe_id):
    """Remove 'probe_id's wpa_supplicant certificate"""
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'host_certs', probe_id)
    if os.path.exists(path):
        shutil.rmtree(path)


def get_certificate_data(username, probe_id):
    """Return a dictionary containing the filenames of the uploaded certificates,
    for any, 2.4GHz and 5 GHz, respectively"""
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


# Using this as a global var is not very nice. Maybe find a better solution.
_ansible_pid = {}


def run_ansible_playbook(username):
    """Start an Ansible instance as subprocess with 'username's configs

    Pipe all output from the Ansible process to a separate logfile
    """
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
    log_file.write(' ')  # Be sure to clear the file

    # This will run in parallel with the web application. stdout will
    # be logged to the log_file, so to check the status of the command,
    # just check that file (if the 'PLAY RECAP' string is in the log,
    # the command has been completed)
    if not is_ansible_running(username):
        ps = Popen(command, stdout=log_file)
        global ansible_pid
        _ansible_pid[username] = ps.pid

    log_file.close()

    # Change ansible status immediately
    get_playbook_status(username, probe=None, force_fileread=True)


def is_ansible_running(username):
    if username in _ansible_pid:
        return os.path.exists('/proc/{}'.format(_ansible_pid[username]))
    return False

_playbook_status = None


def get_playbook_status(username, probe=None, force_fileread=False):
    """Return whether ansible is running or not, and optionally the results
    of the last Ansible run. This is the "front-end" function to
    _read_playbook_status()

    This function should be used instead of _read_playbook_status, because
    this function does not read the log file as each call, but rather only
    if a set time has passed since last time the log was read.

    If force_fileread is True, the file reading timer will be ignored.

    If only username is supplied, return one of:
        running             : ansible is running
        not-running         : ansible is not running

    If probe is supplied too, return the status for that specific probe, which
    will be one of the  following:
        updating            : probe is currently updating
        completed           : probe completed successfully in the last update
        failed              : probe failed in the last update
        unknown             : the log file could not be read
    """

    global _playbook_status

    update_interval = 30
    if (not force_fileread and
            _playbook_status is not None and
            'timestamp' in _playbook_status and
            time.time() - _playbook_status['timestamp'] < update_interval):
        pass
    else:
        _playbook_status = _read_playbook_status(username)
        if _playbook_status is None:
            return 'unknown'

    # If no probe is specified, return the status of Ansible itself (running or not-running)
    ansible_running = is_ansible_running(username)
    if probe is None:
        return 'running' if ansible_running else 'not-running'

    # If the probe was updated last time Ansible was run, return completed or failed
    if probe.custom_id in _playbook_status:
        return _playbook_status[probe.custom_id]

    return 'unknown'


def _read_playbook_status(username):
    """Do not run ths function directly; use get_playbook_status instead.

    Read the log generated by the ansible-playbook command and parse its content.

    run_ansible_playbook), and return:
      * Not started (no log file or empty):        None
      * Unfinished (No 'PLAY RECAP' in log file):  'running'
      * Finished ('PLAY RECAP' in log file):       dictionary of each probe's state, like:
                                                   status = {'123456abcdef': 'succeeded'
                                                             'abcdef123456': 'failed'}
    """
    status = {}

    status['timestamp'] = time.time()

    log_file = os.path.join(settings.ANSIBLE_PATH, 'logs', username)
    inventory_file = os.path.join(settings.ANSIBLE_PATH, 'inventory', username)
    if not os.path.isfile(log_file) or not os.path.isfile(inventory_file):
        status['ansible'] = 'not-running'
        return status

    with open(log_file, 'r') as log_f, open(inventory_file, 'r') as inv_f:
        log_cont = log_f.read()
        inv_cont = inv_f.read()
        # Ansible is done updating
        if 'PLAY RECAP' in log_cont:
            # Matches lines like this, and extracts the numbers:
            # '12af4521deee               : ok=0    changed=0    unreachable=1    failed=0'
            regex = '([a-zA-Z0-9_-]+)\s+:\s+ok=([0-9]+)+\s+changed=([0-9]+)\s+unreachable=([0-9]+)+\s+failed=([0-9]+)+'
            probes = re.findall(regex, log_cont)
            status = {name: int(unreachable)+int(failed) for name, ok, changed, unreachable, failed in probes}
            for key, value in status.items():
                status[key] = 'completed' if value == 0 else 'failed'
        # Ansible is running
        elif log_cont != '' and is_ansible_running(username):
            regex = '\n([a-zA-Z0-9_-]+) '
            probes = re.findall(regex, inv_cont)
            status = {name: 'updating' for name in probes}

    status['timestamp'] = time.time()
    return status
