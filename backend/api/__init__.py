from .device import api as device_api
# from .discovery import api as discovery_api
from .election import api as election_api
from .jobs import api as jobs_api
# from .leader import api as leader_api

def register_blueprints(app):
    app.register_blueprint(device_api, url_prefix="/api")
    # app.register_blueprint(discovery_api, url_prefix="/api")
    app.register_blueprint(election_api, url_prefix="/api")
    app.register_blueprint(jobs_api, url_prefix="/api")
    # app.register_blueprint(leader_api, url_prefix="/api")
