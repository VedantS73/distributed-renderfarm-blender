import socket
import threading
import time
import platform
import netifaces
import psutil
import os
from pathlib import Path

import requests
from .sequencer_tcp import SequencerServer, SequencedClient
JOBS_DIR = "jobs"
os.makedirs(JOBS_DIR, exist_ok=True)

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
        self.monitor_thread = None
        
        # File transfer server
        self.file_server_thread = None
        self.file_server_socket = None
        
        # Initial score calculation
        self.current_score = 0
        self.ring_topology = []
        self.blend_operation_cancelled = False
        
        # LCR / Election State
        self.ring_successor = "Undefined"
        self.current_leader = None
        self.election_active = False
        self.election_results = None
        self.participant = False
        self.my_role = "Undefined"
        
        # Sequencer-based control channel (reliable ordered control messages)
        self.control_port = 8890
        self._sequencer_server = None
        self._sequenced_client = None
        self._control_manager_thread = None
        self._control_manager_running = False
        self._last_known_leader_for_control = None

        # Ordered commit tracking (JOB_COMMIT arrives via Sequencer before/after files)
        self._pending_job_commits = set()
        self._pending_job_lock = threading.Lock()
        
        self._last_score_update_ts = 0
        self._score_update_interval = 10  

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
            self._start_control_manager()

            
            # Add self to discovery list
            self.current_score = self.get_resource_score()
            self.add_device(self.pc_name, self.local_ip, self.current_score, role="Undefined")
            
            # Start threads
            self.broadcast_thread = threading.Thread(target=self.broadcast_loop, daemon=True)
            self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.monitor_thread = threading.Thread(target=self.check_stale_devices, daemon=True)
            
            self.broadcast_thread.start()
            self.listen_thread.start()
            self.monitor_thread.start()
            
            return True, "Discovery Service Started"
        except Exception as e:
            return False, str(e)

    def stop(self):
        """Stops all services and clears all internal state data."""
        self.running = False

        # Stop sequencer control channel (TCP ordering) cleanly
        try:
            self._stop_control_manager()
        except:
            pass

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
        
        print(f"[{self.local_ip}] Discovery Service stopped and state cleared.")

    def broadcast_loop(self):
        """Broadcasts UDP Beacons every 3 seconds"""
        while self.running:
            try:
                self.update_resource_score_during_election()
                
                msg = f"DISCOVER:{self.pc_name}:{self.local_ip}:{self.current_score}:{self.my_role}"
                for addr in self.get_broadcast_addresses():
                    if addr.startswith('255') or addr.startswith('127'):
                        continue
                    try:
                        self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
                    except:
                        pass
                
                # print(f"SENDER => detected {self.pc_name} : {self.local_ip}")
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
                        # print(f"LISTENER => detected {name} : {ip}")
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
                        self._control_manager_kick()
                
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

                            jobs_path = Path(JOBS_DIR)
                            if not jobs_path.exists():
                                return

                            for job_folder in jobs_path.iterdir():
                                if not job_folder.is_dir():
                                    continue

                                metadata_file = job_folder / "metadata.json"
                                if not metadata_file.exists():
                                    continue
                                
                                import json

                                try:
                                    with open(metadata_file) as f:
                                        metadata = json.load(f)

                                    if metadata.get("status") == "in_progress":
                                        metadata['status'] = 'canceled'

                                        with open(metadata_file, "w", encoding="utf-8") as f:
                                            json.dump(metadata, f, indent=2) 
                                except Exception as e:
                                    print(f"Error handling leader down for {job_folder.name}: {e}")

                
                elif msg.startswith("CLIENT_DISCONNECTED"):
                    print("Client Disconnected received.")
                    continue
                    
            except:
                continue
    
    def update_resource_score_during_election(self):
        now = time.time()

        if self.election_active:
            return

        if now - self._last_score_update_ts >= self._score_update_interval:
            self.current_score = self.get_resource_score()
            self._last_score_update_ts = now

    def add_device(self, name, ip, score, role="Undefined"):
        if ip in self.discovered_devices:
            self.discovered_devices[ip]["last_seen"] = int(time.time())
            self.discovered_devices[ip]["my_role"] = role
            if not self.election_active:
                self.discovered_devices[ip]["resource_score"] = score
        else:
            self.discovered_devices[ip] = {
                "name": name,
                "ip": ip,
                "resource_score": score,
                "last_seen": int(time.time()),
                "my_role": role
            }

    def get_devices(self):
        return list(self.discovered_devices.values())
    
    def check_stale_devices(self):
        while self.running:
            try:
                current_time = int(time.time())
                stale_devices = []
                leader_went_down = False
                down_leader_ip = None

                for ip, device in list(self.discovered_devices.items()):
                    if ip == self.local_ip:
                        continue

                    last_seen = device.get('last_seen', 0)
                    if current_time - last_seen > 10:
                        stale_devices.append(ip)
                        print(f"[{self.local_ip}] Device {device['name']} ({ip}) is stale")

                for stale_ip in stale_devices:
                    # del self.discovered_devices[stale_ip]
                    print(f"[{self.local_ip}] Removed stale device: {stale_ip}")

                    if stale_ip == self.current_leader:
                        leader_went_down = True
                        down_leader_ip = stale_ip
                    else:
                        requests.post(f"http://{self.current_leader}:5050/api/election/notify_node_disconnection", json={"ip": stale_ip})

                # Recalculate topology ONCE
                if stale_devices:
                    self.calculate_ring_topology()

                # Handle leader-down logic OUTSIDE loop
                if leader_went_down:
                    self.my_role = "Undefined"
                    self.handle_leader_down(down_leader_ip)

            except Exception as e:
                print(f"[{self.local_ip}] Error in stale device check: {e}")

            time.sleep(2)
    
    def handle_leader_down(self, leader_ip):
        print("THE LEADER IS DOWN ACCORDING TO DISCOVERY SERVICE")
        import json
        import requests
        from pathlib import Path

        jobs_path = Path(JOBS_DIR)
        if not jobs_path.exists():
            return

        for job_folder in jobs_path.iterdir():
            if not job_folder.is_dir():
                continue

            metadata_file = job_folder / "metadata.json"
            if not metadata_file.exists():
                continue

            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)

                if metadata.get("status") == "in_progress":
                    job_id = job_folder.name
                    response = requests.post(
                        f"http://{self.local_ip}:5050/api/leader_is_down_flag",
                        data={"job_id": job_id, "ip": leader_ip},
                        timeout=30
                    )
                    print(f"Leader down handler response: {response.status_code}")
                    break

            except Exception as e:
                print(f"Error handling leader down for {job_folder.name}: {e}")

    def pop_key(self, key):
        print(f"Popping device with IP: {key}")
        if key in self.discovered_devices:
            del self.discovered_devices[key]
    
    def pop_leader(self, key):
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
        print("Calculating ring topology with devices: ", self.discovered_devices)
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

    def finalize_job_if_committed(self, job_id):
        """Called after /worker/submit-job to apply any already-received ordered JOB_COMMIT."""
        try:
            self._finalize_job_commit(job_id)
        except Exception:
            pass

    def _finalize_job_commit(self, job_id):
        """If JOB_COMMIT was received for job_id and files are present, mark it committed locally."""
        with self._pending_job_lock:
            if job_id not in self._pending_job_commits:
                return

        # Only finalize if metadata exists locally
        meta_path = Path(JOBS_DIR) / job_id / "metadata.json"
        if not meta_path.exists():
            return

        try:
            from backend.api.worker import commit_job_local
            commit_job_local(job_id=job_id, assigned_worker_ip=self.local_ip)
        except Exception:
            return

        with self._pending_job_lock:
            self._pending_job_commits.discard(job_id)

    def _control_manager_kick(self):
        # Force manager to react on next tick
        self._last_known_leader_for_control = None

    # ==========================================
    # SEQUENCER-BASED CONTROL CHANNEL
    # ==========================================

    def _start_control_manager(self):
        if self._control_manager_running:
            return
        self._control_manager_running = True
        self._control_manager_thread = threading.Thread(target=self._control_manager_loop, daemon=True)
        self._control_manager_thread.start()

    def _stop_control_manager(self):
        self._control_manager_running = False

        try:
            if self._sequenced_client:
                self._sequenced_client.stop()
        except Exception:
            pass
        self._sequenced_client = None

        try:
            if self._sequencer_server:
                self._sequencer_server.stop()
        except Exception:
            pass
        self._sequencer_server = None

        try:
            if self._control_manager_thread and self._control_manager_thread.is_alive():
                self._control_manager_thread.join(timeout=2)
        except Exception:
            pass
        self._control_manager_thread = None

        self._last_known_leader_for_control = None

    def _control_manager_loop(self):
        while self._control_manager_running:
            try:
                leader_ip = self.current_leader
                if leader_ip != self._last_known_leader_for_control:
                    self._last_known_leader_for_control = leader_ip

                    # If I'm the leader -> run server, otherwise connect as client
                    if leader_ip and leader_ip == self.local_ip:
                        self._become_leader_control()
                    else:
                        self._become_worker_control(leader_ip)
            except Exception:
                pass
            time.sleep(1.0)

    def _become_leader_control(self):
        # Stop client if any
        try:
            if self._sequenced_client:
                self._sequenced_client.stop()
        except Exception:
            pass
        self._sequenced_client = None

        # Start server (idempotent)
        if self._sequencer_server is None:
            try:
                self._sequencer_server = SequencerServer(host=self.local_ip, port=self.control_port)
                self._sequencer_server.start()
                print(f"[{self.local_ip}] Sequencer TCP server started on port {self.control_port}")
            except Exception as e:
                print(f"[{self.local_ip}] Failed to start Sequencer TCP server: {e}")
                self._sequencer_server = None

    def _become_worker_control(self, leader_ip):
        # Stop server if any
        try:
            if self._sequencer_server:
                self._sequencer_server.stop()
        except Exception:
            pass
        self._sequencer_server = None

        # Start / re-start client if leader exists
        if not leader_ip:
            try:
                if self._sequenced_client:
                    self._sequenced_client.stop()
            except Exception:
                pass
            self._sequenced_client = None
            return

        if self._sequenced_client is None or self._sequenced_client.leader_host != leader_ip:
            try:
                if self._sequenced_client:
                    self._sequenced_client.stop()
            except Exception:
                pass
            self._sequenced_client = SequencedClient(
                leader_host=leader_ip,
                leader_port=self.control_port,
                on_message=self._handle_control_message
            )
            self._sequenced_client.start()
            print(f"[{self.local_ip}] Connected to Sequencer leader {leader_ip}:{self.control_port}")

    def broadcast_control_message(self, msg_type, payload):
        """
        Reliable ordered broadcast (leader only).
        Returns (ok: bool, seq: int | None, message: str)
        """
        if self.current_leader != self.local_ip or self._sequencer_server is None:
            return False, None, "Not leader or sequencer not running"
        try:
            seq = self._sequencer_server.broadcast_control(msg_type, payload or {})
            return True, seq, "Sent"
        except Exception as e:
            return False, None, str(e)


    def _handle_control_message(self, msg):
        """Worker-side dispatch for ordered control messages."""
        try:
            msg_type = msg.get("type")
            payload = msg.get("payload") or {}

            if msg_type == "JOB_COMMIT":
                print("JOB_COMMIT received")
                job_id = payload.get("job_id")
                if job_id:
                    with self._pending_job_lock:
                        self._pending_job_commits.add(job_id)
                    # If files already arrived, finalize immediately
                    self._finalize_job_commit(job_id)

            elif msg_type == "STOP_RENDER":
                print("STOP_RENDER received")
                job_id = payload.get("job_id")
                worker_ip = []
                if job_id:
                    print("STOP_RENDER triggered. Stopping rendering",job_id)
                    from backend.api.worker import stop_render_local
                    stop_render_local(job_id=job_id, worker_ip=worker_ip)

            elif msg_type == "CANCEL_JOB":
                print("CANCEL_JOB received")
                job_id = payload.get("job_id")
                print("CANCEL_JOB triggered. Cancelling rendering")
                if job_id:
                    from backend.api.worker import cancel_job_local
                    cancel_job_local(job_id=job_id)

            elif msg_type == "CANCEL_ALL":
                print("CANCEL_ALL received")
                from backend.api.worker import cancel_all_local
                cancel_all_local()

            elif msg_type == "JOB_CREATED":
                print("JOB_CREATED received")
                pass
            else:
                print("Invalid Message received", msg_type)    

        except Exception:
            pass

    def initiate_election(self):
        # 1. RESET STATE FORCEFULLY
        self.participant = False
        self.current_leader = None
        self._control_manager_kick()
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
            self._control_manager_kick()
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
        
        print("Ring Topology " , self.ring_topology)
        print("LCR Received UUID ", mid_uid, ". My UUID ", my_uid)
        if is_leader:
            self.current_leader = mid_ip
            self._control_manager_kick()
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

        elif mid_ip == self.local_ip:
            self.current_leader = self.local_ip
            self._control_manager_kick()
            self.my_role = "Leader"
            print(f"[{self.local_ip}] I have won the election and am the Leader.")
            self.participant = False
            self.send_lcr_token(self.current_score, self.local_ip, is_leader=True)

        elif mid_uid < my_uid and not self.participant:
            self.participant = True
            self.send_lcr_token(self.current_score, self.local_ip, is_leader=False)
            
        elif mid_uid > my_uid:
            self.participant = True
            self.send_lcr_token(mid_score, mid_ip, is_leader=False)
            

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
    
    def send_client_disconnection(self):
        msg = f"CLIENT_DISCONNECTED"
        try:
            for addr in self.get_broadcast_addresses():
                if addr.startswith('255') or addr.startswith('127'):
                    continue
                self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
            print(f"[{self.local_ip}] Broadcasted client disconnection message.")
        except Exception as e:
            print(f"[{self.local_ip}] Error broadcasting client disconnection: {e}")

        # ALSO issue an ordered cancel via sequencer (leader only), so workers apply deterministically.
        try:
            if self.my_role == "Leader":
                ok, seq, info = self.broadcast_control_message("CANCEL_ALL", {})
                if ok:
                    print(f"[{self.local_ip}] Ordered CANCEL_ALL sent (seq={seq})")
                else:
                    print(f"[{self.local_ip}] Failed to send ordered CANCEL_ALL: {info}")
        except:
            pass
