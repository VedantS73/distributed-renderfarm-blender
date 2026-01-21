import time
import json
import os
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_DIR = "jobs"
SERVER_URL = "http://localhost:5050/api/jobs/broadcast-to-workers"
JSON_FILENAME = "metadata.json"

# ==========================================


class FolderHandler(FileSystemEventHandler):

    def on_created(self, event):
        # Only react to new directories
        if not event.is_directory:
            return

        folder_path = event.src_path
        print(f"[+] New folder detected: {folder_path}")

        # Give filesystem time to finish writes
        time.sleep(1)

        json_path = os.path.join(folder_path, JSON_FILENAME)

        if not os.path.exists(json_path):
            print("[-] metadata.json not found, ignoring folder")
            return

        try:
            #READ JSON --------
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            #STATUS CHECK --------
            if data.get("status") != "created":
                print(f"[-] Job status is '{data.get('status')}', skipping")
                return

            #VALIDATION --------
            frame_start = int(data["metadata"]["frame_start"])
            frame_end = int(data["metadata"]["frame_end"])
            workers = int(data["no_of_workers"])

            if data["initiator_is_participant"]== False:
                workers-=1

            if frame_end < frame_start or workers <= 0:
                print("[!] Invalid frame range or worker count")
                return

            # -------- FRAME SPLITTING --------
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

            # -------- UPDATE JSON --------
            data["status"] = "in_progress"
            data["jobs"] = jobs

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            # -------- SEND HTTP --------
            # response = requests.post(SERVER_URL, json=data, timeout=5)
            response = requests.post(SERVER_URL, json={"uuid": os.path.basename(folder_path)}, timeout=5)
            response.raise_for_status()

            print("[+] Job accepted, split, and sent to server")

        except json.JSONDecodeError as e:
            print("[!] JSON parse error:", e)

        except requests.exceptions.RequestException as e:
            print("[!] HTTP error:", e)

        except Exception as e:
            print("[!] Unexpected error:", e)


def main():
    observer = Observer()
    handler = FolderHandler()

    observer.schedule(handler, WATCH_DIR, recursive=False)
    observer.start()

    print(f"[+] Watching directory: {WATCH_DIR}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[+] Shutting down watcher...")
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()