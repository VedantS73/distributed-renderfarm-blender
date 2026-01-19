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
        discovery.add_device(discovery.pc_name, discovery.local_ip, discovery.current_score, role=discovery.my_role)
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

# --- Health Check Endpoint ---

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