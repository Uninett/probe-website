from flask import request
from probe_website import util

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


def upload_certificate():
    error = ''
    return True

    # if 'file' not in request.files:
    #     error += 'File part missing.\n'
    #     return  # error ?

    # cert = request.files[
    # filename = util.parse_configs(request.files.items(), 'network')
    # print(filename)


def update_probe(probe_id):
    new_name = request.form.get('probe_name', '')
    new_probe_id = request.form.get('probe_id', '')
    new_location = request.form.get('probe_location', '')
    new_contact_person = request.form.get('contact_person', '')
    new_contact_email = request.form.get('contact_email', '')

    successful = database.update_probe(probe_id, new_name, new_probe_id, new_location,
                                       new_contact_person, new_contact_email)
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
