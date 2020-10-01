Clone project: An awesome project
```
git clone --recursive https://github.com/UNINETT/probe-website.git
```

In the probe_website directory, do
```
cp settings.py.example settings.py
cp secret_settings.py.example secret_settings.py
```
and change the config values in both files.

Build the initial database
```
sqlite3 database.db < database.sqlite.sql
```

Execute various setup tasks (this will only make the server ready as a local dev server, i.e. can be run directly with Flask. For apache/nginx, further manual configuration is necessary):
```
cd probe-website
bash setup_server.sh
```

To run a dev server:
```
export FLASK_APP=runserver.py
flask run
```

For documentation, see: http://wifiprobe-doc.paas.uninett.no/
