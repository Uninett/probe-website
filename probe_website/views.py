from probe_website import app
from flask import render_template, request, abort, redirect, url_for
from probe_website.database import Database
from probe_website import util, settings
from probe_website import ansible_interface as ansible
from probe_website.database import Probe

database = Database(settings.DATABASE_PATH)

USERNAME = 'test'


@app.teardown_appcontext
def shutdown_database_session(exception=None):
    database.shutdown_session()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/download_image', methods=['GET', 'POST'])
def download_image():
    required_entries = [
            {'name': 'ssid', 'description': 'SSID'},
            {'name': 'anonymous_identity', 'description': 'Anonymous identity'},
            {'name': 'identity', 'description': 'Identity'},
            {'name': 'password', 'description': 'Password'}
    ]
    optional_entries = [
            {'name': 'scan_ssid', 'description': 'Scan SSID', 'value': '1'},
            {'name': 'key_mgmt', 'description': 'Key managment', 'value': 'WPA-EAP'},
            {'name': 'eap', 'description': 'EAP', 'value': 'TTLS'},
            {'name': 'phase1', 'description': 'Phase 1', 'value': 'peaplabel=0'},
            {'name': 'phase2', 'description': 'Phase 2', 'value': 'auth=MSCHAPV2'},
    ]
    if request.method == 'POST':
        return render_template('download_image.html',
                               required=required_entries,
                               optional=optional_entries)
    else:
        return render_template('download_image.html',
                               required=required_entries,
                               optional=optional_entries)


@app.route('/probes', methods=['GET', 'POST'])
def probes():
    message_for_user = ''
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'new_probe':
            error_message = new_probe()
            message_for_user += error_message
        elif action == 'remove_probe':
            probe_id = request.form.get('probe_id', '')
            database.remove_probe(probe_id)
            database.save_changes()
        elif action == 'push_config':
            for probe in database.session.query(Probe).all():
                ansible.export_script_config(probe.custom_id, database.get_script_data(probe))

    probes = database.get_all_probes_data('nouser')
    return render_template('probes.html', probes=probes, message=message_for_user)


@app.route('/probe_setup', methods=['GET', 'POST'])
def probe_setup():
    message_for_user = ''
    probe_id = request.args.get('id', '')
    if probe_id == '':
        print('No probe ID specified')
        abort(404)
    
    probe = database.get_probe(probe_id)

    if request.method == 'POST':
        successful_script_update = update_scripts()
        successful_probe_update = update_probe(probe_id)

        if successful_script_update and successful_probe_update:
            database.save_changes()

            action = request.form.get('action', '')
            if action == 'save_as_default':
                ansible.export_script_config_as_default(USERNAME, database.get_script_data(probe))

            return redirect(url_for('probes'))
        else:
            database.revert_changes()
            if not successful_script_update:
                message_for_user = settings.ERROR_MESSAGE['invalid_scripts']
            if not successful_probe_update:
                message_for_user = settings.ERROR_MESSAGE['invalid_mac']

    return generate_probe_setup_template(probe_id, message_for_user)


#################################################################
#                                                               #
#  Everything below should probably be moved to its own module  #
#                                                               #
#################################################################

def update_scripts():
    probe_id = request.args.get('id', '')
    script_configs = util.parse_script_configs(request.form.items())
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


def update_probe(probe_id):
    new_name = request.form.get('probe_name', '')
    new_probe_id = request.form.get('probe_id', '')
    new_location = request.form.get('probe_location', '')
    new_contact_person = request.form.get('contact_person', '')
    new_contact_email = request.form.get('contact_email', '')

    successful = database.update_probe(probe_id, new_name, new_probe_id, new_location,
                                       new_contact_person, new_contact_email)
    return successful

def generate_probe_setup_template(probe_id, message_for_user):
    probe_data = database.get_probe_data(probe_id)
    required_entries = [
            {'name': 'probe_name', 'description': 'Probe name', 'value': probe_data['name']},
            {'name': 'probe_id', 'description': 'wlan0 MAC address', 'value': probe_data['id']},
            {'name': 'probe_location', 'description': 'Probe location', 'value': probe_data['location']},
            {'name': 'contact_person', 'description': 'Contact person (name)', 'value': probe_data['contact_person']},
            {'name': 'contact_email', 'description': 'Contact email', 'value': probe_data['contact_email']},
    ]

    return render_template('probe_setup.html',
                           message=message_for_user,
                           required=required_entries,
                           scripts=probe_data['scripts'])

def new_probe():
    message_for_user = ''

    name = request.form.get('probe_name', '')
    probe_id = request.form.get('probe_id', '')
    location = request.form.get('probe_location', '')
    contact_person = request.form.get('contact_person', '')
    contact_email = request.form.get('contact_email', '')

    new_probe = database.add_probe(username=USERNAME, probe_name=name, custom_id=probe_id, location=location,
                                   contact_person=contact_person, contact_email=contact_email)
    # If new_probe is None, it means there already existed a probe with that ID
    # (Note that in this case, nothing will be added to the database)
    if new_probe is not None:
        database.save_changes()
    else:
        if not database.is_valid_id(probe_id):
            message_for_user = settings.ERROR_MESSAGE['invalid_mac']
        else:
            message_for_user = (
                'Something went wrong when processing the entry.'
            )

    return message_for_user
