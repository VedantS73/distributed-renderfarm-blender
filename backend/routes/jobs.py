from flask import Blueprint, jsonify, request
import uuid
import datetime
from backend.services.blender_service import BlenderService

jobs_api = Blueprint("jobs_api", __name__, url_prefix="/api/jobs")

blender = BlenderService()

@jobs_api.route("/analyze", methods=["POST"])
def create_job():
    job_id = str(uuid.uuid4())
    
    file = request.data
    if not file:
        return jsonify({"error": "No file provided"}), 400
    
    # Extract blend file from request
    blend_file_path = f"/tmp/{job_id}.blend"
    with open(blend_file_path, "wb") as f:
        f.write(file)
    
    # analysis_result = blender.analyze(blend_file_path)

    analysis_result = {
        "renderer": "Cycles",
        "frame_start": 1,
        "frame_end": 250,
        "fps": 24,
    }

    return jsonify(analysis_result), 201

