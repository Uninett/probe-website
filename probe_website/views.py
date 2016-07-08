from probe_website import app
from flask import render_template, request, abort, redirect, url_for
import yaml
from probe_website.database import Database

# These probably shouldn't be hardcoded
ANSIBLE_PATH = '/home/frestr/Ansible/wifi_probe/'
DATABASE_PATH = '/home/frestr/Projects/probe_website/database.db'

database = Database(DATABASE_PATH)

ERROR_MESSAGE = {
        'invalid_mac': (
            'The supplied MAC address was not valid or is already in use. '
        )
}


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
        print(request.form)
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
            name = request.form.get('probe_name', '')
            probe_id = request.form.get('probe_id', '')
            location = request.form.get('probe_location', '')
            contact_person = request.form.get('contact_person', '')
            contact_email = request.form.get('contact_email', '')

            new_probe = database.add_probe(name=name, custom_id=probe_id, location=location,
                                           contact_person=contact_person, contact_email=contact_email)
            # If new_probe is None, it means there already existed a probe with that ID
            # (Note that in this case, nothing will be added to the database)
            if new_probe is not None:
                database.save_changes()
            else:
                if not database.is_valid_id(probe_id):
                    message_for_user = ERROR_MESSAGE['invalid_mac']
                else:
                    message_for_user = (
                        'Something went wrong when processing the entry.'
                    )
                                        
        elif action == 'remove_probe':
            probe_id = request.form.get('probe_id', '')
            database.remove_probe(probe_id)
            database.save_changes()

    probes = database.get_all_probes_data('nouser')
    return render_template('probes.html', probes=probes, message=message_for_user)


@app.route('/probe_setup', methods=['GET', 'POST'])
def probe_setup():
    message_for_user = ''
    probe_id = request.args.get('id', '')
    if probe_id == '':
        print('No probe ID specified')
        abort(404)

    if request.method == 'POST':
        new_name = request.form.get('probe_name', '')
        new_probe_id = request.form.get('probe_id', '')
        new_location = request.form.get('probe_location', '')
        new_contact_person = request.form.get('contact_person', '')
        new_contact_email = request.form.get('contact_email', '')

        successful = database.update_probe(probe_id, new_name, new_probe_id, new_location,
                                           new_contact_person, new_contact_email)
        if successful:
            database.save_changes()
            return redirect(url_for('probes'))
        else:
            database.revert_changes()
            message_for_user = ERROR_MESSAGE['invalid_mac']

    probe_data = database.get_probe_data(probe_id)
    required_entries = [
            {'name': 'probe_name', 'description': 'Probe name', 'value': probe_data['name']},
            {'name': 'probe_id', 'description': 'wlan0 MAC address', 'value': probe_data['id']},
            {'name': 'location', 'description': 'Probe location', 'value': probe_data['location']},
            {'name': 'contact_person', 'description': 'Contact person (name)', 'value': probe_data['contact_person']},
            {'name': 'contact_email', 'description': 'Contact email', 'value': probe_data['contact_email']},
    ]

    if len(probe_data['scripts']) == 0:
        # Load default configs
        with open(ANSIBLE_PATH + 'group_vars/all/script_configs') as f:
            probe_data['scripts'] = yaml.safe_load(f)['default_script_configs']

    return render_template('probe_setup.html',
                           message=message_for_user,
                           required=required_entries,
                           scripts=probe_data['scripts'])


def get_probe(probe_id):
    #MOCK OBJECT
    probe = {'name': 'probe', 'location': 'norway', 'contact_person': '', 'contact_email': ''}
    return probe
