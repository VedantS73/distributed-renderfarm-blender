import subprocess
import json
import tempfile
import os
from typing import Dict, Optional


class BlendServiceError(Exception):
    pass


class BlenderService:
    def __init__(self, blender_binary: str = "blender"):
        """
        :param blender_binary: Path to blender executable
        """
        self.blender_binary = blender_binary

    def analyze(self, blend_file_path: str) -> Dict[str, Optional[str]]:
        pass