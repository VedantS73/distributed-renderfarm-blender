import subprocess
from pathlib import Path
import sys


def stitch_pngs_to_video(frames_dir, output_video, fps):

    frames_dir = Path(frames_dir).resolve()
    output_video = Path(output_video).resolve()

    if not frames_dir.exists():
        raise FileNotFoundError(f"Frames directory does not exist: {frames_dir}")

    fps = int(fps)
    if fps <= 0:
        raise ValueError("FPS must be a positive integer")

    # Collect PNG files and sort numerically by filename stem
    png_files = sorted(
        frames_dir.glob("*.png"),
        key=lambda p: int(p.stem)
    )

    if not png_files:
        raise RuntimeError("No PNG files found in directory")

    # Create FFmpeg file list
    list_file = frames_dir / "frames.txt"

    with open(list_file, "w", encoding="utf-8") as f:
        for img in png_files:
            # FFmpeg concat format
            f.write(f"file '{img.name}'\n")

    # FFmpeg command
    command = [
        "ffmpeg",
        "-y",                      
        "-r", str(fps),            
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(output_video)
    ]

    print("[+] Running FFmpeg:")
    print(" ".join(command))

    subprocess.run(command, check=True)

    print(f"[+] Video created: {output_video}")
