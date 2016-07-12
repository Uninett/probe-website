from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from probe_website.database import Base


class Probe(Base):
    __tablename__ = 'probes'
    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    custom_id = Column(String(256))
    location = Column(String(256))
    contact_person = Column(String(256))
    contact_email = Column(String(256))

    def __init__(self, name=None, custom_id=None, location=None,
                 contact_person=None, contact_email=None):
        self.name = name
        self.custom_id = custom_id
        self.location = location
        self.contact_person = contact_person
        self.contact_email = contact_email

    def __repr__(self):
        return 'id={},name={},custom_id={},location={},contact_person={},contact_email={}'.format(
                self.id, self.name, self.custom_id, self.location, self.contact_person, self.contact_email)

    def add_script(self, script):
        self.scripts.append(script)


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

# class Database(Base):
#     _tablename__ = 'databases'
#     id = Column(Integer, primary_key=True)
#     description = Column(String(256))
#     name = Column(String(256))
#     address = Column(String(256))
#     username = Column(String(256))
#     password = Column(String(256))

#     probe_id = Column(Integer, ForeignKey('probes.id'))
#     probe = relationship('Probe', back_populates='scripts')
