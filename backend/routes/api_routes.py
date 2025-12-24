from flask import Blueprint, jsonify, request
from backend.services.discovery_service import NetworkDiscoveryService
import psutil
import shutil

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
        discovery.add_device(discovery.pc_name, discovery.local_ip)
    return jsonify({"success": True})

@api.post("/election/start")
def start_election():
    """
    Initiates the election process and returns the calculated ring topology.
    The Client Node triggers this.
    """
    if not discovery.running:
        return jsonify({"error": "Discovery service is not running. Start it first."}), 400

    # Recalculate scores and topology based on current network state
    election_result = discovery.run_election_simulation()
    
    return jsonify({
        "status": "Election Completed",
        "message": "Ring established and Leader elected based on Composite ID (Score, IP)",
        "data": election_result
    })

@api.get("/election/status")
def get_election_status():
    """
    Returns the current election status for this node.
    This endpoint is called by clients to check their role.
    """
    return jsonify(discovery.get_election_status())