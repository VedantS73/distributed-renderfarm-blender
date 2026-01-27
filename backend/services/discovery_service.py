import socket
import threading
import time
import platform
import netifaces
import psutil
import os
import json
from datetime import datetime
from .blender_service import BlenderService
class NetworkDiscoveryService:
    def __init__(self):
        self.broadcast_port = 8888
        self.file_transfer_port = 8889
        self.running = False
        self.socket = None
        self.discovered_devices = {}
        self.pc_name = platform.node()
        self.local_ip = self.get_local_ip()
        self.broadcast_thread = None
        self.listen_thread = None
        
        # File transfer server
        self.file_server_thread = None
        self.file_server_socket = None
        
        # Render tracking
        self.render_jobs = {}  # {job_id: {file, status, progress, assigned_to}}
        self.my_render_tasks = []  # Tasks assigned to this node
        
        # Initial score calculation
        self.current_score = 0
        self.ring_topology = []
        
        # LCR / Election State
        self.ring_successor = "Undefined"
        self.current_leader = None
        self.election_active = False
        self.election_results = None
        self.participant = False
        self.my_role = "Undefined"
        
        # Upload tracking
        self.current_blend_file = {
            "file_name": None,
            "filepath": None,
            "scene_name": None,
            "start_frame": None,
            "end_frame": None,
            "samples": None,
            "engine": None,
            "res_x": None,
            "res_y": None,
            "output_format": None
        }

        self.upload_status = {
            "uploading": False,
            "progress": 0,
            "filename": None,
            "error": None
        }

    def get_local_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "127.0.0.1"

    def get_resource_score(self):
        """Calculates Composite ID component: Resource_Score"""
        try:
            ram = psutil.virtual_memory()
            cpu_usage = psutil.cpu_percent(interval=0.1)
            disk = psutil.disk_usage('/')
            
            disk_score = disk.free / (1024**3) * 50  # GB * 50
            ram_score = ram.available / (1024**3) * 30  # GB * 30
            cpu_score = (100 - cpu_usage) * 30
            
            return int(ram_score + cpu_score + disk_score)
        except:
            return 10

    def get_broadcast_addresses(self):
        """Get all broadcast addresses for network interfaces"""
        broadcast_addresses = ['255.255.255.255']
        try:
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for link in addrs[netifaces.AF_INET]:
                        if 'broadcast' in link:
                            broadcast_addresses.append(link['broadcast'])
        except:
            pass
        return broadcast_addresses

    def start(self):
        if self.running:
            return True, "Already running"
        
        try:
            # UDP broadcast socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            if platform.system() == 'Darwin':
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            
            self.socket.bind(('', self.broadcast_port))
            self.running = True
            
            # Add self to discovery list
            self.current_score = self.get_resource_score()
            self.add_device(self.pc_name, self.local_ip, self.current_score, role="Undefined")
            
            # Start threads
            self.broadcast_thread = threading.Thread(target=self.broadcast_loop, daemon=True)
            self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.file_server_thread = threading.Thread(target=self.file_server_loop, daemon=True)
            
            self.broadcast_thread.start()
            self.listen_thread.start()
            self.file_server_thread.start()
            
            return True, "Discovery Service Started"
        except Exception as e:
            return False, str(e)

    def stop(self):
        """Stops all services and clears all internal state data."""
        self.running = False
        
        # 1. Close Network Sockets
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
            
        if self.file_server_socket:
            try:
                self.file_server_socket.close()
            except:
                pass
            self.file_server_socket = None

        # 2. Reset Election & Role State
        self.election_active = False
        self.current_leader = None
        self.my_role = "Undefined"
        self.ring_successor = "Undefined"
        self.participant = False
        self.election_results = None
        
        # 3. Clear Discovered Data
        self.discovered_devices = {}
        self.ring_topology = []
        
        # 4. Clear Render and File State
        self.render_jobs = {}
        self.my_render_tasks = []
        
        # 5. Reset Upload Buffers
        self.current_blend_file = {
            "file_name": None, "filepath": None, "scene_name": None,
            "start_frame": None, "end_frame": None, "samples": None,
            "engine": None, "res_x": None, "res_y": None, "output_format": None
        }

        self.upload_status = {
            "uploading": False,
            "progress": 0,
            "filename": None,
            "error": None
        }
        
        print(f"[{self.local_ip}] Discovery Service stopped and state cleared.")

    def broadcast_loop(self):
        """Broadcasts UDP Beacons every 3 seconds"""
        while self.running:
            try:
                self.current_score = self.get_resource_score()
                msg = f"DISCOVER:{self.pc_name}:{self.local_ip}:{self.current_score}:{self.my_role}"
                
                for addr in self.get_broadcast_addresses():
                    self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
                
                time.sleep(3)
            except:
                time.sleep(3)

    def listen_loop(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                msg = data.decode()
                # print("incoming packet:", msg)
                
                if msg.startswith("DISCOVER:"):
                    parts = msg.split(":")
                    if len(parts) >= 4:
                        name = parts[1]
                        ip = parts[2]
                        score = int(parts[3])
                        role = parts[4] if len(parts) >= 5 else "Undefined"
                        
                        self.add_device(name, ip, score, role=role)
                
                elif msg.startswith("ELECTION_INIT:"):
                    print("Election initiation message received .")
                    print(msg)
                    parts = msg.split(":")
                    if len(parts) >= 3:
                        initiator_ip = parts[1]
                        
                        self.participant = False
                        self.election_active = True
                        self.current_leader = None
                        
                        # if initiator_ip != self.local_ip:
                        #     self.run_election_simulation()
                
                elif msg.startswith("LCR_TOKEN:"):
                    print("LCR token message received.")
                    print(msg)
                    parts = msg.split(":")
                    if len(parts) >= 4:
                        mid_score = int(parts[1])
                        mid_ip = parts[2]
                        is_leader = parts[3] == "True"
                        self.handle_lcr_token(mid_score, mid_ip, is_leader)
                
                elif msg.startswith("POP_STALE_LEADER:"):
                    print("Removing Stale Leader.")
                    parts = msg.split(":")
                    if len(parts) >= 2:
                        stale_ip = parts[1]
                        if stale_ip in self.discovered_devices:
                            del self.discovered_devices[stale_ip]
                            print(f"[{self.local_ip}] Removed stale leader: {stale_ip}")
                            print("Current discovered devices:", self.get_devices())
                            self.calculate_ring_topology()
                            print("Updated ring topology:", self.ring_topology)
            except:
                continue

    def file_server_loop(self):
        """TCP server for receiving file uploads"""
        try:
            self.file_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.file_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.file_server_socket.bind(('', self.file_transfer_port))
            self.file_server_socket.listen(5)
            
            print(f"[{self.local_ip}] File server listening on port {self.file_transfer_port}")
            
            while self.running:
                try:
                    self.file_server_socket.settimeout(1.0)
                    conn, addr = self.file_server_socket.accept()
                    threading.Thread(target=self.handle_file_upload, args=(conn, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except:
                    break
        except Exception as e:
            print(f"[{self.local_ip}] File server error: {e}")

    def handle_file_upload(self, conn, addr):
        """Handles incoming file upload from a worker node"""
        try:
            # Receive metadata first (JSON)
            metadata_size = int.from_bytes(conn.recv(4), 'big')
            metadata_json = conn.recv(metadata_size).decode()
            metadata = json.loads(metadata_json)
            
            filename = metadata['filename']
            filesize = metadata['filesize']
            job_id = metadata.get('job_id', 'unknown')
            
            print(f"[{self.local_ip}] Receiving file: {filename} ({filesize} bytes) from {addr[0]}")
            
            # Create uploads directory if it doesn't exist
            upload_dir = "uploads"
            os.makedirs(upload_dir, exist_ok=True)
            
            filepath = os.path.join(upload_dir, filename)

            # clear existing file if any
            if os.path.exists(filepath):
                os.remove(filepath)
            
            # Receive file data
            received = 0
            with open(filepath, 'wb') as f:
                while received < filesize:
                    chunk = conn.recv(min(8192, filesize - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            
            # Send acknowledgment
            response = json.dumps({"status": "success", "received": received})
            conn.sendall(response.encode())
            
            print(f"[{self.local_ip}] File received successfully: {filepath}")
            
            # If this is the leader, create a render job
            if self.my_role == "Leader":
                self.create_render_job(job_id, filename, filepath, addr[0])
            
        except Exception as e:
            print(f"[{self.local_ip}] Error handling file upload: {e}")
            try:
                error_response = json.dumps({"status": "error", "message": str(e)})
                conn.sendall(error_response.encode())
            except:
                pass
        finally:
            conn.close()

    def upload_blender_file(self, filepath):
        """Upload a Blender file to the leader node"""
        if not os.path.exists(filepath):
            return {"success": False, "error": "File not found"}
        
        if self.my_role == "Leader":
            # store in uploads directory
            upload_dir = "uploads"
            os.makedirs(upload_dir, exist_ok=True)
            dest_path = os.path.join(upload_dir, os.path.basename(filepath))
            with open(filepath, 'rb') as src_file:
                with open(dest_path, 'wb') as dest_file:
                    dest_file.write(src_file.read())
            
            self.current_blend_file = {
                "filename": os.path.basename(filepath),
                "filepath": dest_path,
                "info": None  # You might want to extract blend info here if needed
            }
            print(f"[{self.local_ip}] Analyzed Blender file info: {blend_info}")
            
            return {"success": False, "error": "I am the leader, no need to upload"}
        
        if not self.current_leader:
            return {"success": False, "error": "No leader elected yet"}
        
        try:
            self.upload_status["uploading"] = True
            self.upload_status["progress"] = 0
            self.upload_status["filename"] = os.path.basename(filepath)
            self.upload_status["error"] = None
            
            # Connect to leader's file server
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.current_leader, self.file_transfer_port))
            
            # Prepare metadata
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            job_id = f"{self.local_ip}_{int(time.time())}"
            
            metadata = {
                "filename": filename,
                "filesize": filesize,
                "job_id": job_id,
                "sender_ip": self.local_ip,
                "sender_name": self.pc_name
            }
            
            metadata_json = json.dumps(metadata).encode()
            
            # Send metadata size and metadata
            client_socket.sendall(len(metadata_json).to_bytes(4, 'big'))
            client_socket.sendall(metadata_json)
            
            # Send file data
            sent = 0
            with open(filepath, 'rb') as f:
                while sent < filesize:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    client_socket.sendall(chunk)
                    sent += len(chunk)
                    self.upload_status["progress"] = int((sent / filesize) * 100)
            
            # Receive acknowledgment
            response = client_socket.recv(1024).decode()
            result = json.loads(response)
            
            client_socket.close()
            
            self.upload_status["uploading"] = False
            self.upload_status["progress"] = 100

            service = BlenderService()
            blend_info = service.analyze_blend_file(filepath)
            print(f"[{self.local_ip}] Analyzed Blender file info: {blend_info}")

            self.current_blend_file = blend_info
            print(f"[{self.local_ip}] Uploaded Blender file info: {blend_info}")
            
            if result.get("status") == "success":
                return {
                    "success": True,
                    "job_id": job_id,
                    "bytes_sent": sent,
                    "message": f"File uploaded successfully to leader at {self.current_leader}"
                }
            else:
                self.upload_status["error"] = result.get("message", "Unknown error")
                return {"success": False, "error": self.upload_status["error"]}
                
        except Exception as e:
            self.upload_status["uploading"] = False
            self.upload_status["error"] = str(e)
            return {"success": False, "error": str(e)}

    def create_render_job(self, job_id, filename, filepath, uploader_ip):
        """Leader creates a render job and assigns it to workers"""
        if self.my_role != "Leader":
            return
        
        self.render_jobs[job_id] = {
            "job_id": job_id,
            "filename": filename,
            "filepath": filepath,
            "uploader": uploader_ip,
            "status": "pending",
            "progress": 0,
            "assigned_to": None,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None
        }
        
        print(f"[{self.local_ip}] Created render job: {job_id}")
        
        # Auto-assign to best worker (could be improved with load balancing)
        self.assign_render_job(job_id)

    def assign_render_job(self, job_id):
        """Leader assigns a render job to the best available worker"""
        if self.my_role != "Leader" or job_id not in self.render_jobs:
            return
        
        # Find worker with highest resource score
        workers = [d for d in self.discovered_devices.values() if d['ip'] != self.local_ip]
        
        if not workers:
            print(f"[{self.local_ip}] No workers available for job {job_id}")
            return
        
        best_worker = max(workers, key=lambda w: w['resource_score'])
        
        self.render_jobs[job_id]['assigned_to'] = best_worker['ip']
        self.render_jobs[job_id]['status'] = 'assigned'
        
        print(f"[{self.local_ip}] Assigned job {job_id} to {best_worker['name']} ({best_worker['ip']})")
        
        # Broadcast job assignment
        self.broadcast_render_job(job_id)

    def broadcast_render_job(self, job_id):
        """Broadcast render job status update"""
        if job_id not in self.render_jobs:
            return
        
        job = self.render_jobs[job_id]
        msg = f"RENDER_JOB:{job_id}:{job['assigned_to']}:{job['status']}:{job['progress']}"
        
        try:
            for addr in self.get_broadcast_addresses():
                self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
        except Exception as e:
            print(f"[{self.local_ip}] Error broadcasting render job: {e}")

    def update_render_job(self, job_id, worker_ip, status, progress):
        """Update render job status (called when receiving updates)"""
        if job_id in self.render_jobs:
            self.render_jobs[job_id]['status'] = status
            self.render_jobs[job_id]['progress'] = progress
            
            if status == 'rendering' and not self.render_jobs[job_id]['started_at']:
                self.render_jobs[job_id]['started_at'] = datetime.now().isoformat()
            elif status == 'completed':
                self.render_jobs[job_id]['completed_at'] = datetime.now().isoformat()

    def get_upload_status(self):
        """Get current upload status"""
        return self.upload_status.copy()

    def get_render_status(self):
        """Get render job status"""
        return {
            "my_role": self.my_role,
            "jobs": list(self.render_jobs.values()) if self.my_role == "Leader" else [],
            "my_tasks": self.my_render_tasks
        }

    def add_device(self, name, ip, score, role="Undefined"):
        self.discovered_devices[ip] = {
            "name": name,
            "ip": ip,
            "resource_score": score,
            "last_seen": int(time.time()),
            "my_role": role
        }

    def get_devices(self):
        return list(self.discovered_devices.values())
    
    def pop_key_from_discovered(self, key):
        if key in self.discovered_devices:
            del self.discovered_devices[key]
            msg = f"POP_STALE_LEADER:{key}"
            for addr in self.get_broadcast_addresses():
                if addr.startswith('255') or addr.startswith('127'):
                    continue
                try:
                    self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
                except:
                    pass
            print(f"Force broadcasted removal of stale leader: {key}")
            time.sleep(3)
    
    def calculate_ring_topology(self):
        all_nodes = sorted(self.discovered_devices.keys())
        try:
            my_index = all_nodes.index(self.local_ip)
            successor_ip = all_nodes[(my_index + 1) % len(all_nodes)]
            self.ring_successor = successor_ip
        except ValueError:
            self.ring_successor = self.local_ip
        
        self.ring_topology = []
        for idx, ip in enumerate(all_nodes):
            self.ring_topology.append({
                "position": idx + 1,
                "ip": ip,
                "name": self.discovered_devices[ip]['name'],
                "resource_score": self.discovered_devices[ip]['resource_score']
            })
        return all_nodes

    def initiate_election(self):
        # 1. RESET STATE FORCEFULLY
        self.participant = False
        self.current_leader = None
        self.election_active = True
        self.my_role = "Worker" # Default to worker until won
        
        print(f"[{self.local_ip}] Initiating Election...")

        try:
            msg = f"ELECTION_INIT:{self.local_ip}:{self.pc_name}"
            #print(self.get_broadcast_addresses())
            # 2. BROADCAST FIRST
            for addr in self.get_broadcast_addresses():
                # address starting with 255 is global broadcast, 127 is loopback broadcast. Ignore both
                if addr.startswith('255') or addr.startswith('127'):
                    continue
                try:
                    self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
                except:
                    pass
            
            # 3. RUN SIMULATION ONCE (Outside Loop)
            # Add a tiny delay to allow other nodes to receive the INIT message 
            # and reset their state before we send the first token.
            time.sleep(0.5) 
            self.run_election_simulation()
                
        except Exception as e:
            print(f"Error broadcasting election initiation: {e}")

    def run_election_simulation(self):
        print("=" * 60)
        print("LEADER ELECTION SIMULATION HAS BEEN INITIATED")
        print("=" * 60)
        
        ring_order_ips = self.calculate_ring_topology()
        print(f"[{self.local_ip}] Ring Order IPs: {ring_order_ips}")
        
        if len(ring_order_ips) == 0:
            return None
        
        successor_index = (ring_order_ips.index(self.local_ip) + 1) % len(ring_order_ips)
        self.ring_successor = ring_order_ips[successor_index]
        print(f"[{self.local_ip}] Successor IP: {self.ring_successor}")

        if self.ring_successor == self.local_ip:
            print(f"[{self.local_ip}] Only node in ring. declaring self leader.")
            self.current_leader = self.local_ip
            self.my_role = "Leader"
            self.election_active = False
            # self.broadcast_election_result(self.local_ip, self.pc_name)
            return
              
        if not self.participant:
            self.participant = True
            self.send_lcr_token(self.current_score, self.local_ip, is_leader=False)
        
        self.election_results = {
            "initiator_ip": self.local_ip,
            "ring_topology": ring_order_ips,
            "successor": self.ring_successor
        }
        return self.election_results

    def send_lcr_token(self, mid_score, mid_ip, is_leader):
        if self.ring_successor == "Undefined":
            ring_order_ips = self.calculate_ring_topology()
            successor_index = (ring_order_ips.index(self.local_ip) + 1) % len(ring_order_ips)
            self.ring_successor = ring_order_ips[successor_index]
        try:
            msg = f"LCR_TOKEN:{mid_score}:{mid_ip}:{is_leader}"
            # Send 3 times to ensure delivery (UDP redundancy)
            for _ in range(1):
                print("Sending LCR token to " + self.ring_successor)
                self.socket.sendto(msg.encode(), (self.ring_successor, self.broadcast_port))
                time.sleep(0.05) # Tiny gap between bursts
        except Exception as e:
            print(f"[{self.local_ip}] Error sending LCR token: {e}")

    def handle_lcr_token(self, mid_score, mid_ip, is_leader):
        mid_uid = (mid_score, mid_ip)
        my_uid = (self.current_score, self.local_ip)
        
        if is_leader:
            self.current_leader = mid_ip
            self.my_role = "Leader" if mid_ip == self.local_ip else "Worker"
            self.participant = False
            print(f"[{self.local_ip}] I have recognized the leader: {mid_ip}")
            if self.ring_successor != self.local_ip and self.my_role != "Leader":
                self.send_lcr_token(mid_score, mid_ip, is_leader=True)
            elif self.my_role == "Leader":
                print(f"[{self.local_ip}] Election complete. Ending election process.")
            else:
                print(f"[{self.local_ip}] Invalid Condition BEEEEP!.")
            
            self.election_active = False
            # device_name = self.discovered_devices.get(mid_ip, {}).get('name', 'Unknown')
            # self.broadcast_election_result(mid_ip, device_name)
            
        elif mid_uid < my_uid and not self.participant:
            self.participant = True
            self.send_lcr_token(self.current_score, self.local_ip, is_leader=False)
            
        elif mid_uid > my_uid:
            self.participant = True
            self.send_lcr_token(mid_score, mid_ip, is_leader=False)
            
        elif mid_ip == self.local_ip:
            self.current_leader = self.local_ip
            self.my_role = "Leader"
            print(f"[{self.local_ip}] I have won the election and am the Leader.")
            self.participant = False
            self.send_lcr_token(self.current_score, self.local_ip, is_leader=True)
            # self.broadcast_election_result(self.local_ip, self.pc_name)

    # def broadcast_election_result(self, leader_ip, leader_name):
    #     try:
    #         msg = f"ELECTION:{leader_ip}:{leader_name}"
    #         for addr in self.get_broadcast_addresses():
    #             try:
    #                 self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
    #                 self.election_active = False
    #             except:
    #                 pass
    #     except Exception as e:
    #         print(f"Error broadcasting election result: {e}")

    def get_election_status(self):
        leader_consensus = self.verify_leader_consensus()
        topology_with_status = []
        
        for node in self.ring_topology:
            node_data = node.copy()
            node_data['is_leader'] = (node['ip'] == self.current_leader)
            topology_with_status.append(node_data)
        
        return {
            "election_active": self.election_active,
            "current_leader": self.current_leader,
            "my_role": self.my_role,
            "my_ip": self.local_ip,
            "participant": self.participant,
            "ring_successor": self.ring_successor,
            "leader_consensus": leader_consensus,
            "election_results": self.election_results,
            "ring_topology": topology_with_status
        }

    def verify_leader_consensus(self):
        if not self.current_leader:
            return {
                "consensus_reached": False,
                "reason": "No leader elected yet"
            }
        
        return {
            "consensus_reached": self.election_active and self.current_leader is not None,
            "agreed_leader": self.current_leader,
            "total_nodes": len(self.discovered_devices)
        }