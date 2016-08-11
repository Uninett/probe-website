from probe_website import app
from flask import render_template, request, abort, redirect, url_for, flash
import probe_website.database
from probe_website.database import User, Probe
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

        if user is not None and user.check_password(password):
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


@app.route('/download_image', methods=['GET'])
@flask_login.login_required
def download_image():
    return render_template('download_image.html')


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
            flash(settings.ERROR_MESSAGE['invalid_settings'], 'error')

    db_info = database.get_database_info(current_user.username)

    return render_template('databases.html',
                           dbs=db_info)


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
        elif action == 'renew_period':
            probe_id = request.form.get('probe_id', '')
            probe = database.get_probe(probe_id)
            if probe is not None and probe.user.username == current_user.username:
                probe.new_association_period()
                database.save_changes()
        elif action == 'push_config':
            # Only run one instance of Ansible at a time (for each user)
            if ansible.get_playbook_status(current_user.username) != 'running':
                # Export the script configs in the sql database to ansible readable configs
                user = database.get_user(current_user.username)
                for probe in database.session.query(Probe).filter(Probe.user_id == user.id).all():
                    ansible.export_host_config(probe.custom_id,
                                               {'host_script_configs': database.get_script_data(probe)},
                                               'script_configs')
                    ansible.export_host_config(probe.custom_id,
                                               {'networks': database.get_network_config_data(probe)},
                                               'network_configs')
                ansible.export_to_inventory(current_user.username, database)
                ansible.export_known_hosts(database)
                ansible.run_ansible_playbook(current_user.username)
            else:
                flash(settings.INFO_MESSAGE['ansible_already_running'], 'info')

    probes = database.get_all_probes_data(current_user.username)
    return render_template('probes.html', probes=probes)


@app.route('/probe_setup', methods=['GET', 'POST'])
@flask_login.login_required
def probe_setup():
    probe_id = request.args.get('id', '')
    if probe_id == '':
        flash('No probe ID specified')
        abort(404)

    probe_id = util.convert_mac(probe_id, mode='storage')
    probe = database.get_probe(probe_id)

    if probe is None or probe.user.username != current_user.username:
        flash('Unknown probe ID')
        abort(404)

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
        elif action == 'edit_user':
            username = request.form.get('username', '')


    return render_template('user_managment.html', users=database.get_all_user_data())


@app.route('/edit_user', methods=['GET', 'POST'])
@flask_login.login_required
def edit_user():
    if not current_user.admin:
        return abort(403)

    username = request.args.get('username', '')
    if username == '':
        flash('No username specified')
        abort(404)

    user = database.get_user(username)
    if user is None:
        flash('Unknown username')
        abort(404)

    if request.method == 'POST':
        successful = form_parsers.update_user(username)
        if successful:
            database.save_changes()
            flash('Settings successfully saved', 'info')
            return redirect(url_for('user_managment'))
        else:
            database.revert_changes()
            flash(settings.ERROR_MESSAGE['invalid_settings'], 'error')

    user_data = database.get_user_data(username)
    return render_template('edit_user.html',
                           user=user_data)


# The following two views are used as an API for registering a new
# probe, and are not meant to be accessed through a web browser

@app.route('/register_key', methods=['POST'])
def register_key():
    mac = request.form.get('mac', '')
    if not util.is_mac_valid(mac):
        return 'invalid-mac'

    mac = util.convert_mac(mac, mode='storage')
    probe = database.get_probe(mac)

    if probe is None:
        return 'unknown-mac'

    pub_key = request.form.get('pub_key', '')
    host_key = request.form.get('host_key', '')

    if pub_key == '' or not util.is_pub_ssh_key_valid(pub_key):
        return 'invalid-pub-key'

    if host_key == '' or not util.is_ssh_host_key_valid(host_key):
        return 'invalid-host-key'

    if probe.pub_key != '' or probe.host_key != '':
        return 'already-registered'

    if probe.association_period_expired():
        return 'association-period-expired'

    probe.set_pub_key(pub_key)
    probe.set_host_key(host_key)
    probe.associated = True

    database.save_changes()
    ansible.export_known_hosts(database)

    return 'success'


@app.route('/get_port', methods=['GET'])
def get_port():
    mac = request.args.get('mac', '')
    if not util.is_mac_valid(mac):
        return 'invalid-mac'

    mac = util.convert_mac(mac, mode='storage')
    probe = database.get_probe(mac)

    if probe is None:
        return 'unknown-mac'

    if probe.pub_key == '' or probe.host_key == '':
        return 'no-registered-key'

    return str(probe.port)


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
