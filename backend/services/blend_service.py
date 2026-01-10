import subprocess
import json
import tempfile
import os
from typing import Dict, Optional


class BlendServiceError(Exception):
    pass


class BlendService:
    def __init__(self, blender_binary: str = "blender"):
        """
        :param blender_binary: Path to blender executable
        """
        self.blender_binary = blender_binary

    def analyze(self, blend_file_path: str) -> Dict[str, Optional[str]]:
        if not os.path.isfile(blend_file_path):
            raise BlendServiceError(f"Blend file not found: {blend_file_path}")

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False
        ) as script_file:
            script_file.write(self._blender_analysis_script())
            script_path = script_file.name

        try:
            result = subprocess.run(
                [
                    self.blender_binary,
                    "-b",
                    blend_file_path,
                    "--python",
                    script_path,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise BlendServiceError(
                    f"Blender failed:\n{result.stderr.strip()}"
                )

            try:
                return json.loads(result.stdout.strip())
            except json.JSONDecodeError as e:
                raise BlendServiceError(
                    f"Invalid JSON from Blender:\n{result.stdout}"
                ) from e

        finally:
            os.remove(script_path)

    @staticmethod
    def _blender_analysis_script() -> str:
        """
        This code runs INSIDE Blender (embedded Python).
        """
        return r"""
import bpy
import json
import os

scene = bpy.context.scene

data = {
    "file_name": os.path.basename(bpy.data.filepath),
    "filepath": bpy.data.filepath,
    "scene_name": scene.name,
    "start_frame": scene.frame_start,
    "end_frame": scene.frame_end,
    "engine": scene.render.engine,
    "res_x": scene.render.resolution_x,
    "res_y": scene.render.resolution_y,
    "output_format": scene.render.image_settings.file_format,
}

if scene.render.engine == "CYCLES":
    data["samples"] = scene.cycles.samples
elif scene.render.engine == "BLENDER_EEVEE":
    data["samples"] = scene.eevee.taa_render_samples
else:
    data["samples"] = None

print(json.dumps(data))
"""
