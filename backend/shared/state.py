from backend.services.discovery_service import NetworkDiscoveryService
from backend.services.blender_service import BlenderService
import os

BLENDER_PATH = os.getenv("BLENDER_PATH") or "blender"
print("Starting Server with Blender Binary at : " + BLENDER_PATH)

discovery = NetworkDiscoveryService()
blender = BlenderService(blender_binary=BLENDER_PATH)