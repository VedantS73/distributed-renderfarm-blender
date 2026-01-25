from .device import api as device_api
from .election import api as election_api
from .jobs import api as jobs_api
from .worker import api as worker_api

def register_blueprints(app):
    app.register_blueprint(device_api, url_prefix="/api")
    app.register_blueprint(election_api, url_prefix="/api")
    app.register_blueprint(jobs_api, url_prefix="/api")
    app.register_blueprint(worker_api, url_prefix="/api")
