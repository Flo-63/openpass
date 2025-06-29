# wsgi.py
from werkzeug.middleware.proxy_fix import ProxyFix

# Local/Application
from app import create_app

app = create_app()
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)