from flask import Blueprint, jsonify
import psutil, shutil
from backend.shared.state import discovery

api = Blueprint("device_api", __name__)

def is_installed(cmd: str) -> bool:
    return shutil.which(cmd) is not None

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
