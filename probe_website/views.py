from probe_website import app
from flask import render_template, request, abort, redirect, url_for
import probe_website.database
from probe_website import settings, form_parsers
from probe_website import ansible_interface as ansible

database = probe_website.database.DatabaseManager(settings.DATABASE_PATH)
form_parsers.set_database(database)

USERNAME = 'testuser'


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


@app.route('/databases', methods=['GET', 'POST'])
def databases():
    message_for_user = ''
    if request.method == 'POST':
        successful = form_parsers.update_databases(USERNAME)
        if successful:
            database.save_changes()
            ansible.export_group_config(USERNAME,
                                        {'databases': database.get_database_info(USERNAME)},
                                        'database_configs')
        else:
            database.revert_changes()
            message_for_user += settings.ERROR_MESSAGE['invalid_database_settings']

    return generate_databases_template(USERNAME, message_for_user)


@app.route('/probes', methods=['GET', 'POST'])
def probes():
    message_for_user = ''
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'new_probe':
            error_message = form_parsers.new_probe()
            message_for_user += error_message
        elif action == 'remove_probe':
            probe_id = request.form.get('probe_id', '')
            database.remove_probe(probe_id)
            ansible.remove_host_config(probe_id)
            database.save_changes()
        elif action == 'push_config':
            # Export the script configs in the sql database to ansible readable configs
            for probe in database.session.query(probe_website.database.Probe).all():
                ansible.export_host_config(probe.custom_id,
                                           {'host_script_configs': database.get_script_data(probe)},
                                           'script_configs')
                ansible.export_host_config(probe.custom_id,
                                           {'networks': database.get_network_config_data(probe)},
                                           'network_configs')

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
        successful_script_update = form_parsers.update_scripts()
        successful_network_update = form_parsers.update_network_configs()
        successful_certificate_upload = form_parsers.upload_certificate()
        successful_probe_update = form_parsers.update_probe(probe_id)

        if (successful_script_update and
                successful_probe_update and
                successful_network_update and
                successful_certificate_upload):
            database.save_changes()

            action = request.form.get('action', '')
            if action == 'save_as_default':
                ansible.export_group_config(USERNAME,
                                            {'group_script_configs': database.get_script_data(probe)},
                                            'script_configs')
                ansible.export_group_config(USERNAME,
                                            {'networks': database.get_network_config_data(probe)},
                                            'network_configs')
                #
                # Do something to save the uploaded certificate as default
                #

            return redirect(url_for('probes'))
        else:
            database.revert_changes()
            if not successful_script_update:
                message_for_user += settings.ERROR_MESSAGE['invalid_scripts']
            if not successful_probe_update:
                message_for_user += settings.ERROR_MESSAGE['invalid_mac']
            if not successful_network_update:
                message_for_user += settings.ERROR_MESSAGE['invalid_network_config']
            if not successful_certificate_upload:
                message_for_user += settings.ERROR_MESSAGE['invalid_certificate']

    return generate_probe_setup_template(probe_id, message_for_user)


#################################################################
#                                                               #
#  Everything below should probably be moved to its own module  #
#                                                               #
#################################################################


def generate_probe_setup_template(probe_id, message_for_user):
    probe_data = database.get_probe_data(probe_id)
    required_entries = [
            {'key': 'probe_name', 'description': 'Probe name', 'value': probe_data['name']},
            {'key': 'probe_id', 'description': 'wlan0 MAC address', 'value': probe_data['id']},
            {'key': 'probe_location', 'description': 'Probe location', 'value': probe_data['location']},
            {'key': 'contact_person', 'description': 'Contact person (name)', 'value': probe_data['contact_person']},
            {'name': 'contact_email', 'description': 'Contact email', 'value': probe_data['contact_email']},
    ]

    return render_template('probe_setup.html',
                           message=message_for_user,
                           required=required_entries,
                           scripts=probe_data['scripts'],
                           network_configs=probe_data['network_configs'])

def generate_databases_template(username, message_for_user):
    db_info = database.get_database_info(USERNAME)

    return render_template('databases.html',
                           dbs=db_info,
                           message=message_for_user)


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
