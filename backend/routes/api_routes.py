from flask import Blueprint, jsonify, request
from backend.services.discovery_service import NetworkDiscoveryService
import psutil
import shutil
import os

api = Blueprint("api", __name__, url_prefix="/api")

discovery = NetworkDiscoveryService()

def is_installed(cmd: str) -> bool:
    return shutil.which(cmd) is not None

@api.get("/my_device")
def my_device():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    memory_total = memory.total
    memory_used = memory.used
    memory_usage = (memory_used / memory_total) * 100
    disk = psutil.disk_usage('/')
    disk_usage = disk.percent

    blender_installed = is_installed("blender")
    ffmpeg_installed = is_installed("ffmpeg")

    return jsonify({
        "pc_name": discovery.pc_name,
        "local_ip": discovery.local_ip,
        "cpu_usage": cpu_usage,
        "memory_total": memory_total,
        "memory_used": memory_used,
        "memory_usage": memory_usage,
        "disk_usage": disk_usage,
        "resource_score": discovery.current_score,
        "checks": {
            "blender_installed": blender_installed,
            "ffmpeg_installed": ffmpeg_installed,
            "memory_sufficient": memory_total >= 8 * (1024 ** 3),  # At least 8 GB
            "disk_sufficient": disk.free >= 20 * (1024 ** 3)  # At least 20 GB free
        }
    })

@api.post("/start")
def start():
    ok, msg = discovery.start()
    return jsonify({"success": ok, "message": msg})

@api.post("/stop")
def stop():
    discovery.stop()
    return jsonify({"success": True})

@api.get("/devices")
def get_devices():
    return jsonify(discovery.get_devices())

@api.get("/status_listener")
def status_listener():
    return jsonify({
        "my_role": discovery.my_role,
        "leader": discovery.current_leader,
        "successor": discovery.ring_successor,
        "election_active": discovery.election_active,
        "election_results": discovery.election_results
    })

@api.get("/status")
def status():
    return jsonify({
        "running": discovery.running,
        "local_pc_name": discovery.pc_name,
        "local_ip": discovery.local_ip
    })

@api.post("/clear")
def clear():
    discovery.discovered_devices.clear()
    if discovery.running:
        discovery.add_device(discovery.pc_name, discovery.local_ip, discovery.current_score)
    return jsonify({"success": True})

@api.post("/election/start")
def start_election():
    """
    Initiates the election process and returns the calculated ring topology.
    The Client Node triggers this.
    """
    discovery.initiate_election()
    return jsonify({
        "status": "Election Initiated",
        "message": "Election process has been started. Ring establishment in progress."
    })

@api.get("/election/status", endpoint="election_status")
def get_election_status():
    """
    Returns the current election status for this node.
    This endpoint is called by clients to check their role.
    """
    return jsonify(discovery.get_election_status())

@api.post("/render/upload")
def upload_render_file():
    """
    Upload a Blender file to the leader node for rendering.
    Expects multipart/form-data with 'file' field.
    """
    # Check if running
    if not discovery.running:
        return jsonify({
            "success": False,
            "error": "Discovery service not running"
        }), 400
    
    # Check if we have a leader
    if not discovery.current_leader:
        return jsonify({
            "success": False,
            "error": "No leader elected. Please run election first."
        }), 400
    
    # Check if file was uploaded
    if 'file' not in request.files:
        return jsonify({
            "success": False,
            "error": "No file provided"
        }), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({
            "success": False,
            "error": "No file selected"
        }), 400
    
    # Validate file extension
    if not file.filename.endswith('.blend'):
        return jsonify({
            "success": False,
            "error": "Only .blend files are supported"
        }), 400
    
    try:
        # Save file temporarily
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        
        # Upload to leader
        result = discovery.upload_blender_file(temp_path)
        
        # Clean up temp file
        try:
            os.remove(temp_path)
        except:
            pass
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@api.get("/render/upload/status")
def get_upload_status():
    """
    Get the current upload status for this node.
    """
    return jsonify(discovery.get_upload_status())

@api.get("/render/status")
def get_render_status():
    """
    Returns the current render status for this node.
    - If Leader: returns all render jobs
    - If Worker: returns assigned tasks
    """
    return jsonify(discovery.get_render_status())

@api.get("/render/jobs")
def get_render_jobs():
    """
    Get all render jobs (Leader only).
    """
    if discovery.my_role != "Leader":
        return jsonify({
            "success": False,
            "error": "Only the leader can view all render jobs"
        }), 403
    
    return jsonify({
        "success": True,
        "jobs": list(discovery.render_jobs.values())
    })

@api.get("/render/jobs/<job_id>")
def get_render_job(job_id):
    """
    Get details of a specific render job.
    """
    if job_id in discovery.render_jobs:
        return jsonify({
            "success": True,
            "job": discovery.render_jobs[job_id]
        })
    else:
        return jsonify({
            "success": False,
            "error": "Job not found"
        }), 404

@api.post("/render/jobs/<job_id>/cancel")
def cancel_render_job(job_id):
    """
    Cancel a render job (Leader only).
    """
    if discovery.my_role != "Leader":
        return jsonify({
            "success": False,
            "error": "Only the leader can cancel render jobs"
        }), 403
    
    if job_id not in discovery.render_jobs:
        return jsonify({
            "success": False,
            "error": "Job not found"
        }), 404
    
    discovery.render_jobs[job_id]["status"] = "cancelled"
    discovery.broadcast_render_job(job_id)
    
    return jsonify({
        "success": True,
        "message": f"Job {job_id} cancelled"
    })

@api.post("/render/worker/update")
def update_worker_progress():
    """
    Worker nodes call this to update their render progress.
    Expects JSON: {"job_id": "...", "status": "...", "progress": 0-100}
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "error": "No data provided"
        }), 400
    
    job_id = data.get("job_id")
    status = data.get("status")
    progress = data.get("progress", 0)
    
    if not job_id or not status:
        return jsonify({
            "success": False,
            "error": "job_id and status are required"
        }), 400
    
    # Update local tracking
    discovery.update_render_job(job_id, discovery.local_ip, status, progress)
    
    # Broadcast update to network
    discovery.broadcast_render_job(job_id)
    
    return jsonify({
        "success": True,
        "message": "Progress updated"
    })

@api.get("/health")
def health_check():
    """
    Health check endpoint.
    """
    return jsonify({
        "status": "healthy",
        "running": discovery.running,
        "role": discovery.my_role,
        "leader": discovery.current_leader
    })