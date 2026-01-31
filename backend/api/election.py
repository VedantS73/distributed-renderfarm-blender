import os
import shutil
import requests
from flask import Blueprint, json, jsonify, request
from backend.shared.state import discovery
import datetime

api = Blueprint("election_api", __name__)

JOBS_DIR = "jobs"
os.makedirs(JOBS_DIR, exist_ok=True)

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

@api.post("/election/start")
def start_election():
    if "force_remove" in  request.args:
        force_remove_ip = request.args.get("force_remove")
        discovery.pop_leader(force_remove_ip)
        print(f"Force removed device with IP: {force_remove_ip}")
    print("Election start requested via API")
    print("Current discovered devices:", discovery.get_devices())
    discovery.initiate_election()
    return jsonify({
        "status": "Election Initiated",
        "message": "Election process has been started. Ring establishment in progress."
    })

@api.get("/election/status")
def get_election_status():
    return jsonify(discovery.get_election_status())

@api.post("/election/notify_node_disconnection")
def notify_node_disconnection():
    print("/election/notify_node_disconnection called ======= STEP 2 TO CLIENT DISCONNECTION  =======")
    data = request.get_json()
    ip = data.get("ip")

    if not discovery.discovered_devices.get(ip):
        print(f"No device found with IP: {ip} or Device already removed")
        return jsonify({"success": False, "message": f"No device found with IP: {ip} or Device already removed"}), 404
    
    my_role = discovery.discovered_devices.get(ip).get('my_role')
    print(f"Disconnected node role is: {my_role}")

    if not ip:
        return jsonify({"success": False, "message": "IP address not provided."}), 400

    affected_jobs = []

    # 1. Scan all job folders
    print(f"Processing node disconnection for IP: {ip}")
    
    # Find metadata file with client ip same as disconnected client
    for job_id in os.listdir(JOBS_DIR):
        job_path = os.path.join(JOBS_DIR, job_id)
        metadata_path = os.path.join(job_path, "metadata.json")

        if not os.path.isdir(job_path) or not os.path.exists(metadata_path):
            continue

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            
            print("Metadata loaded")
            # 2. Check if job is in progress and owned by this node
            if metadata.get("status") == "in_progress":
                initiator_client_ip = metadata.get("metadata", {}).get("initiator_client_ip")
                
                # CLIENT CASE
                if initiator_client_ip == ip:
                    print(f"Resetting job {job_id} due to node disconnection.")
                    metadata["status"] = "canceled"
                    with open(metadata_path, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, indent=2)

                    affected_jobs.append(job_id)
                    
                    # discovery.send_client_disconnection()
                    devices = discovery.discovered_devices
                    devices.pop(ip, None)
                    print("*"*50)
                    print(devices)
                    print("*"*50)
                    discovery.broadcast_control_message("STOP_RENDER", { 'job_id' : job_id})

                # WORKER CASE
                else:
                    print(f"Reassigning frames for job {job_id} due to worker node disconnection.")
                    frames_to_reassign = []
                    devices = discovery.discovered_devices
                    devices.pop(ip, None)
                    print("*"*50)
                    print(devices)
                    print("*"*50)
                    if metadata['jobs'][ip]:
                        print(f"Reassigning frames from disconnected node {ip} for job {job_id}.")
                        frames_to_reassign = metadata['jobs'][ip]
                    else:
                        print(f"No frames to reassign from disconnected node {ip} for job {job_id}.")
                        return jsonify({"message": f"No frames to reassign from disconnected node {ip} for job {job_id}."})
                    
                    print(f"Frames to reassign: {frames_to_reassign}")
                    new_job_id = job_id + "_reassign"
                    job_dir = os.path.join(JOBS_DIR, new_job_id)
                    os.makedirs(job_dir, exist_ok=True)

                    # Copy blend file to new job directory
                    blend_file_src = os.path.join(job_path, metadata['filename'])
                    blend_file_dst = os.path.join(job_dir, metadata['filename'])
                    shutil.copy2(blend_file_src, blend_file_dst)

                    new_metadata_path = os.path.join(job_dir, "metadata.json")
                    
                    no_of_other_workers = len(metadata['jobs']) - 1
                    if no_of_other_workers > 0 and frames_to_reassign:
                        frames_per_worker = len(frames_to_reassign) // no_of_other_workers
                        extra_frames = len(frames_to_reassign) % no_of_other_workers

                        frame_index = 0
                        for worker_ip in metadata['jobs']:
                            if worker_ip == ip:
                                continue
                            assigned_frames = frames_to_reassign[frame_index:frame_index + frames_per_worker]
                            if extra_frames > 0:
                                assigned_frames.append(frames_to_reassign[frame_index + frames_per_worker])
                                extra_frames -= 1
                            frame_index += len(assigned_frames)

                            metadata['jobs'][worker_ip] = assigned_frames
                        
                        metadata['jobs'].pop(ip, None)
                        metadata["status"] = "in_progress"
                        metadata["total_no_frames"] = sum(len(frames) for frames in metadata['jobs'].values())
                        metadata["remaining_frames"] = sum(len(frames) for frames in metadata['jobs'].values())
                        metadata["no_of_nodes"] = len(metadata['jobs'])
                        metadata["job_id"] = new_job_id
                        metadata["created_at"] = datetime.datetime.now().isoformat()
                        with open(new_metadata_path, "w", encoding="utf-8") as f:
                            json.dump(metadata, f, indent=2)
                        
                        for job_worker_ip, _ in metadata['jobs'].items():
                            print(f"Notifying worker {job_worker_ip} about reassigned frames for job {new_job_id}.")
                            requests.post(f"http://localhost:5050/api/jobs/broadcast-to-workers", json={
                                "uuid": new_job_id,
                            })

                        affected_jobs.append(new_job_id)
                    else:
                        print(f"No other workers available to reassign frames for job {job_id}.")


        except Exception as e:
            print(f"[WARN] Failed processing {metadata_path}: {e}")

    return jsonify({
        "success": True,
        "message": f"Node {ip} disconnected.",
        "jobs_reset": affected_jobs
    })
