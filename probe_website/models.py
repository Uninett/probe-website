from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from probe_website.database import Base
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from time import time
from probe_website.settings import PROBE_ASSOCIATION_PERIOD

# All classes in this module inherits from a SQL Alchemy class,
# and defines how to database tables should look. They also function
# as "normal" classes, so they are not used solely for SQL Alchemy


class User(Base, UserMixin):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(256))
    pw_hash = Column(String(256))
    contact_person = Column(String(256))
    contact_email = Column(String(256))
    admin = Column(Boolean)

    def __init__(self, username, password, contact_person, contact_email, admin=False):
        self.username = username
        self.contact_person = contact_person
        self.contact_email = contact_email
        self.admin = admin

        self.set_password(password)

    def set_password(self, password):
        self.pw_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.pw_hash, password)

    # This is a method override from UserMixin
    def get_id(self):
        return self.username


class Probe(Base):
    __tablename__ = 'probes'
    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    custom_id = Column(String(256))
    location = Column(String(256))
    port = Column(Integer)
    pub_key = Column(String(1024))
    host_key = Column(String(1024))

    association_period_start = Column(Integer)
    associated = Column(Boolean)

    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', back_populates='probes')

    def __init__(self, name=None, custom_id=None, location=None, port=None):
        self.name = name
        self.custom_id = custom_id
        self.location = location
        self.port = port
        self.set_pub_key('')
        self.set_host_key('')
        self.activated = False
        self.new_association_period()

    def set_pub_key(self, key):
        self.pub_key = key

    def set_host_key(self, key):
        self.host_key = key

    def new_association_period(self):
        self.association_period_start = int(time())

    def association_period_expired(self):
        # period_duration = 60*60  # One hour
        return time() - self.association_period_start > PROBE_ASSOCIATION_PERIOD

    def __repr__(self):
        return 'id={},name={},custom_id={},location={}'.format(
                self.id, self.name, self.custom_id, self.location)


class Script(Base):
    __tablename__ = 'scripts'
    id = Column(Integer, primary_key=True)
    description = Column(String(256))
    filename = Column(String(256))
    args = Column(String(256))
    minute_interval = Column(Integer)
    enabled = Column(Boolean)
    required = Column(Boolean)

    probe_id = Column(Integer, ForeignKey('probes.id'))
    probe = relationship('Probe', back_populates='scripts')

    def __init__(self, description, filename, args, minute_interval, enabled, required=False):
        self.description = description
        self.filename = filename
        self.args = args
        self.minute_interval = minute_interval
        self.enabled = enabled
        self.required = required

    def __repr__(self):
        return ('id={},description={},filename={},args={},minute_interval={},enabled={},required={},'
                'probe_id={}'.format(self.id, self.description, self.filename, self.args,
                                     self.minute_interval, self.enabled, self.required, self.probe_id))

class NetworkConfig(Base):
    __tablename__ = 'network_configs'
    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    ssid = Column(String(64))
    anonymous_id = Column(String(256))
    username = Column(String(256))
    password = Column(String(256))

    probe_id = Column(Integer, ForeignKey('probes.id'))
    probe = relationship('Probe', back_populates='network_configs')

    def __init__(self, name, ssid, anonymous_id, username, password):
        self.name = name
        self.ssid = ssid
        self.anonymous_id = anonymous_id
        self.username = username
        self.password = password

    def __repr__(self):
        return ('id={},name={},ssid={},anonymous_id={},username={}'.format(self.id,
                    self.name, self.ssid, self.anonymous_id, self.username))

    def is_filled(self):
        def filled(x):
            return x is not None and x != ''
        return (filled(self.name) and
                filled(self.ssid) and
                filled(self.anonymous_id) and
                filled(self.username) and
                filled(self.password))

class Database(Base):
    __tablename__ = 'databases'
    id = Column(Integer, primary_key=True)
    db_name = Column(String(256))
    db_type = Column(String(256))
    address = Column(String(256))
    port = Column(String(6))
    username = Column(String(256))
    password = Column(String(256))

    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', back_populates='databases')

    def __init__(self, db_name, db_type, address, port, username, password):
        self.db_name = db_name
        self.db_type = db_type
        self.address = address
        self.port = port
        self.username = username
        self.password = password

    def is_filled(self):
        def filled(x):
            return x is not None and x != ''
        return (filled(self.db_name) and
                filled(self.db_type) and
                filled(self.address) and
                filled(self.port) and
                filled(self.username) and
                filled(self.password))
