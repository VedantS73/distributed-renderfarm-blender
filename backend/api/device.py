from flask import Blueprint, jsonify, request
import psutil, shutil
from backend.shared.state import discovery
import requests

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

@api.post("/node_disconnected")
def node_disconnected():
    print("1. client has detected a node going down -> ", request.get_json())
    data = request.get_json()
    ip = data.get("ip")
    print("2. processing disconnection for IP -> ", ip)
    if ip:
        print(ip)
        discovery.pop_key(ip)
        
        curr_leader_ip = discovery.current_leader
        print("Notifying current leader about disconnection... LEADR IP: " + str(curr_leader_ip))
        print("Current Leader IP:", curr_leader_ip)
        if curr_leader_ip:
            print("Sending notification to leader at IP:", curr_leader_ip)
            requests.post(f"http://{curr_leader_ip}:5050/api/election/notify_node_disconnection", json={"ip": ip})
        return jsonify({"success": True, "message": f"Device with IP {ip} removed."})
    else:
        return jsonify({"success": False, "message": "IP address not provided."}), 400