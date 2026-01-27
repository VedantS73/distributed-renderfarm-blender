from flask import Blueprint, jsonify, request
from backend.shared.state import discovery

api = Blueprint("election_api", __name__)

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
        discovery.pop_key_from_discovered(force_remove_ip)
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