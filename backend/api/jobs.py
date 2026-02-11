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

    no_of_nodes = len(discovery.ring_topology)
    if metadata.get('initiator_is_participant') == 'undefined':
        no_of_nodes -= 1
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
    print(discovery.discovered_devices)
    scores = {}
    for ip, data  in discovery.discovered_devices.items():
        scores[ip] = data.get('resource_score', 0)
    
    metadata_payload = {
        "job_id": job_id,
        "filename": filename,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "metadata": metadata,
        "status": "created",
        "no_of_nodes": no_of_nodes,
        "leader_ip": discovery.local_ip,
        "scores": scores
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
    print("Devices to give job to ", discovery.get_devices())
    # RELIABLE ORDERING (optional marker): announce job creation in global sequence
    try:
        if discovery.my_role == "Leader":
            discovery.broadcast_control_message("JOB_CREATED", {"job_id": job_id})
    except:
        pass

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
        initiator_client_ip = metadata.get("metadata", {}).get("initiator_client_ip")
        old_jobs = metadata.get("jobs", {})

        # Map old numeric keys to IPs from discovery.ring_topology
        new_jobs = old_jobs
        worker_ips = [w['ip'] for w in discovery.ring_topology]

        print("==================================================================")
        print("Old Jobs Keys:", old_jobs)
        print("==================================================================")
        idx=0
        for ip in worker_ips:
            if initiator_client_ip == ip and not metadata["metadata"].get("initiator_is_participant", False):
                continue
            old_key = str(idx + 1)  # old keys are "1", "2", ...
            if old_key in old_jobs:
                new_jobs[ip] = old_jobs[old_key]
                new_jobs.pop(old_key, None)
            idx+=1

        print("New Job keys: ", new_jobs)
        metadata["jobs"] = new_jobs

        # Write back updated metadata
        jf.seek(0)
        json.dump(metadata, jf, indent=4)
        jf.truncate()
    # --- Done updating jobs ---

    # RELIABLE ORDERING: announce broadcast start in global sequence
    try:
        if discovery.my_role == "Leader":
            discovery.broadcast_control_message("JOB_BROADCAST_BEGIN", {"job_id": job_id})
    except:
        pass

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

            # RELIABLE ORDERING: per-worker "sent" marker in global sequence
            try:
                if discovery.my_role == "Leader":
                    discovery.broadcast_control_message("JOB_SENT", {"job_id": job_id, "worker_ip": worker_ip})
            except:
                pass

        except Exception as e:
            results.append({
                "worker": worker,
                "error": str(e),
            })

    # RELIABLE ORDERING: announce broadcast completion in global sequence
    try:
        if discovery.my_role == "Leader":
            discovery.broadcast_control_message("JOB_BROADCAST_DONE", {"job_id": job_id})
    except:
        pass


    # RELIABLE ORDERING: commit the job globally (workers will process this in strict sequence)
    try:
        if discovery.my_role == "Leader":
            discovery.broadcast_control_message("JOB_COMMIT", {"job_id": job_id})
    except:
        pass

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

    # count number of files in renders directory
    no_of_frames = 0
    renders_dir = job_path / "renders"
    if renders_dir.is_dir():
        no_of_frames = len(list(renders_dir.glob("*.*")))

    
    print("Number of frames in folder : ", no_of_frames)
    
    # 7. Update remaining_frames
    remaining = metadata.get("remaining_frames")

    if not isinstance(remaining, int) or remaining <= 0:
        return jsonify({"error": "Invalid remaining_frames value"}), 400

    
    metadata["remaining_frames"] = remaining - 1
    
    # Optional: auto-finish job
    if metadata["remaining_frames"] == 0:
        metadata["status"] = "completed_frames"
        
    if metadata["total_no_frames"] == no_of_frames:
        metadata["status"] = "completed_frames"

    with metadata_path.open("w") as f:
        json.dump(metadata, f, indent=2)

    # 8. Success response
    return jsonify({
        "job_id": job_id,
        "saved_as": filename,
        "remaining_frames": metadata["remaining_frames"]
    }), 200

@api.post("/jobs/send-video-to-client")
def send_video_to_client():
    job_id = request.form.get("uuid")
    status = request.form.get("status")
    client_ip = request.form.get("client_ip")
    video = request.files.get("video")
    print(request.files)
    
    print("Received video upload request")
    if not job_id:
        print("Job ID missing in request")
        return jsonify({"error": "uuid is required"}), 400

    if not video:
        print("Video file missing in request")
        return jsonify({"error": "video file is missing"}), 400
    
    job_path = Path(JOBS_DIR) / job_id
    if not job_path.is_dir():
        print("Job folder not found")
        return jsonify({"error": "Job folder not found"}), 404

    metadata_path = job_path / "metadata.json"
    if not metadata_path.is_file():
        return jsonify({"error": "metadata.json not found"}), 400

    with metadata_path.open("r") as f:
        metadata = json.load(f)

    video_path = job_path / "output_video.mp4"
    video.save(video_path)

    print(f"[+] Received video for job {job_id}")
    print(f"    Status     : {status}")
    print(f"    From IP    : {client_ip}")
    print(f"    Saved at   : {video_path}")

    return jsonify({
        "message": "Video received successfully",
        "job_id": job_id,
        "path": str(video_path)
    }), 200
