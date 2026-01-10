from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename
import os
import json
import subprocess
import threading
import psutil
import shutil
from backend.services.discovery_service import NetworkDiscoveryService

api = Blueprint("api", __name__, url_prefix="/api")

discovery = NetworkDiscoveryService()

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'rendered_output'
ALLOWED_EXTENSIONS = {'blend'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def is_installed(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_blend_info(filepath):
    """Extract scene information from Blender file"""
    try:
        # Use Blender's Python API to extract info
        script = f"""
import bpy
import json

bpy.ops.wm.open_mainfile(filepath=r"{filepath}")
scene = bpy.context.scene

info = {{
    "scene_name": scene.name,
    "total_frames": scene.frame_end - scene.frame_start + 1,
    "frame_start": scene.frame_start,
    "frame_end": scene.frame_end,
    "frame_rate": scene.render.fps,
    "render_engine": scene.render.engine,
    "resolution_x": scene.render.resolution_x,
    "resolution_y": scene.render.resolution_y,
    "resolution_percentage": scene.render.resolution_percentage,
    "duration": (scene.frame_end - scene.frame_start + 1) / scene.render.fps
}}

print("BLEND_INFO_START")
print(json.dumps(info))
print("BLEND_INFO_END")
"""
        
        result = subprocess.run(
            ['blender', '-b', filepath, '--python-expr', script],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Parse output
        output = result.stdout
        start_idx = output.find('BLEND_INFO_START')
        end_idx = output.find('BLEND_INFO_END')
        
        if start_idx != -1 and end_idx != -1:
            json_str = output[start_idx + len('BLEND_INFO_START'):end_idx].strip()
            return json.loads(json_str)
        
        # Fallback to basic info
        return {
            "scene_name": "Unknown",
            "total_frames": 1,
            "frame_start": 1,
            "frame_end": 1,
            "frame_rate": 24,
            "render_engine": "CYCLES",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "duration": 0
        }
    except Exception as e:
        print(f"Error extracting blend info: {e}")
        return {
            "scene_name": "Unknown",
            "total_frames": 1,
            "frame_start": 1,
            "frame_end": 1,
            "frame_rate": 24,
            "render_engine": "CYCLES",
            "resolution_x": 1920,
            "resolution_y": 1080,
            "duration": 0
        }

# --- Device & Status Endpoints ---

@api.get("/my_device")
def my_device():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    blender_installed = is_installed("blender")
    ffmpeg_installed = is_installed("ffmpeg")

    return jsonify({
        "pc_name": discovery.pc_name,
        "local_ip": discovery.local_ip,
        "cpu_usage": cpu_usage,
        "memory_total": memory.total,
        "memory_used": memory.used,
        "memory_usage": (memory.used / memory.total) * 100,
        "disk_usage": disk.percent,
        "resource_score": discovery.current_score,
        "checks": {
            "blender_installed": blender_installed,
            "ffmpeg_installed": ffmpeg_installed,
            "memory_sufficient": memory.total >= 8 * (1024 ** 3),
            "disk_sufficient": disk.free >= 20 * (1024 ** 3)
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

# --- Election Endpoints ---

@api.post("/election/start")
def start_election():
    discovery.initiate_election()
    return jsonify({
        "status": "Election Initiated",
        "message": "Election process has been started. Ring establishment in progress."
    })

@api.get("/election/status")
def get_election_status():
    return jsonify(discovery.get_election_status())

# --- Render Endpoints ---

@api.post("/render/upload")
def upload_render_file():
    """Upload a Blender file and extract scene information"""
    if not discovery.running:
        return jsonify({
            "success": False,
            "error": "Discovery service not running"
        }), 400
    
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
    
    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": "Only .blend files are supported"
        }), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Extract blend file info
        blend_info = get_blend_info(filepath)
        
        # Store the uploaded file info
        discovery.current_blend_file = {
            "filename": filename,
            "filepath": filepath,
            "info": blend_info
        }
        
        return jsonify({
            "success": True,
            "filename": filename,
            **blend_info
        }), 200
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@api.post("/render/start")
def start_render():
    """Start the distributed render job"""
    if discovery.my_role != "Leader":
        return jsonify({
            "success": False,
            "error": "Only the leader can start render jobs"
        }), 403
    
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "error": "No configuration provided"
        }), 400
    
    if not hasattr(discovery, 'current_blend_file'):
        return jsonify({
            "success": False,
            "error": "No blend file uploaded"
        }), 400
    
    try:
        render_config = {
            "start_frame": data.get("startFrame", 1),
            "end_frame": data.get("endFrame", 1),
            "samples": data.get("samples", 128),
            "resolution_x": data.get("resolutionX", 1920),
            "resolution_y": data.get("resolutionY", 1080),
            "engine": data.get("engine", "CYCLES"),
            "output_format": data.get("outputFormat", "PNG")
        }
        
        # Create render job
        job_id = f"render_{int(discovery.local_ip.replace('.', ''))}_{int(time.time())}"
        
        total_frames = render_config["end_frame"] - render_config["start_frame"] + 1
        
        # Distribute frames across workers
        workers = [d for d in discovery.discovered_devices.values() 
                   if d['ip'] != discovery.local_ip]
        
        if not workers:
            return jsonify({
                "success": False,
                "error": "No workers available"
            }), 400
        
        # Assign frames to workers
        frames_per_worker = max(1, total_frames // len(workers))
        frame_assignments = {}
        
        current_frame = render_config["start_frame"]
        for idx, worker in enumerate(workers):
            start = current_frame
            if idx == len(workers) - 1:
                # Last worker gets remaining frames
                end = render_config["end_frame"]
            else:
                end = min(start + frames_per_worker - 1, render_config["end_frame"])
            
            frame_assignments[worker['ip']] = {
                "start_frame": start,
                "end_frame": end,
                "frames": list(range(start, end + 1))
            }
            current_frame = end + 1
        
        # Create render job
        discovery.render_jobs[job_id] = {
            "job_id": job_id,
            "filename": discovery.current_blend_file['filename'],
            "filepath": discovery.current_blend_file['filepath'],
            "config": render_config,
            "frame_assignments": frame_assignments,
            "status": "running",
            "progress": 0,
            "total_frames": total_frames,
            "completed_frames": 0,
            "frame_status": {str(f): "pending" for f in range(render_config["start_frame"], 
                                                               render_config["end_frame"] + 1)},
            "worker_progress": {w['ip']: 0 for w in workers},
            "created_at": datetime.now().isoformat(),
            "started_at": datetime.now().isoformat()
        }
        
        # Broadcast job to workers
        discovery.broadcast_render_job(job_id)
        
        return jsonify({
            "success": True,
            "job_id": job_id,
            "total_frames": total_frames,
            "workers": len(workers),
            "frame_assignments": frame_assignments
        }), 200
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@api.get("/render/progress")
def get_render_progress():
    """Get overall render progress"""
    if discovery.my_role != "Leader":
        return jsonify({
            "success": False,
            "error": "Only leader can view overall progress"
        }), 403
    
    # Get the latest job
    if not discovery.render_jobs:
        return jsonify({
            "overall_progress": 0,
            "completed_frames": 0,
            "total_frames": 0,
            "frame_status": []
        })
    
    latest_job_id = list(discovery.render_jobs.keys())[-1]
    job = discovery.render_jobs[latest_job_id]
    
    return jsonify({
        "overall_progress": job.get("progress", 0),
        "completed_frames": job.get("completed_frames", 0),
        "total_frames": job.get("total_frames", 0),
        "frame_status": [
            {"frame": int(k), "status": v} 
            for k, v in job.get("frame_status", {}).items()
        ]
    })

@api.get("/render/worker-progress")
def get_worker_progress():
    """Get progress for each worker"""
    if discovery.my_role != "Leader":
        return jsonify({})
    
    if not discovery.render_jobs:
        return jsonify({})
    
    latest_job_id = list(discovery.render_jobs.keys())[-1]
    job = discovery.render_jobs[latest_job_id]
    
    worker_progress = {}
    for worker_ip, progress in job.get("worker_progress", {}).items():
        worker_info = discovery.discovered_devices.get(worker_ip, {})
        worker_progress[worker_ip] = {
            "name": worker_info.get("name", "Unknown"),
            "progress": progress,
            "assignment": job.get("frame_assignments", {}).get(worker_ip, {})
        }
    
    return jsonify(worker_progress)

@api.post("/render/worker/update")
def update_worker_progress():
    """Worker nodes call this to update their render progress"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            "success": False,
            "error": "No data provided"
        }), 400
    
    job_id = data.get("job_id")
    frame = data.get("frame")
    status = data.get("status")
    worker_progress = data.get("progress", 0)
    
    if not job_id or frame is None or not status:
        return jsonify({
            "success": False,
            "error": "job_id, frame, and status are required"
        }), 400
    
    # Update render job
    if job_id in discovery.render_jobs:
        job = discovery.render_jobs[job_id]
        
        # Update frame status
        job["frame_status"][str(frame)] = status
        
        # Update worker progress
        job["worker_progress"][discovery.local_ip] = worker_progress
        
        # Calculate overall progress
        completed = sum(1 for s in job["frame_status"].values() if s == "completed")
        job["completed_frames"] = completed
        job["progress"] = int((completed / job["total_frames"]) * 100)
        
        # Broadcast update
        discovery.broadcast_render_job(job_id)
    
    return jsonify({
        "success": True,
        "message": "Progress updated"
    })

@api.get("/render/my-assignment")
def get_my_assignment():
    """Worker gets their frame assignment"""
    if not discovery.render_jobs:
        return jsonify({
            "success": False,
            "error": "No active render jobs"
        }), 404
    
    latest_job_id = list(discovery.render_jobs.keys())[-1]
    job = discovery.render_jobs[latest_job_id]
    
    assignment = job.get("frame_assignments", {}).get(discovery.local_ip)
    
    if not assignment:
        return jsonify({
            "success": False,
            "error": "No assignment for this worker"
        }), 404
    
    return jsonify({
        "success": True,
        "job_id": latest_job_id,
        "assignment": assignment,
        "blend_file": job["filename"],
        "config": job["config"]
    })

@api.get("/render/jobs")
def get_render_jobs():
    """Get all render jobs (Leader only)"""
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
    """Get specific render job details"""
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
    """Cancel a render job (Leader only)"""
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

@api.get("/render/download/<job_id>")
def download_render(job_id):
    """Download rendered frames as a zip file"""
    if job_id not in discovery.render_jobs:
        return jsonify({
            "success": False,
            "error": "Job not found"
        }), 404
    
    job = discovery.render_jobs[job_id]
    
    if job["status"] != "completed":
        return jsonify({
            "success": False,
            "error": "Job not completed yet"
        }), 400
    
    # Create zip file of rendered frames
    import zipfile
    zip_path = os.path.join(OUTPUT_FOLDER, f"{job_id}.zip")
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        output_dir = os.path.join(OUTPUT_FOLDER, job_id)
        if os.path.exists(output_dir):
            for file in os.listdir(output_dir):
                file_path = os.path.join(output_dir, file)
                zipf.write(file_path, file)
    
    return send_file(zip_path, as_attachment=True)

@api.get("/health")
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "running": discovery.running,
        "role": discovery.my_role,
        "leader": discovery.current_leader
    })

# Add these to discovery service
import time
from datetime import datetime

# Initialize additional attributes in NetworkDiscoveryService.__init__
discovery.current_blend_file = None