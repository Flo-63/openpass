"""
===============================================================================
Project   : openpass
Module    : gunicorn_config.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This is to configure Gunicorn for the openpass application.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

import os


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

# Number of worker processes. With a single sync worker any expensive or blocking
# request - a large image upload, a stalled SMTP connection - takes the whole
# application offline for its duration. Rate limits and the single-use markers for
# login links live in Redis, so they are shared correctly across workers. Override
# with GUNICORN_WORKERS if the host is memory constrained.
workers = int(os.getenv("GUNICORN_WORKERS", 2))

# Worker class configuration
#worker_class = "gevent"  # Async worker (commented out)
worker_class = "sync"     # Synchronous worker currently in use

# Logging configuration
errorlog = "/var/log/rcb-ausweis/gunicorn.log"  # Error log file location
log_level = "warning"                           # Logging verbosity level