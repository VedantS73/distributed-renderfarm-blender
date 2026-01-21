import time
import json
import os
import shutil
import requests
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from backend.shared.state import discovery

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
            workers = int(data["no_of_workers"])
            if not data["metadata"].get("initiator_is_participant", True):
                workers -= 1

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

                my_id = discovery.local_ip
                frames = []
                for worker_id, frame_list in data["jobs"].items():
                    if worker_id == str(my_id):
                        frames = frame_list
                        break

                if not frames:
                    print(f"No frames assigned to this node for job {job_folder}")
                    continue

                # Render frames
                job_output_path = os.path.join(os.getcwd(), "render_output", job_folder)
                if os.path.exists(job_output_path):
                    shutil.rmtree(job_output_path)
                os.makedirs(job_output_path)

                frame_list_str = ",".join(map(str, frames))
                output_path = os.path.join(job_output_path, "#.png")
                print(f"[+] Rendering frames: {frame_list_str}")
                os.system(f"blender --background {os.path.join(folder_path, blend_file)} -o {output_path} --render-frame {frame_list_str}")

                # Send to leader
                leader_ip = discovery.get_election_status()["current_leader"]
                leader_url = f"http://{leader_ip}:5050/api/jobs/submit-frames"
                files = {f: open(os.path.join(job_output_path, f), "rb") for f in os.listdir(job_output_path)}
                requests.post(leader_url, files=files)
                print(f"[+] Sent rendered frames of job {job_folder} to leader")

                # Mark completed
                data["status"] = "completed"
                with open(json_path, "w") as f:
                    json.dump(data, f, indent=4)
                
                processed_blender_jobs.append(job_folder)

        except Exception as e:
            print("[!] Error in render loop:", e)

        time.sleep(1)

# ==========================================
# MAIN
# ==========================================

def main():
    observer = Observer()
    handler = FolderHandler()
    observer.schedule(handler, WATCH_DIR, recursive=False)
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