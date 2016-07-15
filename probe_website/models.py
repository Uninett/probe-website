from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from probe_website.database import Base
from flask_login import UserMixin


class User(Base, UserMixin):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(256))
    password = Column(String(256))
    contact_person = Column(String(256))
    contact_email = Column(String(256))
    admin = Column(Boolean)

    def __init__(self, username, password, contact_person, contact_email, admin=False):
        self.username = username
        self.password = password
        self.contact_person = contact_person
        self.contact_email = contact_email
        self.admin = admin

    # This is a method override from UserMixin
    def get_id(self):
        return self.username


class Probe(Base):
    __tablename__ = 'probes'
    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    custom_id = Column(String(256))
    location = Column(String(256))

    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', back_populates='probes')

    def __init__(self, name=None, custom_id=None, location=None):
        self.name = name
        self.custom_id = custom_id
        self.location = location

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
                    self.name, self.ssid, self.anonymousd_id, self.username))

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
