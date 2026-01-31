from flask import Blueprint, request, jsonify, json
import tempfile, uuid, os, requests, datetime
from werkzeug.utils import secure_filename
from backend.shared.state import blender, discovery
import json
from pathlib import Path
import shutil

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

    # 7. If an ordered commit already arrived, finalize it now
    try:
        discovery.finalize_job_if_committed(job_id)
    except Exception:
        pass

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
    data = request.get_json() or {}
    worker_ip = data.get("ip")
    job_id = data.get("job_id")

    if not worker_ip or not job_id:
        return jsonify({"success": False, "message": "IP address or Job ID not provided."}), 400

    result = stop_render_local(job_id=job_id, worker_ip=worker_ip)

    if result.get("status") == "ok":
        print(f"Render for Job ID: {job_id} has been stopped due to node disconnection.")

    print(f"Stopping render for Job ID: {job_id} from IP: {worker_ip}")

    return jsonify({"success": True, "result": result})

def commit_job_local(job_id, assigned_worker_ip):
    """
    Apply the ordered 'JOB_COMMIT' decision locally.

    If the job hasn't arrived yet (files not present), this function returns pending.
    The discovery service keeps a pending set and will re-try after /worker/submit-job.
    """
    job_meta_path = Path(JOBS_DIR) / job_id / "metadata.json"
    if not job_meta_path.exists():
        return {"status": "pending", "message": "Job files not received yet"}

    try:
        with open(job_meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception:
        metadata = {}

    metadata["assigned_worker"] = assigned_worker_ip

    # Don't override a running job, but mark it ready if not started yet
    if metadata.get("status") not in ("in_progress", "completed", "completed_frames"):
        metadata["status"] = "ready"

    with open(job_meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return {"status": "ok", "message": "Job committed"}

def stop_render_local(job_id, worker_ip=None):
    """
    Stop rendering a job locally by marking it as canceled.
    Used by BOTH:
    - HTTP API
    - Sequenced control messages

    If worker_ip is provided, the stop is applied only if the job is assigned to that worker.
    """
    job_meta_path = Path(JOBS_DIR) / job_id / "metadata.json"

    if not job_meta_path.exists():
        return {"status": "error", "message": "Job metadata not found"}

    with open(job_meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    if worker_ip and metadata.get("assigned_worker") not in (None, worker_ip):
        return {"status": "ignored", "message": "Job not assigned to this worker"}

    if metadata.get("status") in ("in_progress", "ready"):
        metadata["status"] = "canceled"
        with open(job_meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        return {"status": "ok", "message": "Render stopped"}

    return {"status": "ignored", "message": "Job not running"}

def cancel_job_local(job_id):
    """Delete a specific job folder locally (ordered control action)."""
    job_path = Path(JOBS_DIR) / job_id
    if not job_path.exists():
        return {"status": "ignored", "message": "Job folder not found"}

    try:
        if job_path.is_dir():
            shutil.rmtree(job_path)
        else:
            job_path.unlink(missing_ok=True)
        return {"status": "ok", "message": "Job deleted"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def cancel_all_local():
    """Delete all jobs locally (ordered control action)."""
    jobs_dir = Path(JOBS_DIR)
    if not jobs_dir.exists():
        return {"status": "ignored", "message": "Jobs dir not found"}

    deleted = 0
    for p in jobs_dir.iterdir():
        try:
            if p.is_dir():
                shutil.rmtree(p)
                deleted += 1
        except Exception:
            continue

    return {"status": "ok", "deleted": deleted}
