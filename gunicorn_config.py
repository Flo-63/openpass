# User and group settings for process execution

# user = "www-data"  # User that runs Gunicorn processes
# group = "www-data" # Group for the Gunicorn processes

user = "app"  # User that runs Gunicorn processes on Apache
group = "app" # Group for the Gunicorn processes  on Apache

# Network binding configuration
bind = "0.0.0.0:5001"  # Listen on all interfaces on port 5001
# bind = "unix:/run/gunicorn/rcb-ausweis.sock" # Listen on unix domain socket for reverse proxy via Apache

# Application loading
preload_app = True  # Load application code before forking workers

# Request handling configuration
timeout = 300  # Request timeout in seconds
workers = 1    # Number of worker processes (reduced to 1 for async operation)

# Worker class configuration
#worker_class = "gevent"  # Async worker (commented out)
worker_class = "sync"     # Synchronous worker currently in use

# Logging configuration
errorlog = "/var/log/rcb-ausweis/gunicorn.log"  # Error log file location
log_level = "warning"                           # Logging verbosity level