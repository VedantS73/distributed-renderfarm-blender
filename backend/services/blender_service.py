import subprocess
import json
import tempfile
import os
from typing import Dict, Optional
from .blender_render_info.blend_render_info import read_blend_rend_chunk

class BlendServiceError(Exception):
    pass


class BlenderService:
    def __init__(self, blender_binary: str = "blender"):
        """
        :param blender_binary: Path to blender executable
        """
        self.blender_binary = blender_binary

    def analyze(self, blend_file_path: str) -> Dict[str, Optional[str]]:
        blend_details = dict()
        
        blend_details["fps"] = 24

        blend_chunk = (read_blend_rend_chunk(blend_file_path))

        print(blend_chunk)

        # blend_details["frame_start"] = blend_chunk[0]
        # blend_details["frame_end"] = blend_chunk[1]
        return blend_details