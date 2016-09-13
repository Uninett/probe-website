from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from re import fullmatch
from probe_website import util, settings
from probe_website import ansible_interface as ansible
from flask import flash

# The models module depend on this, so that's why it's global
Base = declarative_base()

# This must be imported AFTER Base has been instantiated!
from probe_website.models import Probe, Script, NetworkConfig, Database, User


class DatabaseManager():
    """Class managing pretty much all queries to the SQL database"""
    def __init__(self, database_url):
        """Set up SQL Alchemy with the database at 'database_path'

        database_url can be e.g. 'sqlite:////home/bob/database.db'
        """
        self.engine = create_engine(database_url, convert_unicode=True)
        self.session = scoped_session(sessionmaker(autocommit=False,
                                                   autoflush=False,
                                                   bind=self.engine))

        global Base
        Base.query = self.session.query_property()

        self.setup_relationships()

        Base.metadata.create_all(self.engine)

        if len(self.session.query(User).all()) == 0:
            self.add_user('admin', 'admin', 'admin', 'admin', True)

    def setup_relationships(self):
        """Set up the relations between the different SQL tables"""
        Probe.scripts = relationship('Script',
                                     order_by=Script.id,
                                     back_populates='probe',
                                     cascade='all, delete, delete-orphan')

        Probe.network_configs = relationship('NetworkConfig',
                                             order_by=NetworkConfig.id,
                                             back_populates='probe',
                                             cascade='all, delete, delete-orphan')

        User.probes = relationship('Probe',
                                   order_by=Probe.id,
                                   back_populates='user',
                                   cascade='all, delete, delete-orphan')

        User.databases = relationship('Database',
                                      order_by=Database.id,
                                      back_populates='user',
                                      cascade='all, delete, delete-orphan')

    def shutdown_session(self):
        """Close the database"""
        self.session.remove()

    def add_user(self, username, password, contact_person, contact_email, admin=False):
        """Add a new user to the database"""
        if len(self.session.query(User).filter(User.username == username).all()) != 0:
            return False

        user = User(username, password, contact_person, contact_email, admin)
        self.session.add(user)
        self.add_default_databases(user)
        self.save_changes()
        return True

    def add_probe(self, username, probe_name, custom_id, location=None, scripts=None, network_configs=None):
        """Create a probe instance, add it to the database session, and return
        it to the caller"""
        if not self.is_valid_id(custom_id):
            return None

        port = self.generate_probe_port()
        if port == -1:
            print('Error generating port number. The port space may be '
                  'exhausted (though that is unlikely)')
            return None

        probe = Probe(probe_name, util.convert_mac(custom_id, mode='storage'),
                      location, port)
        user = self.get_user(username)
        user.probes.append(probe)

        if scripts is None:
            self.load_default_scripts(probe, username)

        if network_configs is None:
            self.load_default_network_configs(probe, username)

        return probe

    def add_script(self, probe, description, filename, args, minute_interval, enabled, required):
        """Add a new script"""
        script = Script(description, filename, args, minute_interval, enabled, required)
        probe.scripts.append(script)

    def add_network_config(self, probe, name, ssid, anonymous_id, username, password):
        """Add a new network config"""
        config = NetworkConfig(name, ssid, anonymous_id, username, password)
        probe.network_configs.append(config)

    def add_database(self, user, db_type, name, address, port, username, password):
        """Add a new database for 'user' (NB: This is NOT a SQL database, but rather the
        credentials for the database the probe will send data to (like InfluxDB))"""
        # Need to take user into account here
        db = Database(name, db_type, address, port, username, password)
        user.databases.append(db)

    def add_default_databases(self, user):
        """Add InfluxDB as a a default database for 'user'"""
        self.add_database(user, 'influxdb', '', '', '', '', '')

    def load_default_scripts(self, probe, username):
        """Load default scripts for probe from Ansible configs. The default
        scripts will either be the defaults for 'username' if any defaults
        have been set, or the global defaults if no such defaults exist"""
        configs = ansible.load_default_config(username, 'script_configs')

        if 'default_script_configs' in configs:
            configs = configs['default_script_configs']
        elif 'group_script_configs' in configs:
            configs = configs['group_script_configs']
        else:
            print('Error reading default script config file')
            return

        for script in configs:
            required = False
            if 'required' in script:
                required = script['required']
                # required implies enabled
                if required:
                    script['enabled'] = True

            self.add_script(probe, script['name'], script['script_file'],
                            script['args'], script['minute_interval'],
                            script['enabled'], required)

    def load_default_network_configs(self, probe, username):
        """Load default network configs for probe. If defaults for 'username'
        exists, they will be used. Otherwise, add empty entries for any,
        2.4GHz & 5GHz"""
        configs = ansible.load_default_config(username, 'network_configs')
        ansible.load_default_certificate(username, probe.custom_id)

        if 'networks' in configs:
            for freq, config in configs['networks'].items():
                self.add_network_config(probe, freq, config['ssid'],
                                        config['anonymous_id'], config['username'], config['password'])
        else:
            self.add_network_config(probe, 'two_g', '', '', '', '')
            self.add_network_config(probe, 'five_g', '', '', '', '')
            self.add_network_config(probe, 'any', '', '', '', '')

    def is_valid_id(self, probe_id):
        """Return true if 'probe_id' is a valid MAC address for use as a
        probe id."""
        if not self.is_valid_string(probe_id):
            return False
        if not util.is_mac_valid(probe_id):
            return False

        probe_id = util.convert_mac(probe_id, mode='storage')
        is_unused = len(self.session.query(Probe.custom_id).filter(Probe.custom_id == probe_id).all()) == 0

        return is_unused

    def is_valid_string(self, entry):
        """Return true if 'entry' is of type str and non-empty"""
        return type(entry) is str and entry != ''

    def update_probe(self, current_probe_id, name=None, new_custom_id=None, location=None):
        """Update 'current_probe_id' with new attributes"""
        probe = self.get_probe(current_probe_id)
        if probe is None:
            return False

        conv_curr = util.convert_mac(current_probe_id, mode='storage')
        conv_new = util.convert_mac(new_custom_id, mode='storage')
        if not conv_curr == conv_new:
            if self.is_valid_id(new_custom_id):
                probe.custom_id = util.convert_mac(new_custom_id, mode='storage')
            else:
                return False

        if self.is_valid_string(name):
            probe.name = name
        if self.is_valid_string(location):
            probe.location = location

        return True

    def update_script(self, probe, script_id, name=None, script_file=None,
                      args=None, minute_interval=None, enabled=None):
        """Update 'probe's 'script_id' with new attributes"""
        if probe is None:
            return False

        script = self.get_script(probe, script_id)
        if script is None:
            return False

        if self.is_valid_string(name):
            script.name = name
        if self.is_valid_string(script_file):
            script.script_file = script_file
        if self.is_valid_string(args):
            script.args = args

        # This whole checking should be redone (both for this method and for update_probe)
        try:
            int(minute_interval)
        except:
            pass
        else:
            script.minute_interval = int(minute_interval)

        try:
            script.enabled = bool(enabled)
        except:
            pass
        else:
            script.enabled = bool(enabled)

        # required implies enabled
        if script.required:
            script.enabled = True

        return True

    def update_network_config(self, probe, config_id, ssid=None,
                              anonymous_id=None, username=None, password=None):
        """Update 'probe's 'config_id' with new attributes"""
        if probe is None:
            return False

        config = self.get_network_config(probe, config_id)
        if config is None:
            return False

        if self.is_valid_string(ssid):
            config.ssid = ssid
        if self.is_valid_string(anonymous_id):
            config.anonymous_id = anonymous_id
        if self.is_valid_string(username):
            config.username = username
        if self.is_valid_string(password):
            config.password = password

        return True

    def update_database(self, user, db_id, db_name=None, address=None, port=None, username=None, password=None):
        """Update 'user's 'db_id' with new attributes"""
        if user is None:
            return False

        db = self.get_database(user, db_id)
        if db is None:
            return False

        if self.is_valid_string(db_name):
            db.db_name = db_name
        if self.is_valid_string(address):
            db.address = address
        if self.is_valid_string(port):
            db.port = port
        if self.is_valid_string(username):
            db.username = username
        if self.is_valid_string(password):
            db.password = password

        return True

    def update_user(self, current_username, new_username=None, password=None,
                    contact_person=None, contact_email=None):
        """Update 'current_username' with new attributes"""
        user = self.get_user(current_username)
        if user is None:
            return False

        if self.is_valid_string(new_username) and ' ' not in new_username:
            user.username = new_username
        if self.is_valid_string(password) and password != '***':
            user.set_password(password)
        if self.is_valid_string(contact_person):
            user.contact_person = contact_person
        if self.is_valid_string(contact_email):
            user.contact_email = contact_email

        return True

    # This method also just returns the basic info, not info about each
    # probe's script configs etc.
    def get_all_probes_data(self, username):
        """Return a list of dictionaries with data about all probes of 'username'.

        The data listed for each probe is the same as the data returned from
        get_probe_data (see function below), with the exception of the script
        and network configs;
        """
        all_data = []
        user = self.get_user(username)

        for probe in self.session.query(Probe).filter(Probe.user_id == user.id).all():
            data_entry = self.get_probe_data(probe.custom_id)

            # We don't need the detailed data
            data_entry.pop('scripts')
            data_entry.pop('network_configs')
            all_data.append(data_entry)

        return all_data

    def get_probe_data(self, probe_id):
        """Return a dictionary containing all saved data about 'probe_id'"""
        probe = self.get_probe(probe_id)
        data = {
                'name': probe.name,
                'id': util.convert_mac(probe.custom_id, mode='display'),
                'storage_id': probe.custom_id,
                'location': probe.location,
                'scripts': self.get_script_data(probe),
                'network_configs': self.get_network_config_data(probe),
                'associated': probe.associated,
                'association_period_expired': probe.association_period_expired(),
        }
        return data

    def get_script_data(self, probe):
        """Return a dictionary containing all script configs of 'probe'"""
        scripts = []
        for script in probe.scripts:
            data_entry = {
                    'name': script.description,
                    'script_file': script.filename,
                    'args': script.args,
                    'minute_interval': script.minute_interval,
                    'enabled': script.enabled,
                    'required': script.required,
                    'id': script.id
            }
            scripts.append(data_entry)
        return scripts

    def get_network_config_data(self, probe):
        configs = {'two_g': '', 'five_g': '', 'any': ''}
        """Return a dictionary containing all network configs of 'probe'"""
        for config in probe.network_configs:
            if config.name in configs:
                configs[config.name] = {
                        'ssid': config.ssid,
                        'anonymous_id': config.anonymous_id,
                        'username': config.username,
                        'password': config.password,
                        'id': config.id,
                        'description': config.name
                }
                descriptions = {
                        'two_g': '2.4 GHz',
                        'five_g': '5 GHz',
                        'any': 'Any (will use both 2.4 GHz and 5 GHz)'
                }
                if config.name in descriptions:
                    configs[config.name]['description'] = descriptions[config.name]

        return configs

    def get_database_info(self, user):
        """Return a dictionary containing all database configs of 'user'"""
        if type(user) is str:
            user = self.get_user(user)
            if user is None:
                print('Invalid username')
                return

        databases = self.session.query(Database).filter(Database.user_id == user.id)

        configs = {db.db_type: '' for db in databases}
        for database in databases:
            configs[database.db_type] = {
                    'db_name': database.db_name,
                    'db_type': database.db_type,
                    'address': database.address,
                    'port': database.port,
                    'username': database.username,
                    'password': database.password,
                    'id': database.id
            }
        return configs

    def get_user_data(self, username):
        """Return a dictionary containing all data about 'username'"""
        user = self.get_user(username)
        data = {
                'username': user.username,
                'password': '***',
                'contact_person': user.contact_person,
                'contact_email': user.contact_email,
                'id': user.id
        }
        return data

    def get_all_user_data(self):
        """Return a list containing data about all users"""
        users = []
        for username, in self.session.query(User.username).all():
            users.append(self.get_user_data(username))
        return users

    def get_user(self, username):
        """Return the User class instance with the username 'username'"""
        return self.session.query(User).filter(User.username == username).first()

    def get_probe(self, probe_id):
        """Return the Probe class instance with the custom_id/MAC 'probe_id'"""
        probe_id = util.convert_mac(probe_id, mode='storage')
        return self.session.query(Probe).filter(Probe.custom_id == probe_id).first()

    def get_script(self, probe, script_id):
        """Return the Script class instance with the id 'probe_id' and relation to 'probe'"""
        return self.session.query(Script).filter(Script.probe_id == probe.id, Script.id == script_id).first()

    def get_network_config(self, probe, config_id):
        """Return the NetworkConfig class instance with the id 'config_id' and relation to 'probe'"""
        return self.session.query(NetworkConfig).filter(NetworkConfig.probe_id == probe.id, NetworkConfig.id == config_id).first()

    def get_database(self, user, db_id):
        """Return the Database class instance with the id 'db_id' and relation to 'user'"""
        return self.session.query(Database).filter(Database.user_id == user.id, Database.id == db_id).first()

    def remove_probe(self, username, probe_custom_id):
        """Remove the probe with id 'probe_custom_id', as long as it belongs
        to 'username'"""
        probe = self.get_probe(probe_custom_id)
        if probe is None or self.get_user(username).id != probe.user_id:
            flash('Invalid probe ID', 'error')
            return False

        probe_id = util.convert_mac(probe_custom_id, mode='storage')
        ansible.remove_host_cert(probe_id)
        if probe is not None:
            self.session.delete(probe)

        return True

    def remove_user(self, username):
        """Remove the user with username 'username', and with it all it's saved
        probes and database configs."""
        user = self.get_user(username)
        if user is None:
            flash('Attempted to remove invalid username', 'error')
            return False

        for probe in self.session.query(Probe).filter(Probe.user_id == user.id).all():
            self.remove_probe(username, probe.custom_id)

        for database in self.session.query(Database).filter(Database.user_id == user.id).all():
            self.session.delete(database)

        self.session.delete(user)

        return True

    def save_changes(self):
        """Save database changes persistently to SQL database"""
        self.session.commit()

    def revert_changes(self):
        """Revert database back to how it was at last save"""
        self.session.rollback()

    def valid_network_configs(self, probe):
        """Returns true if 'probe's network config(s) has been filled out"""
        success = True
        for net_conf in probe.network_configs:
            # For now we just check for any (not two_g & and five_g), because
            # we don't use the two_g and five_g at the moment
            if net_conf.name == 'any' and not net_conf.is_filled():
                message = settings.ERROR_MESSAGE['fill_out_network_credentials'].format(
                    str(probe.name) + ' / ' + util.convert_mac(probe.custom_id, mode='display'))
                flash(message, 'error')
                success = False
        return success

    def valid_database_configs(self, user):
        """Returns true if 'user's database config(s) has been filled out"""
        success = True
        for db_conf in user.databases:
            # For now, just make sure everything is filled out (in the future, with
            # more than one db, maybe check that at least one is filled out)
            if not db_conf.is_filled():
                message = settings.ERROR_MESSAGE['fill_out_database_credentials']
                flash(message, 'error')
                success = False
        return success

    def generate_probe_port(self):
        """Return an available port for SSH tunnel."""
        base_port = 50000
        max_port = 65000

        used_ports = [port for port, in self.session.query(Probe.port).all()]
        i = 0
        while True:
            if base_port + i not in used_ports:
                return base_port + i
            elif base_port + i > max_port:
                return -1
            i += 1
