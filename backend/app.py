import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from backend.routes.api_routes import api

def create_app():
    app = Flask(__name__, static_folder="../client/dist", static_url_path="")
    CORS(app)

    # Register API routes
    app.register_blueprint(api)

    # Frontend routes
    @app.route("/")
    def serve_root():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        file_path = os.path.join(app.static_folder, path)
        if os.path.exists(file_path):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, "index.html")

    return app
