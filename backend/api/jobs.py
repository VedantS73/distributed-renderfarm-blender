from flask import Blueprint, request, jsonify
import tempfile, uuid, os, requests, datetime
from werkzeug.utils import secure_filename
from backend.shared.state import blender, discovery

JOBS_DIR = "jobs"
os.makedirs(JOBS_DIR, exist_ok=True)

api = Blueprint("jobs_api", __name__)

@api.post("/jobs/analyze")
def analyze_blend():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".blend"):
        return jsonify({"error": "Invalid file type"}), 400

    job_id = str(uuid.uuid4())

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".blend"
    ) as tmp:
        file.save(tmp.name)
        blend_file_path = tmp.name

    analysis_result = blender.analyze(blend_file_path)
    return jsonify(analysis_result), 201

@api.post("/jobs/upload")
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".blend"):
        return jsonify({"error": "Invalid file type"}), 400

    # metadata from frontend (renderer, frames, fps, etc.)
    metadata = request.form.to_dict()

    election_status = discovery.get_election_status()
    leader_ip = election_status.get("current_leader")

    if not leader_ip:
        return jsonify({"error": "No leader found in the network"}), 500

    leader_ip = election_status.get("current_leader")
    leader_url = f"http://{leader_ip}:5050/api/jobs/create"

    print(f"Forwarding job to leader at {leader_url}")

    # Save temporarily before forwarding
    with tempfile.NamedTemporaryFile(delete=False, suffix=".blend") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            files = {
                "file": (filename, f, "application/octet-stream")
            }
            response = requests.post(
                leader_url,
                files=files,
                data=metadata,
                timeout=10
            )

        if response.status_code != 201:
            return jsonify({
                "error": "Leader rejected job",
                "details": response.text
            }), 502

        return jsonify({
            "message": "Job successfully forwarded to leader",
            "leader": leader_ip
        }), 201

    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502

    finally:
        os.unlink(tmp_path)

# -- Leader Endpoints --

@api.post("/jobs/create")
def create_job():
    # 1. Validate file
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".blend"):
        return jsonify({"error": "Invalid file type"}), 400

    # 2. Read metadata
    metadata = request.form.to_dict()

    # 3. Generate JOB ID
    job_id = str(uuid.uuid4())

    # 4. Create job directory
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    # 5. Save file
    file_path = os.path.join(job_dir, filename)
    file.save(file_path)

    # 6. Persist metadata (optional but highly recommended)
    metadata_payload = {
        "job_id": job_id,
        "filename": filename,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "metadata": metadata
    }

    metadata_path = os.path.join(job_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        import json
        json.dump(metadata_payload, f, indent=2)

    # 7. Print metadata (as requested)
    print("📦 New Render Job Created")
    print(f"🆔 Job ID: {job_id}")
    print(f"📁 File: {file_path}")
    print("📝 Metadata:")
    for k, v in metadata.items():
        print(f"   {k}: {v}")

    return jsonify({
        "message": "Job created successfully",
        "job_id": job_id,
        "job_dir": job_dir
    }), 201