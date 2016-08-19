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

For documentation, see the document DOCUMENTATION.md. To export the markdown file to a nice and fancy PDF file, install pandoc and run the following command:
```
pandoc --number-sections --toc -o documentation.pdf -f markdown DOCUMENTATION.md
```
(There is a PDF version in redmine too.)
