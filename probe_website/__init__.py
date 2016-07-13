from flask import Flask
from probe_website import settings

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = settings.CERTIFICATE_DIR

import probe_website.views
