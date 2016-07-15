from flask import request, flash
from probe_website import util, app, settings, ansible_interface
from werkzeug.utils import secure_filename
import os
import shutil

# NB: This module doesn't just parse forms, but also updates the database
# (Though it doesn't make the changes persistent on its own, so changes
# made can be reverted)

database = None


# This function MUST be called before any other functions in this module
def set_database(new_database):
    global database
    database = new_database


def update_scripts():
    probe_id = request.args.get('id', '')
    script_configs = util.parse_configs(request.form.items(), 'script')
    blank_config = {
            'name': None,
            'script_file': None,
            'args': None,
            'minute_interval': None,
            'enabled': None,
    }

    probe = database.get_probe(probe_id)
    successful = True
    for script_id, config in script_configs.items():
        # Merge the two dicts
        m_dict = blank_config.copy()
        m_dict.update(config)
        success = database.update_script(probe, script_id, m_dict['name'], m_dict['script_file'],
                                         m_dict['args'], m_dict['minute_interval'], m_dict['enabled'])
        if not success:
            successful = False

    return successful


def update_network_configs():
    probe_id = request.args.get('id', '')
    network_configs = util.parse_configs(request.form.items(), 'network')
    blank_config = {
            'ssid': None,
            'anonymous_id': None,
            'username': None,
            'password': None,
    }

    probe = database.get_probe(probe_id)
    successful = True
    for config_id, config in network_configs.items():
        # Merge the two dicts
        m_dict = blank_config.copy()
        m_dict.update(config)
        success = database.update_network_config(probe, config_id, m_dict['ssid'], m_dict['anonymous_id'],
                                                 m_dict['username'], m_dict['password'])
        if not success:
            successful = False

    return successful


def upload_certificate(probe_id, username):
    certs = util.parse_configs(request.files.items(), 'network')
    probe = database.get_probe(probe_id)
    data = ansible_interface.get_certificate_data(username, probe_id)
    successful = True

    for net_conf_id, tup in certs.items():
        freq = database.get_network_config(probe, net_conf_id).name

        if 'certificate' not in tup:
            flash('Certificate file part missing.', 'error')
            successful = False
            break

        cert = tup['certificate']
        if cert.filename == '':
            if freq in data and data[freq] != '':
                continue
            flash('No certificate file selected.', 'error')
            successful = False
            break

        if cert and util.allowed_cert_filename(cert.filename):
            filename = secure_filename(cert.filename)


            path = os.path.join(app.config['UPLOAD_FOLDER'], 'host_certs', probe_id, freq)
            if os.path.exists(path):
                shutil.rmtree(path)  # Empty the dir
            os.makedirs(path)
            cert.save(os.path.join(path, filename))
        else:
            flash('Invalid certificate filename extension.', 'error')
            successful = False
            break

    return successful


def update_probe(probe_id):
    new_name = request.form.get('probe_name', '')
    new_probe_id = request.form.get('probe_id', '')
    new_location = request.form.get('probe_location', '')

    successful = database.update_probe(probe_id, new_name, new_probe_id, new_location)
    return successful


def update_databases(username):
    configs = util.parse_configs(request.form.items(), 'database')
    user = database.get_user(username)

    successful = True
    for db_id, config in configs.items():
        success = database.update_database(user, db_id, db_name=config['db_name'], address=config['address'],
                                           port=config['port'], username=config['username'],
                                           password=config['password'])
        if not success:
            successful = False

    return successful


def new_probe(username):
    name = request.form.get('probe_name', '')
    probe_id = request.form.get('probe_id', '')
    location = request.form.get('probe_location', '')

    new_probe = database.add_probe(username=username, probe_name=name, custom_id=probe_id, location=location)

    # If new_probe is None, it means there already existed a probe with that ID
    # (Note that in this case, nothing will be added to the database)
    if new_probe is not None:
        database.save_changes()
    else:
        if not database.is_valid_id(probe_id):
            flash(settings.ERROR_MESSAGE['invalid_mac'], 'error')
        else:
            flash('Something went wrong when processing the entry.', 'error')
        return False

    return True


def new_user():
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    contact_person = request.form.get('contact_person', '')
    contact_email = request.form.get('contact_email', '')

    success = database.add_user(username, password, contact_person, contact_email)
    return success
