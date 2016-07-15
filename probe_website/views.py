from probe_website import app
from flask import render_template, request, abort, redirect, url_for, flash
import probe_website.database
from probe_website.database import User
from probe_website import settings, form_parsers, util
from probe_website import ansible_interface as ansible
import flask_login
from flask_login import current_user

database = probe_website.database.DatabaseManager(settings.DATABASE_PATH)
form_parsers.set_database(database)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def user_loader(username):
    try:
        user = database.session.query(User).filter(User.username == username).first()
    except:
        user = None
    return user


@app.teardown_appcontext
def shutdown_database_session(exception=None):
    database.shutdown_session()


@app.route('/')
def index():
    if flask_login.current_user.is_authenticated:
        return render_template('index.html')
    else:
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        user = user_loader(username)

        # NB: Should not save passwords in plaintext (temporary solution)
        if user is not None and user.password == password:
            flask_login.login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid login', 'error')

    return render_template('login.html')


@app.route('/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return redirect(url_for('login'))


@app.route('/download_image', methods=['GET', 'POST'])
@flask_login.login_required
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
@flask_login.login_required
def databases():
    if request.method == 'POST':
        successful = form_parsers.update_databases(current_user.username)
        if successful:
            database.save_changes()
            ansible.export_group_config(current_user.username,
                                        {'databases': database.get_database_info(current_user.username)},
                                        'database_configs')
            flash('Settings successfully saved', 'info')
        else:
            database.revert_changes()
            flash(settings.ERROR_MESSAGE['invalid_database_settings'], 'error')

    return generate_databases_template(current_user.username)


@app.route('/probes', methods=['GET', 'POST'])
@flask_login.login_required
def probes():
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'new_probe':
            form_parsers.new_probe(current_user.username)
        elif action == 'remove_probe':
            probe_id = request.form.get('probe_id', '')
            success = database.remove_probe(current_user.username, probe_id)
            if not success:
                flash('Invalid probe ID', 'error')
            else:
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

    probes = database.get_all_probes_data(current_user.username)
    return render_template('probes.html', probes=probes)


@app.route('/probe_setup', methods=['GET', 'POST'])
@flask_login.login_required
def probe_setup():
    probe_id = request.args.get('id', '')
    if probe_id == '':
        print('No probe ID specified')
        abort(404)

    probe_id = util.convert_mac(probe_id, mode='storage')
    probe = database.get_probe(probe_id)

    if request.method == 'POST':
        successful_script_update = form_parsers.update_scripts()
        successful_network_update = form_parsers.update_network_configs()
        successful_certificate_upload = form_parsers.upload_certificate(probe_id, current_user.username)
        successful_probe_update = form_parsers.update_probe(probe_id)

        if (successful_script_update and
                successful_probe_update and
                successful_network_update and
                successful_certificate_upload):
            database.save_changes()

            action = request.form.get('action', '')
            if action == 'save_as_default':
                ansible.export_group_config(current_user.username,
                                            {'group_script_configs': database.get_script_data(probe)},
                                            'script_configs')
                ansible.export_group_config(current_user.username,
                                            {'networks': database.get_network_config_data(probe)},
                                            'network_configs')

                ansible.make_certificate_default(probe_id, current_user.username)

            return redirect(url_for('probes'))
        else:
            database.revert_changes()

    return generate_probe_setup_template(probe_id, current_user.username)


@app.route('/user_managment', methods=['GET', 'POST'])
@flask_login.login_required
def user_managment():
    if not current_user.admin:
        return abort(403)

    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'new_user':
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            contact_person = request.form.get('contact_person', '')
            contact_email = request.form.get('contact_email', '')

            success = database.add_user(username, password, contact_person, contact_email)
            if not success:
                database.revert_changes()
                flash('Could not add user. The username is probably already taken', 'error')
            else:
                database.save_changes()
                flash('Successfully added user {}'.format(username), 'info')
        elif action == 'remove_user':
            username = request.form.get('username', '')
            if username == current_user.username:
                flash('You cannot remove yourself!', 'error')
            else:
                success = database.remove_user(username)
                if success:
                    database.save_changes()
                    flash('User {} successfully removed'.format(username), 'info')
                else:
                    database.revert_changes()

    return render_template('user_managment.html', users=database.get_all_user_data())


#################################################################
#                                                               #
#  Everything below should probably be moved to its own module  #
#                                                               #
#################################################################


def generate_probe_setup_template(probe_id, username):
    probe_data = database.get_probe_data(probe_id)
    required_entries = [
            {'key': 'probe_name', 'description': 'Probe name', 'value': probe_data['name']},
            {'key': 'probe_id', 'description': 'wlan0 MAC address', 'value': probe_data['id']},
            {'key': 'probe_location', 'description': 'Probe location', 'value': probe_data['location']},
    ]

    cert_data = ansible.get_certificate_data(username, probe_id)
    return render_template('probe_setup.html',
                           required=required_entries,
                           scripts=probe_data['scripts'],
                           network_configs=probe_data['network_configs'],
                           cert_data=cert_data)

def generate_databases_template(username):
    db_info = database.get_database_info(current_user.username)

    return render_template('databases.html',
                           dbs=db_info)
