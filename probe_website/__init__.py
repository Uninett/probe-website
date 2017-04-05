from flask import Flask
from probe_website import settings
from probe_website import secret_settings

#  __        ___ _____ _                   _
#  \ \      / (_)  ___(_)  _ __  _ __ ___ | |__   ___  ___
#   \ \ /\ / /| | |_  | | | '_ \| '__/ _ \| '_ \ / _ \/ __|
#    \ V  V / | |  _| | | | |_) | | | (_) | |_) |  __/\__ \
#     \_/\_/  |_|_|   |_| | .__/|_|  \___/|_.__/ \___||___/
#                         |_|

app = Flask(__name__)

app.secret_key = secret_settings.SECRET_KEY

app.config['UPLOAD_FOLDER'] = settings.CERTIFICATE_DIR
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024  # 64 KiB

import probe_website.views
