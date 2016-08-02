from probe_website import settings, util, app
import yaml
import os.path
from os import makedirs
from subprocess import Popen
import shutil


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
def export_to_inventory(username):
    dir_path = os.path.join(settings.ANSIBLE_PATH, 'inventories', username)
    if not os.path.exists(dir_path):
        makedirs(dir_path)

    with open(os.path.join(dir_path, 'hosts'), 'w') as f:
        # Each entry is in the form:
        # <probe_wlan0_mac> ansible_host=localhost ansible_port=<probe_port> probe_name=<is this needed?>
        pass


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


def update_hosts_file():
    pass


def run_ansible_playbook(username):
    command = ['ansible-playbook', '-i', settings.ANSIBLE_PATH + 'hosts',
               settings.ANSIBLE_PATH + 'probe.yml', '--vault-password-file',
               settings.ANSBILE_PATH + 'vault_pass.txt']
