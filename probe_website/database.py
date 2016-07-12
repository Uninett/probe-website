from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from re import fullmatch
from probe_website import util, settings
from probe_website import ansible_interface as ansible

# The models module depends on this, so that's why it's global
Base = declarative_base()

# This must be imported AFTER Base has been instantiated!
from probe_website.models import Probe, Script, NetworkConfig


class Database():
    def __init__(self, database_path):
        self.engine = create_engine('sqlite:///' + database_path, convert_unicode=True)
        self.session = scoped_session(sessionmaker(autocommit=False,
                                                   autoflush=False,
                                                   bind=self.engine))

        global Base
        Base.query = self.session.query_property()

        Probe.scripts = relationship('Script',
                                     order_by=Script.id,
                                     back_populates='probe',
                                     cascade='all, delete, delete-orphan')

        Probe.network_configs = relationship('NetworkConfig',
                                             order_by=NetworkConfig.id,
                                             back_populates='probe',
                                             cascade='all, delete, delete-orphan')

        Base.metadata.create_all(self.engine)

    def shutdown_session(self):
        self.session.remove()

    def add_probe(self, username, probe_name, custom_id, location=None, contact_person=None, contact_email=None, scripts=None, network_configs=None):
        ''' 
        Creates a probe instance, adds it to the database session, and returns
        it to the caller
        '''

        if not self.is_valid_id(custom_id):
            return None

        probe = Probe(probe_name, util.convert_mac(custom_id, mode='storage'),
                      location, contact_person, contact_email)
        self.session.add(probe)

        if scripts is None:
            self.load_default_scripts(probe, username)

        if network_configs is None:
            self.load_default_network_configs(probe, username)

        return probe

    def add_script(self, probe, description, filename, args, minute_interval, enabled, required):
        script = Script(description, filename, args, minute_interval, enabled, required)
        probe.scripts.append(script)

    def add_network_config(self, probe, name, ssid, anonymous_id, username, password):
        config = NetworkConfig(name, ssid, anonymous_id, username, password)
        probe.network_configs.append(config)

    def load_default_scripts(self, probe, username):
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
        configs = ansible.load_default_config(username, 'network_configs')

        print(configs)
        # for name in ['any', 'two_g', 'five_g']:
        #     if 'network' in configs and name in configs['network']:
        #         self.add_network_config(probe, name,
        #                                 configs['network'][name]['ssid'],
        #                                 configs['network'][name]['anonymous_id'],
        #                                 configs['network'][name]['username'],
        #                                 configs['network'][name]['password'])
        #     else:
        #         self.add_network_config(probe, name, '', '', '', '')

        if 'group_network_configs' in configs:
            for config in configs['group_network_configs']:
                self.add_network_config(probe, config['name'], config['ssid'],
                                        config['anonymous_id'], config['username'], config['password'])
        else:
            self.add_network_config(probe, 'two_g', '', '', '', '')
            self.add_network_config(probe, 'five_g', '', '', '', '')
            self.add_network_config(probe, 'any', '', '', '', '')

    def is_valid_id(self, probe_id):
        if not self.is_valid_string(probe_id):
            return False
        if not util.is_mac_valid(probe_id):
            return False

        probe_id = util.convert_mac(probe_id, mode='storage')
        is_unused = len(self.session.query(Probe.custom_id).filter(Probe.custom_id == probe_id).all()) == 0

        return is_unused

    def is_valid_string(self, entry):
        return type(entry) is str and entry != ''

    def update_probe(self, current_probe_id, name=None, new_custom_id=None, location=None,
                     contact_person=None, contact_email=None):
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
        if self.is_valid_string(contact_person):
            probe.contact_person = contact_person
        if self.is_valid_string(contact_email):
            probe.contact_email = contact_email

        return True

    def update_script(self, probe, script_id, name=None, script_file=None,
                      args=None, minute_interval=None, enabled=None):
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

    # This method should only return probes associated with the specified
    # username, but atm support for different users aren't implemented, so
    # just return everything

    # This method also just returns the basic info, not info about each
    # probe's script configs etc.
    def get_all_probes_data(self, username):
        all_data = []
        for probe in self.session.query(Probe).all():
            data_entry = self.get_probe_data(probe.custom_id)

            # We only want the basic data
            data_entry.pop('scripts')
            data_entry.pop('network_configs')
            all_data.append(data_entry)

        return all_data


    def get_probe_data(self, probe_id):
        probe = self.get_probe(probe_id)
        data = {
                'name': probe.name,
                'id': util.convert_mac(probe.custom_id, mode='display'),
                'location': probe.location,
                'contact_person': probe.contact_person,
                'contact_email': probe.contact_email,
                'scripts': self.get_script_data(probe),
                'network_configs': self.get_network_config_data(probe)
        }
        return data

    def get_script_data(self, probe):
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
        configs = []
        for config in probe.network_configs:
            data_entry = {
                    'name': config.name,
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
                    'any': "Any (will use both 2.4 GHz and 5 GHz)"
            }
            if data_entry['name'] in descriptions:
                data_entry['description'] = descriptions[data_entry['name']]

            configs.append(data_entry)
        return configs

    def get_probe(self, probe_id):
        probe_id = util.convert_mac(probe_id, mode='storage')
        return self.session.query(Probe).filter(Probe.custom_id == probe_id).first()

    def get_script(self, probe, script_id):
        return self.session.query(Script).filter(Script.id == script_id).first()

    def get_network_config(self, probe, config_id):
        return self.session.query(NetworkConfig).filter(NetworkConfig.id == config_id).first()

    def remove_probe(self, probe_custom_id):
        probe = self.get_probe(probe_custom_id)
        if probe is not None:
            self.session.delete(probe)

    # def remove_script(self, probe, script_filename):
    #     script = self.session.query.filter(Probe.scripts.

    def save_changes(self):
        self.session.commit()

    def revert_changes(self):
        self.session.rollback()

    def __repr__(self):
        string = ''
        for probe in self.session.query(Probe).order_by(Probe.id):
            string += str(probe) + '\n'
        return string
