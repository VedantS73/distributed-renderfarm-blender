import os
from flask import Blueprint, jsonify, request, json
import psutil, shutil
from backend.shared.state import discovery
import requests

api = Blueprint("device_api", __name__)
JOBS_DIR = "jobs"
os.makedirs(JOBS_DIR, exist_ok=True)
    
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
        # discovery.pop_key(ip)
        
        curr_leader_ip = discovery.current_leader
        print("Notifying current leader about disconnection... LEADR IP: " + str(curr_leader_ip))
        print("Current Leader IP:", curr_leader_ip)
        if curr_leader_ip:
            print("Sending notification to leader at IP:", curr_leader_ip)
            requests.post(f"http://{curr_leader_ip}:5050/api/election/notify_node_disconnection", json={"ip": ip})
        return jsonify({"success": True, "message": f"Device with IP {ip} removed."})
    else:
        return jsonify({"success": False, "message": "IP address not provided."}), 400

@api.post("/leader_is_down_flag")
def leader_is_down_flag():
    crashed_leader_ip = False

    print("Leader is down! Restarting election")
    # Find ongoing jobs where you are the client
    for job_id in os.listdir(JOBS_DIR):
        print("Current Job id ", job_id)
        job_path = os.path.join(JOBS_DIR, job_id)
        metadata_path = os.path.join(job_path, "metadata.json")

        if not os.path.isdir(job_path) or not os.path.exists(metadata_path):
            continue

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            print("Metadata loaded")
            print("Client ip ", discovery.local_ip)
            # 2. Check if job is in progress and you are the client of this node
            if (metadata.get("status") != "completed_video") and (metadata.get("status") != "canceled") :
                client_ip = metadata.get("initiator_client_ip")
                print("Metadata client ip ", client_ip,". Status ", metadata.get("status"))
                if discovery.local_ip == client_ip:
                    # Start leader election again
                    leader_ip = metadata.get("leader_ip")
                    discovery.pop_leader(leader_ip)
                    print("Election start requested as current leader disconnected")
                    print("Current discovered devices:", discovery.get_devices())
                    discovery.initiate_election()

                    # Cancelling job
                    metadata["status"] = "canceled"
                    crashed_leader_ip = True
                    with open(metadata_path, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, indent=2)
                
        except Exception as e:
            print(f"[WARN] Failed processing {metadata_path}: {e}")
            
    return jsonify({"leader_is_down": crashed_leader_ip})