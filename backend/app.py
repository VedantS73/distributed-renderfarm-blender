import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from backend.routes.api_routes import api
from backend.routes.jobs import jobs_api

def create_app():
    app = Flask(__name__, static_folder="../client/dist", static_url_path="")
    CORS(app)

    # Register API routes
    app.register_blueprint(api)
    app.register_blueprint(jobs_api)

    @app.errorhandler(404)
    def not_found(e):
        # This catches any route that isn't an API or a real static file
        return send_from_directory(app.static_folder, "index.html")

    # Frontend routes
    @app.route("/")
    def serve_root():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        # Don't serve API routes from static handler
        if path.startswith("api/"):
            return "Not Found", 404
        
        file_path = os.path.join(app.static_folder, path)
        
        # If the file exists, serve it
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_from_directory(app.static_folder, path)
        
        # Otherwise, serve index.html for all other routes
        return send_from_directory(app.static_folder, "index.html")

    return app
