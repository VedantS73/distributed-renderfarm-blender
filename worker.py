import time
import json
import os
import shutil
import requests
import subprocess
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from backend.shared.state import discovery
from dotenv import load_dotenv
from backend.services.ffmpeg_service import stitch_pngs_to_video
from backend.shared.state import discovery

load_dotenv('.env')
BLENDER_PATH = os.getenv("BLENDER_PATH") or "blender"
print("Starting Worker with Blender Binary at : " + BLENDER_PATH)

WATCH_DIR = "jobs"
JSON_FILENAME = "metadata.json"
SERVER_URL = "http://localhost:5050/api/jobs/broadcast-to-workers"

processed_blender_jobs = []

# ==========================================
# WATCHDOG HANDLER
# ==========================================

class FolderHandler(FileSystemEventHandler):

    def on_created(self, event):
        if not event.is_directory:
            return

        folder_path = event.src_path
        print(f"[+] New folder detected: {folder_path}")
        time.sleep(1)  # wait for filesystem writes

        json_path = os.path.join(folder_path, JSON_FILENAME)
        if not os.path.exists(json_path):
            print("[-] metadata.json not found, ignoring folder")
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("status") != "created":
                print(f"[-] Job status is '{data.get('status')}', skipping")
                return

            # Validate and split frames
            frame_start = int(data["metadata"]["frame_start"])
            frame_end = int(data["metadata"]["frame_end"])
            workers = int(data["no_of_nodes"])
            # if not data["metadata"].get("initiator_is_participant", True):
            #     workers -= 1

            if frame_end < frame_start or workers <= 0:
                print("[!] Invalid frame range or worker count")
                return

            total_frames = frame_end - frame_start + 1
            base_frames = total_frames // workers
            extra_frames = total_frames % workers

            jobs = {}
            current_frame = frame_start
            for worker_id in range(1, workers + 1):
                count = base_frames + (1 if worker_id <= extra_frames else 0)
                frames = list(range(current_frame, current_frame + count))
                jobs[str(worker_id)] = frames
                current_frame += count

            data["status"] = "in_progress"
            data["jobs"] = jobs
            data["total_no_frames"] = total_frames
            data["remaining_frames"] = total_frames

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            # Notify server
            response = requests.post(SERVER_URL, json={"uuid": os.path.basename(folder_path)}, timeout=5)
            response.raise_for_status()
            print("[+] Job accepted, split, and sent to server")

        except Exception as e:
            print("[!] Error handling folder:", e)
        
# ==========================================
# RENDERING LOOP
# ==========================================

def render_in_progress_jobs():
    while True:
        try:
            for job_folder in os.listdir(WATCH_DIR):
                if job_folder in processed_blender_jobs:
                    continue

                folder_path = os.path.join(WATCH_DIR, job_folder)
                json_path = os.path.join(folder_path, JSON_FILENAME)
                if not os.path.exists(json_path):
                    continue

                with open(json_path) as f:
                    data = json.load(f)

                if data.get("status") != "in_progress":
                    continue

                blend_file = data.get("filename")
                if not blend_file or not os.path.exists(os.path.join(folder_path, blend_file)):
                    print(f"Blend file not found for job {job_folder}")
                    continue

                # Get frames assigned to this node
                my_id = str(discovery.local_ip)
                frames = data.get("jobs", {}).get(my_id, [])
                if not frames:
                    print(f"No frames assigned to this node for job {job_folder}")
                    continue

                # Prepare output folder
                job_output_path = os.path.join(os.getcwd(), "render_output", job_folder)
                os.makedirs(job_output_path, exist_ok=True)

                if not data.get("leader_ip"):
                    print(f"No leader IP found for job {job_folder}")
                    continue
                leader_ip = data.get("leader_ip")
                leader_url = f"http://{leader_ip}:5050/api/jobs/submit-frames"

                num_frames_sent_leader = 0

                # --- FRAME-BY-FRAME RENDER & UPLOAD ---
                for frame_no in frames:
                    
                    
                    
                    output_template = os.path.join(job_output_path, "#")
                    blender_cmd = [
                        BLENDER_PATH,
                        "--background",
                        os.path.join(folder_path, blend_file),
                        "-o", output_template,
                        "--render-frame", str(frame_no)
                    ]
                    print(f"[+] Rendering frame {frame_no} for job {job_folder}")
                    subprocess.run(blender_cmd, check=True)

                    # File Blender created
                    output_file = os.path.join(job_output_path, f"{frame_no}.png")

                    with open(json_path, 'r') as file:
                        data = json.load(file)
                    
                    if data['status'] != 'in_progress':
                        print(f"[!] Job {job_folder} status changed to {data['status']}. Stopping render.")
                        break
                    
                    # Send frame immediately
                    with open(output_file, "rb") as f:
                        response = requests.post(
                            leader_url,
                            data={"uuid": job_folder, "frame_no": frame_no},
                            files={"image": f},
                            timeout=10
                        )
                        if response.status_code == 200:
                            print(f"[+] Sent frame {frame_no} successfully")
                            num_frames_sent_leader += 1
                        else:
                            print(f"[!] Failed to send frame {frame_no}: {response.text}")

                print('All frames processed. Deleting temporary folders')
                if os.path.exists('render_output'):
                    shutil.rmtree('render_output')

                # if i am not the leader, no need to update status to completed
                if discovery.local_ip != data.get("leader_ip"):
                    data['status'] = 'completed'
                    json_output = json.dumps(data, indent = 4)

                    # Marking status as completed in local json file
                    with open(json_path, 'w') as file:
                        file.write(json_output)
 
                # Finished all frames for this node
                processed_blender_jobs.append(job_folder)

        except Exception as e:
            print("[!] Error in render loop:", e)

        time.sleep(1)

# ==========================================
# FFMPEG METADATA HANDLER
# ==========================================
class MetadataJsonHandler(FileSystemEventHandler):
    def __init__(self):
        # Track last known status per job
        self.last_status = {}

    def on_modified(self, event):
        if event.is_directory:
            return

        if not event.src_path.endswith(JSON_FILENAME):
            return

        json_path = event.src_path
        job_folder = os.path.basename(os.path.dirname(json_path))

        if job_folder.endswith("_reassign"):
            print(f"[+] Detected reassigned job folder: {job_folder}")
            old_job_folder = job_folder.rsplit("_reassign", 1)[0]
            print(f"[+] Old job folder: {old_job_folder}")

            new_metadata_path = os.path.join(WATCH_DIR, job_folder, JSON_FILENAME)
            print(f"[+] New metadata path: {new_metadata_path}")
            if os.path.exists(new_metadata_path):
                with open(new_metadata_path, "r", encoding="utf-8") as f:
                    print("[+] Reading new metadata file")
                    new_data = json.load(f)
            
                print(f"[+] New job data loaded: {new_data}")
                if new_data.get("status") == "completed_frames":
                    old_renders_path = os.path.join(WATCH_DIR, old_job_folder, "renders")
                    new_renders_path = os.path.join(WATCH_DIR, job_folder, "renders")
                    if os.path.exists(old_renders_path):
                        shutil.copytree(old_renders_path, new_renders_path, dirs_exist_ok=True)
                        print(f"[+] Copied renders from {old_renders_path} to {new_renders_path} for reassigned job {job_folder}")
                    
                    self.on_job_completed(job_folder, new_data)
                    new_data["status"] = "completed_video"
                    with open(new_metadata_path, "w", encoding="utf-8") as f:
                        json.dump(new_data, f, indent=4)

                    old_metadata_path = os.path.join(WATCH_DIR, old_job_folder, JSON_FILENAME)
                    try:
                        with open(old_metadata_path, "r", encoding="utf-8") as f:
                            old_data = json.load(f)
                        old_data["status"] = "canceled"
                        with open(old_metadata_path, "w", encoding="utf-8") as f:
                            json.dump(old_data, f, indent=4)
                        print(f"[+] Updated status to 'canceled' in old job metadata for {old_job_folder}")
                    except Exception as e:
                        print(f"[!] Error updating old job metadata for {old_job_folder}: {e}")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            new_status = data.get("status")
            old_status = self.last_status.get(job_folder)

            if new_status != old_status:
                print(f"[🔔] Job {job_folder} status changed: {old_status} → {new_status}")
                self.last_status[job_folder] = new_status

                # ---- react to specific status ----
                if new_status == "completed_frames":
                    self.on_job_completed(job_folder, data)
                
                    # ----- Update metadata.json to completed_video -----
                    data["status"] = "completed_video"
                    json_output = json.dumps(data, indent = 4)

                    # Marking status as completed in local json file
                    with open(json_path, 'w') as file:
                        file.write(json_output) 
                    
                    if not data.get("leader_ip"):
                        print(f"No leader IP found for job {job_folder}")

                    client_ip = data.get("metadata").get("initiator_client_ip")
                    client_url = f"http://{client_ip}:5050/api/jobs/send-video-to-client"

                    video_path = os.path.join("jobs", job_folder, "renders", "output_video.mp4")

                    with open(video_path, "rb") as video_file:
                        response = requests.post(
                            client_url,
                            data={
                                "uuid": job_folder,
                                "status": new_status,
                                "client_ip": client_ip
                            },
                            files={
                                "video": ("output_video.mp4", video_file, "video/mp4")
                            },
                            timeout=30
                        )

                        if response.status_code == 200:
                            print(f"[✅] Sent final video to client {client_ip} for job {job_folder}")
                        else:
                            print(f"[!] Failed to send final video to client {client_ip} for job {job_folder}: {response.text}")
                    
                    print(f"[+] Notified leader {client_ip} of status change for job {job_folder}")
                
        except Exception as e:
            print(f"[!] Error reading {json_path}: {e}")

    def on_job_completed(self, job_folder, data):
        print(f"[+] Detected job {job_folder} completion, starting video stitching")
        try:
            frames_dir = os.path.join("jobs", job_folder, "renders")
            output_video = os.path.join(frames_dir, "output_video.mp4")
            fps = data["metadata"].get("fps", 24)
            
            if discovery.blend_operation_cancelled:
                print(f"[!] Video stitching cancelled for job {job_folder}. Exiting stitching process.")
                discovery.blend_operation_cancelled = False
                return 

            stitch_pngs_to_video(frames_dir, output_video, fps)

            print(f"[✅] Video stitched for job {job_folder}: {output_video}")

        except Exception as e:
            print(f"[!] Error stitching video for job {job_folder}: {e}")
            return
        print(f"[✅] Job {job_folder} fully completed")
        # do cleanup, notify server, etc.


# ==========================================
# MAIN
# ==========================================

def main():
    observer = Observer()
    
    folder_handler = FolderHandler()
    metadata_handler = MetadataJsonHandler()

    observer.schedule(folder_handler, WATCH_DIR, recursive=False)
    observer.schedule(metadata_handler, WATCH_DIR, recursive=True)
    
    observer.start()
    print(f"[+] Watching directory: {WATCH_DIR}")

    # Start render loop in background thread
    render_thread = Thread(target=render_in_progress_jobs, daemon=True)
    render_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[+] Shutting down watcher...")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()