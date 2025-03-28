# Gunicorn configuration settings.

bind = ":8080"
workers = 2
# Give workers an expiry:
max_requests = 2048
max_requests_jitter = 256
preload_app = True
# Set longer timeout for workers
timeout = 600
# Disable access logging.
accesslog = None
