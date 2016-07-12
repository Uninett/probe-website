from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from re import fullmatch
from probe_website import util, settings
from probe_website import ansible_interface as ansible

# The models module depends on this, so that's why it's global
Base = declarative_base()

# This must be imported AFTER Base has been instantiated!
from probe_website.models import Probe, Script


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

        Base.metadata.create_all(self.engine)

    def shutdown_session(self):
        self.session.remove()

    def add_probe(self, username, probe_name, custom_id, location=None, contact_person=None, contact_email=None, scripts=None):
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

        return probe

    def add_script(self, probe, description, filename, args, minute_interval, enabled, required):
        script = Script(description, filename, args, minute_interval, enabled, required)
        probe.scripts.append(script)

    def load_default_scripts(self, probe, username):
        for script in ansible.load_default_script_configs(username):
            required = False
            if 'required' in script:
                required = script['required']
                # required implies enabled
                if required:
                    script['enabled'] = True

            self.add_script(probe, script['name'], script['script_file'],
                            script['args'], script['minute_interval'],
                            script['enabled'], required)

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

    # This method should only return probes associated with the specified
    # username, but atm support for different users aren't implemented, so
    # just return everything

    # This method also just returns the basic info, not info about each
    # probe's script configs etc.
    def get_all_probes_data(self, username):
        all_data = []
        for probe in self.session.query(Probe).all():
            data_entry = self.get_probe_data(probe.custom_id)

            # We don't need the script data for each probe
            data_entry.pop('scripts')
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
                'scripts': self.get_script_data(probe)
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

    def get_probe(self, probe_id):
        probe_id = util.convert_mac(probe_id, mode='storage')
        return self.session.query(Probe).filter(Probe.custom_id == probe_id).first()

    def get_script(self, probe, script_id):
        return self.session.query(Script).filter(Script.id == script_id).first()

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
