from flask import Flask
from probe_website import settings
import flask_login

app = Flask(__name__)

# This should probably be changed before being used in production
app.secret_key = b'\xf2z\xf83\xdbU\x12+\xccK\xb7\x0c\xf0\xcf\x1c\x01\xd7\xf1\x9e\xd1\xc3\x18gw\'\x97\xc4\xbb\xd0q\xc1\xf0G-\x13k\xf9I\xf7;`"b\x0fL\xc8\x1c\xe1t\x1bx\xa2\x01*\x1a\xad\x1b\xecpoN\xf1A\xaf'

app.config['UPLOAD_FOLDER'] = settings.CERTIFICATE_DIR
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024  # 64 KiB

import probe_website.views
