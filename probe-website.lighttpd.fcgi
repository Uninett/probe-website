#!/usr/bin/env python3
from flup.server.fcgi import WSGIServer
from probe_website import app
from werkzeug.contrib.fixers import CGIRootFix

if __name__ == '__main__':
    WSGIServer(CGIRootFix(app, app_root='/')).run()
