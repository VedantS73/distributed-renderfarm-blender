from backend.services.discovery_service import NetworkDiscoveryService
from backend.services.blender_service import BlenderService

discovery = NetworkDiscoveryService()
blender = BlenderService(blender_binary="/Applications/Blender.app/Contents/MacOS/Blender")