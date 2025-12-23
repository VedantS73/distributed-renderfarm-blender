from flask import Blueprint, jsonify, request
from backend.services.discovery_service import NetworkDiscoveryService

api = Blueprint("api", __name__, url_prefix="/api")

discovery = NetworkDiscoveryService()

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
