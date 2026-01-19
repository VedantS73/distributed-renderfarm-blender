from flask import Blueprint, jsonify, request
import uuid
import datetime
from backend.services.blender_service import BlenderService
from werkzeug.utils import secure_filename

jobs_api = Blueprint("jobs_api", __name__, url_prefix="/api/jobs")

blender = BlenderService()

@jobs_api.route("/analyze", methods=["POST"])
def create_job():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".blend"):
        return jsonify({"error": "Invalid file type"}), 400
    
    job_id = str(uuid.uuid4())

    blend_file_path = f"/tmp/{job_id}.blend"
    file.save(blend_file_path)

    # analysis_result = blender.analyze(blend_file_path)

    analysis_result = {
        "renderer": "Cycles",
        "frame_start": 1,
        "frame_end": 250,
        "fps": 24,
    }

    return jsonify(analysis_result), 201

