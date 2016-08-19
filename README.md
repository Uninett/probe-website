Clone project:
```
git clone --recursive git@scm.uninett.no:maalepaaler/probe-website.git
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
