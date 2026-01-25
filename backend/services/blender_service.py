import subprocess
import os
from typing import Dict, Optional

class BlendServiceError(Exception):
    pass

env = os.environ.copy()
class BlenderService:
    def __init__(self, blender_binary: Optional[str] = None):
        self.blender_binary = (
            blender_binary
            or os.getenv("BLENDER_PATH")
            or "blender"
        )

    def analyze(self, blend_file_path: str) -> Dict[str, Optional[str]]:
        blend_details = dict()
        
        print("according to param ->:", self.blender_binary)

        python_script_path = "backend/services/extract_blend_file_properties.py"
        print("according to env ->", os.getenv("BLENDER_PATH") )
        
        subprocess.run(
        [
            self.blender_binary,
            blend_file_path,
            "--background",
            "--python",
            python_script_path,
        ],
    env=os.environ.copy(),
    check=True
)


        # created by blender command above
        with open("blend_file_data.txt", "r") as file:
            properties = file.readlines()

        # Forming a dictionary where key is property name and value is property value
        blend_file_properties = dict()
        for property in properties:
             property_name, property_value = property.strip().split(":")
             blend_file_properties[property_name] = property_value


        file.close()

        # Deleting the file as its only for temporary purposes
        os.remove("blend_file_data.txt")

        blend_details["fps"] = int(blend_file_properties["fps"])
        blend_details["renderer"] = blend_file_properties["renderer"]
        blend_details["frame_start"] = int(blend_file_properties["frame_start"])
        blend_details["frame_end"] = int(blend_file_properties["frame_end"])
        return blend_details