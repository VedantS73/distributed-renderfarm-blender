from flask import Blueprint, request, jsonify
import tempfile, uuid, os, requests, datetime
from werkzeug.utils import secure_filename
from backend.shared.state import blender, discovery
from pathlib import Path
import json

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
    metadata["initiator_client_ip"] = discovery.local_ip

    election_status = discovery.get_election_status()
    leader_ip = election_status.get("current_leader")

    if not leader_ip:
        return jsonify({"error": "No leader found in the network"}), 500

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

    if metadata.get('initiator_is_participant') == 'undefined':
        metadata['initiator_is_participant'] = False
    else:
        metadata["initiator_is_participant"] = True
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
        "metadata": metadata,
        "status": "created",
        "no_of_nodes": len(discovery.ring_topology),
        "leader_ip": discovery.local_ip,
        "scores": {worker['ip']: worker.get('resource_score', 0) for worker in discovery.discovered_devices}
    }

    metadata_path = os.path.join(job_dir, "metadata.json")
    with open(metadata_path, "w") as f:
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

@api.post("/jobs/broadcast-to-workers")
def broadcast_job_to_workers():
    data = request.get_json(silent=True)
    job_id = data.get("uuid") if data else None
    
    if not job_id:
        return jsonify({"error": "uuid is required"}), 400
    
    jobdir = Path(JOBS_DIR)
    jobdir.mkdir(exist_ok=True)

    job_path = jobdir / job_id
    if not job_path.is_dir():
        return jsonify({"error": "Job folder not found"}), 404

    blend_file = None
    json_file = None
    
    for f in job_path.iterdir():
        if f.suffix == ".blend":
            blend_file = f
        elif f.suffix == ".json":
            json_file = f

    if not blend_file or not json_file:
        return jsonify(
            {"error": "Job folder must contain one .blend and one .json file"}
        ), 400

    # --- Update jobs keys with IPs ---
    with open(json_file, "r+") as jf:
        metadata = json.load(jf)
        old_jobs = metadata.get("jobs", {})

        # Map old numeric keys to IPs from discovery.ring_topology
        new_jobs = {}
        worker_ips = [w['ip'] for w in discovery.ring_topology]

        for idx, ip in enumerate(worker_ips):
            old_key = str(idx + 1)  # old keys are "1", "2", ...
            if old_key in old_jobs:
                new_jobs[ip] = old_jobs[old_key]

        metadata["jobs"] = new_jobs

        # Write back updated metadata
        jf.seek(0)
        json.dump(metadata, jf, indent=4)
        jf.truncate()
    # --- Done updating jobs ---

    results = []
    
    for worker in discovery.ring_topology:
        worker_ip = worker['ip']
        print(f"Sending job to worker at {worker_ip}")
        worker_url = f"http://{worker_ip}:5050/api/worker/submit-job"
        try:
            with open(blend_file, "rb") as bf, open(json_file, "rb") as jf:
                response = requests.post(
                    worker_url,
                    data={"uuid": job_id},
                    files={"blend_file": bf, "metadata": jf},
                    timeout=30
                )
            results.append({
                "worker": worker,
                "status": response.status_code,
            })
        except Exception as e:
            results.append({
                "worker": worker,
                "error": str(e),
            })

    return jsonify({
        "job_id": job_id,
        "broadcast_results": results,
    }), 200

@api.post("/jobs/submit-frames")
def submit_frames():
    # 1. Validate input
    job_id = request.form.get("uuid")
    image = request.files.get("image")

    if not job_id:
        return jsonify({"error": "uuid is required"}), 400

    if not image:
        return jsonify({"error": "image file is required"}), 400

    # 2. Validate job folder
    job_path = Path(JOBS_DIR) / job_id
    if not job_path.is_dir():
        return jsonify({"error": "Job folder not found"}), 404

    # 3. Validate metadata.json
    metadata_path = job_path / "metadata.json"
    if not metadata_path.is_file():
        return jsonify({"error": "metadata.json not found"}), 400

    with metadata_path.open("r") as f:
        metadata = json.load(f)

    # 4. Check job status
    if metadata.get("status") != "in_progress":
        return jsonify({"error": "Job is not in progress"}), 409

    # 5. Create renders directory
    renders_dir = job_path / "renders"
    renders_dir.mkdir(exist_ok=True)

    # 6. Save image
    filename = secure_filename(image.filename)

    # Optional: auto-generate filename if worker sends same name
    if not filename:
        filename = f"frame_{datetime.utcnow().timestamp()}.png"

    image_path = renders_dir / filename
    image.save(image_path)

    # 7. Update remaining_frames
    remaining = metadata.get("remaining_frames")

    if not isinstance(remaining, int) or remaining <= 0:
        return jsonify({"error": "Invalid remaining_frames value"}), 400

    print(f"[-] Received frame no {filename}, updating remaining frames {remaining}")
    metadata["remaining_frames"] = remaining - 1

    # Optional: auto-finish job
    if metadata["remaining_frames"] == 0:
        metadata["status"] = "completed_frames"

    with metadata_path.open("w") as f:
        json.dump(metadata, f, indent=2)

    # 8. Success response
    return jsonify({
        "job_id": job_id,
        "saved_as": filename,
        "remaining_frames": metadata["remaining_frames"]
    }), 200

@api.get("/jobs/send-video-to-client")
def send_video_to_client():
    job_id = request.data.get("uuid")
    client_ip = request.data.get("client_ip")
    if not job_id:
        return jsonify({"error": "uuid is required"}), 

    if not client_ip:
        return jsonify({"error": "No client IP found in metadata"}), 400

    job_path = Path(JOBS_DIR) / job_id
    if not job_path.is_dir():
        return jsonify({"error": "Job folder not found"}), 404

    metadata_path = job_path / "metadata.json"
    if not metadata_path.is_file():
        return jsonify({"error": "metadata.json not found"}), 400

    with metadata_path.open("r") as f:
        metadata = json.load(f)

    video_path = job_path / "renders/output_video.mp4"
    if not video_path.is_file():
        return jsonify({"error": "Output video not found"}), 404

    client_url = f"http://{client_ip}:5050/api/jobs/receive-video"

    try:
        with open(video_path, "rb") as vf:
            response = requests.post(
                client_url,
                data={"uuid": job_id},
                files={"video_file": vf},
                timeout=30
            )

        if response.status_code != 200:
            return jsonify({
                "error": "Client rejected video",
                "details": response.text
            }), 502

        return jsonify({
            "message": "Video successfully sent to client",
            "client": client_ip
        }), 200

    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502