# wsgi.py
# Local/Application
from app import create_app

# create_app() already wraps the WSGI app in ProxyFix and honours TRUSTED_PROXY_COUNT
# while doing so. Wrapping it a second time here would be redundant, and the second
# wrapper used to omit x_for, which reads like the bug that collapses every per-IP rate
# limit into one shared counter.
app = create_app()
