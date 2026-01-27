from flask import Blueprint, json, request, jsonify
import tempfile, uuid, os, requests, datetime
from werkzeug.utils import secure_filename
from backend.shared.state import blender, discovery

JOBS_DIR = "jobs"
os.makedirs(JOBS_DIR, exist_ok=True)

api = Blueprint("worker_api", __name__)

@api.post("/worker/submit-job")
def submit_job():
    # 1. Validate blend file
    if "blend_file" not in request.files:
        return jsonify({"error": "No blend file provided"}), 400

    blend_file = request.files["blend_file"]

    if blend_file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    blend_filename = secure_filename(blend_file.filename)
    if not blend_filename.lower().endswith(".blend"):
        return jsonify({"error": "Invalid file type"}), 400

    # 2. Validate metadata file
    if "metadata" not in request.files:
        return jsonify({"error": "No metadata file provided"}), 400

    metadata_file = request.files["metadata"]
    if metadata_file.filename == "":
        return jsonify({"error": "Empty metadata filename"}), 400

    metadata_filename = secure_filename(metadata_file.filename)
    if not metadata_filename.lower().endswith(".json"):
        return jsonify({"error": "Invalid metadata file type"}), 400

    # 3. Read uuid from FORM
    job_id = request.form.get("uuid")
    if not job_id:
        return jsonify({"error": "uuid missing"}), 400

    # 4. Create job directory
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    # 5. Save blend file
    blend_path = os.path.join(job_dir, blend_filename)
    blend_file.save(blend_path)

    # 6. Save metadata file exactly as sent
    metadata_path = os.path.join(job_dir, "metadata.json")
    metadata_file.save(metadata_path)

    print("📦 New Render Job Created")
    print(f"🆔 Job ID: {job_id}")
    print(f"📁 Blend File: {blend_path}")
    print(f"📁 Metadata File: {metadata_path}")

    return jsonify({
        "message": "Job created successfully",
        "job_id": job_id,
        "job_dir": job_dir
    }), 201

@api.post("/worker/stop-render")
def stop_render():
    data = request.get_json()
    ip = data.get("ip")
    job_id = data.get("job_id")

    if not ip or not job_id:
        return jsonify({"success": False, "message": "IP address or Job ID not provided."}), 400

    print(f"Stopping render for Job ID: {job_id} from IP: {ip}")
    
    job_path = os.path.join(JOBS_DIR, job_id)
    metadata_path = os.path.join(job_path, "metadata.json")
    if not os.path.isdir(job_path) or not os.path.exists(metadata_path):
        pass
    else:
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            if metadata.get("status") == "in_progress":
                metadata["status"] = "canceled"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)

                print(f"Render for Job ID: {job_id} has been stopped and marked as canceled.")
        except Exception as e:
            print(f"[WARN] Failed processing {metadata_path} for stopping render: {e}")

    return jsonify({"success": True, "message": f"Render for Job ID: {job_id} has been stopped."})