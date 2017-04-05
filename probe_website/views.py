from probe_website import app
from flask import render_template, request, abort, redirect, url_for, flash
import probe_website.database
from probe_website.database import User, Probe
from probe_website import settings, form_parsers, util, messages, secret_settings
from probe_website import ansible_interface as ansible
from probe_website.oauth import DataportenSignin
import flask_login
from flask_login import current_user
from collections import OrderedDict
from datetime import datetime
import random

database = probe_website.database.DatabaseManager(settings.DATABASE_URL)
form_parsers.set_database(database)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def user_loader(username):
    """Return the User class instance with the username 'username'."""
    try:
        user = database.session.query(User).filter(User.username == username).first()
    except:
        user = None
    return user


@app.teardown_appcontext
def shutdown_database_session(exception=None):
    """Close the database on application shutdown."""
    database.shutdown_session()


@app.route('/')
def index():
    """Render home page if the user is authenticated.
    Otherwise redirect to login page."""
    if flask_login.current_user.is_authenticated:
        return render_template('index.html')
    else:
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Render login page for GET requests. Authenticate and redirect to homepage
    for POST requests (if authentication was successful)."""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        user = user_loader(username)

        if user is not None and user.check_password(password):
            flask_login.login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid login', 'error')

    feide_enabled = secret_settings.OAUTH_CREDENTIALS['id'] != 'ClientID'
    return render_template('login.html', feide_enabled=feide_enabled)


@app.route('/__oauth/authorize')
def oauth_authorize():
    if flask_login.current_user.is_authenticated:
        return redirect(url_for('index'))
    oauth = DataportenSignin()
    return oauth.authorize()


@app.route('/__oauth/callback')
def oauth_callback():
    if flask_login.current_user.is_authenticated:
        return redirect(url_for('index'))
    oauth = DataportenSignin()
    userinfo = oauth.callback()

    if userinfo is None:
        flash('Authentication failed', 'error')
        return redirect(url_for('index'))

    feide_id = userinfo['userid_sec'][0].replace('feide:', '')
    user = database.session.query(User).filter(User.oauth_id == feide_id).first()
    if user is None:
        rand_pass = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for i in range(64))
        database.add_user(feide_id, rand_pass, userinfo['name'], userinfo['email'], False, feide_id)
        database.save_changes()
        user = database.session.query(User).filter(User.oauth_id == feide_id).first()
    flask_login.login_user(user, True)
    return redirect(url_for('index'))


@app.route('/logout')
@flask_login.login_required
def logout():
    """Log current user out and redirect to login page."""
    flask_login.logout_user()
    return redirect(url_for('login'))


@app.route('/instructions', methods=['GET'])
@flask_login.login_required
def instructions():
    """Render instructions page."""
    return render_template('instructions.html')


@app.route('/download_image', methods=['GET'])
@flask_login.login_required
def download_image():
    """Render download image page."""
    return render_template('download_image.html')


@app.route('/databases', methods=['GET', 'POST'])
@flask_login.login_required
def databases():
    """Render database page for GET. Also parse args and export Ansible
    config for POST."""
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
            flash(messages.ERROR_MESSAGE['invalid_settings'], 'error')

    db_info = database.get_database_info(current_user.username)

    # Make sure the databases occur in the same order each time
    db_info = OrderedDict(sorted(db_info.items(), key=lambda x: x[0]))

    return render_template('databases.html',
                           dbs=db_info)


@app.route('/probes', methods=['GET', 'POST'])
@flask_login.login_required
def probes():
    """Render page for viewing all the user's probes. On POST: add,
    update or remove a probe.

    More specifically, the following can be done via POST:
        - Add a new probe
        - Remove a probe
        - Reboot a probe
        - Renew a probe's association period (if not already associated)
        - Push configurations to probes (i.e. run Ansible)
    """
    user = database.get_user(current_user.username)
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'new_probe':
            form_parsers.new_probe(current_user.username)
        elif action == 'reboot_probe':
            probe_id = request.form.get('probe_id', '')
            probe = database.get_probe(probe_id)
            if probe is not None and probe.user.username == current_user.username and probe.associated:
                success = util.reboot_probe(probe.port)
                if not success:
                    flash('Unable to reboot probe (possibly no connection)')
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
            if not ansible.is_ansible_running(current_user.username):
                # Export configs in the sql database to ansible readable configs
                for probe in database.session.query(Probe).filter(Probe.user_id == user.id).all():
                    # Export script config
                    data = util.strip_id(database.get_script_data(probe))
                    ansible.export_host_config(probe.custom_id,
                                               {'host_script_configs': data},
                                               'script_configs')
                    # Export probe info config
                    ansible.export_host_config(probe.custom_id,
                                               {'probe_name': probe.name,
                                                'probe_location': probe.location,
                                                'probe_mac': probe.custom_id,
                                                'probe_organization': user.get_organization()},
                                               'probe_info')

                    if (probe.associated and
                            util.is_probe_connected(probe.port) and
                            database.valid_network_configs(probe, with_warning=True) and
                            database.valid_database_configs(user, with_warning=True)):
                        data = util.strip_id(database.get_network_config_data(probe))
                        ansible.export_host_config(probe.custom_id,
                                               {'networks': data},
                                               'network_configs')
                ansible.export_to_inventory(current_user.username, database)
                ansible.export_known_hosts(database)
                ansible.run_ansible_playbook(current_user.username)
            else:
                flash(messages.INFO_MESSAGE['ansible_already_running'], 'info')

        # Redirect to avoid re-POSTing
        return redirect(url_for('probes'))

    probes = database.get_all_probes_data(current_user.username)
    return render_template('probes.html',
                           probes=probes,
                           kibana_dashboard='probe-stats',
                           organization=user.get_organization())


@app.route('/probe_setup', methods=['GET', 'POST'])
@flask_login.login_required
def probe_setup():
    """Render page for adding/editing probe data. Also parse data
    on POST.

    More specifically, the data that can be changed are:
        - Basic probe info (name, MAC and location)
        - Script configurations (interval and enabled/disabled for each script)
        - Network configration (SSID, anon id, username, password, cert)
    """
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
    """Render page for adding, editing or removing users on GET. Also parse input
    on POST.

    This page can only be accessed by an admin.
    """
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
    """Render page for editing user information.

    This page can only be accessed by an admin
    """
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
            flash(messages.ERROR_MESSAGE['invalid_settings'], 'error')

    user_data = database.get_user_data(username)
    return render_template('edit_user.html',
                           user=user_data)


# The following two views are used as an API for registering a new
# probe, and are not meant to be accessed through a web browser

@app.route('/register_key', methods=['POST'])
def register_key():
    """Takes an SSH public key, host key and a MAC, and registers
    it to the corresponding probe if a probe with that MAC has been added
    through the website.

    The function can give the following responses (with explanation):
        invalid-mac                 : The supplied MAC was invalid (in form)
        unknown-mac                 : The MAC was valid, but is not in the database
        invalid-pub-key             : The pub key was invalid (in form)
        invalid-host-key            : The host key was invalid (in form)
        already-registered          : There already exists keys associated with this MAC
        assocation-period-expired   : The assocation period has expired and needs
                                      to be renewed through the web site
        success                     : The keys were successfully registered/associated
                                      with the corresponding MAC address
    """
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
    """Returns the port number associated with the supplied MAC.

    The port will be used to construct a SSH tunnel

    The function can give the following responses (with explanation):
        invalid-mac       : The supplied MAC was invalid (in format)
        unknown-mac       : The MAC was valid, but is not in the database
        no-registered-key : No SSH key has been associated with this MAC,
                            and therefore no port will be sent
        <port>            : Returns the queried port (a valid MAC was received)
    """
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


@app.route('/get_connection_status', methods=['GET'])
@flask_login.login_required
def get_connection_status():
    """Return the eth & wlan connection status of the specified probe,

    The only argument is mac, which should be the probe's MAC address
    Returned statuses will be either:
        invalid-mac
        unknown-mac
        {"eth0": 0 or 1, "wlan0": 1 or 0}

        For backwards compatibility:
        connected
    """
    mac = request.args.get('mac', '')
    if mac == '':
        return 'invalid-mac'

    mac = util.convert_mac(mac, 'storage')
    probe = database.get_probe(mac)
    if probe is None:
        return 'unknown-mac'

    status = util.is_probe_connected(probe.port)
    if status:
        con_stat = util.get_interface_connection_status(probe.port)
        if con_stat is not None:
            return con_stat
        else:
            return 'connected'

    return '{"eth0": 0, "wlan0": 0}'


@app.route('/get_ansible_status', methods=['GET'])
@flask_login.login_required
def get_ansible_status():
    """Return the status on the current ansible update

    The only argument is mac, which should be the probe's MAC address
    Returned statuses will be either:
        invalid-mac
        unknown-mac
        updating
        failed
        not-updated
        updated-{time of last update}
    """
    mac = request.args.get('mac', '')
    if mac == '':
        return 'invalid-mac'

    mac = util.convert_mac(mac, 'storage')
    probe = database.get_probe(mac)
    if probe is None:
        return 'unknown-mac'

    status = ansible.get_playbook_status(current_user.username, probe)
    if status in ['updating', 'failed']:
        return status

    if status == 'completed':
        probe.has_been_updated = True
        if (probe.last_updated is None or
                (datetime.today() - probe.last_updated).total_seconds() >= 60):
            probe.last_updated = datetime.today()
            database.save_changes()

    if status == 'completed' or probe.has_been_updated:
        if probe.last_updated is None:
            probe.last_updated = datetime.today()
            database.save_changes()
        time = util.get_textual_timedelta(datetime.today() - probe.last_updated)
        return 'updated-{}'.format(time)

    return 'not-updated'


#################################################################
#                                                               #
#  Everything below should probably be moved to its own module  #
#                                                               #
#################################################################


def generate_probe_setup_template(probe_id, username):
    """Generate a probe setup page and return it."""
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
