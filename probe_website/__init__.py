from flask import Flask
from probe_website import settings

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = settings.CERTIFICATE_DIR
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024  # 64 KiB

import probe_website.views
