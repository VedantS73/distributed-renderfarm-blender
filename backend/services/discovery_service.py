import socket
import threading
import time
import platform
import netifaces
import psutil
from datetime import datetime

class NetworkDiscoveryService:
    def __init__(self):
        self.broadcast_port = 8888
        self.running = False
        self.socket = None
        self.discovered_devices = {}
        self.pc_name = platform.node()
        self.local_ip = self.get_local_ip()
        self.broadcast_thread = None
        self.listen_thread = None
        
        # Initial score calculation
        self.current_score = 0
        
        # LCR / Election State
        self.ring_successor = None
        self.current_leader = None
        self.ring_successor = "Undefined"
        self.election_active = False
        self.election_results = None
        self.participant = False
        self.my_role = "Worker"

    def get_local_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "127.0.0.1"

    def get_resource_score(self):
        """
        Calculates Composite ID component: Resource_Score 
        """
        try:
            ram = psutil.virtual_memory()
            cpu_usage = psutil.cpu_percent(interval=0.1)
            disk = psutil.disk_usage('/')
            
            # Simple weighted formula (can be tuned)
            # Higher free RAM/Disk and Lower CPU usage = Higher Score
            disk_score = disk.free * 50
            ram_score = ram.available * 30
            cpu_score = (100 - cpu_usage) * 30
            
            return int(ram_score + cpu_score + disk_score)
        except:
            return 10

    # ... [Existing get_broadcast_addresses and start/stop methods remain the same] ...

    def start(self):
        if self.running: return True, "Already running"
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # macOS fix
            if platform.system() == 'Darwin':
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                
            self.socket.bind(('', self.broadcast_port))
            self.running = True
            
            # Add self to discovery list immediately
            self.current_score = self.get_resource_score()
            self.add_device(self.pc_name, self.local_ip, self.current_score)

            self.broadcast_thread = threading.Thread(target=self.broadcast_loop, daemon=True)
            self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.broadcast_thread.start()
            self.listen_thread.start()
            
            return True, "Discovery Service Started"
        except Exception as e:
            return False, str(e)

    def stop(self):
        self.running = False
        self.election_active = False
        self.current_leader = None
        self.my_role = "Worker"
        self.ring_successor = "Undefined"
        self.election_results = None

        if self.socket: self.socket.close()

    def broadcast_loop(self):
        """Broadcasts UDP Beacons every 3 seconds [cite: 25]"""
        while self.running:
            try:
                self.current_score = self.get_resource_score()
                # Payload: DISCOVER:NAME:IP:SCORE
                msg = f"DISCOVER:{self.pc_name}:{self.local_ip}:{self.current_score}"
                
                for addr in self.get_broadcast_addresses():
                    self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
                
                time.sleep(3) 
            except:
                time.sleep(3)

    def listen_loop(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                msg = data.decode()
                
                if msg.startswith("DISCOVER:"):
                    parts = msg.split(":")
                    if len(parts) >= 4:
                        name, ip, score = parts[1], parts[2], int(parts[3])
                        self.add_device(name, ip, score)
                
                elif msg.startswith("ELECTION_INIT:"):
                    # Format: ELECTION_INIT:INITIATOR_IP:INITIATOR_NAME
                    parts = msg.split(":")
                    if len(parts) >= 3:
                        initiator_ip = parts[1]
                        # Don't process my own election initiation broadcast
                        if initiator_ip != self.local_ip:
                            # Run election simulation when receiving init from another node
                            self.run_election_simulation()
            
                elif msg.startswith("LCR_TOKEN:"):
                    # Format: LCR_TOKEN:MID_SCORE:MID_IP:IS_LEADER
                    parts = msg.split(":")
                    if len(parts) >= 4:
                        mid_score = int(parts[1])
                        mid_ip = parts[2]
                        is_leader = parts[3] == "True"
                        self.handle_lcr_token(mid_score, mid_ip, is_leader)
            
                elif msg.startswith("ELECTION:"):
                    # Format: ELECTION:LEADER_IP:LEADER_NAME
                    parts = msg.split(":")
                    if len(parts) >= 3:
                        leader_ip, leader_name = parts[1], parts[2]
                        self.current_leader = leader_ip
                        self.my_role = "Leader" if leader_ip == self.local_ip else "Worker"
                        self.election_active = True
                            
            except:
                continue

    def add_device(self, name, ip, score):
        self.discovered_devices[ip] = {
            "name": name,
            "ip": ip,
            "resource_score": score,
            "last_seen": int(time.time()),
        }

    def get_devices(self):
        return list(self.discovered_devices.values())

    # --- NEW LCR ELECTION LOGIC ---

    def calculate_ring_topology(self):
        """
        Establishes the logical unidirectional ring.
        Nodes are sorted by Unique ID (IP) to form the ring structure.
        """
        # Get all active IPs and sort them to form a consistent ring
        all_nodes = sorted(self.discovered_devices.keys())
        
        # Find my index in the ring
        try:
            my_index = all_nodes.index(self.local_ip)
            # Successor is the next node in the list (or wrap around to 0)
            successor_ip = all_nodes[(my_index + 1) % len(all_nodes)]
            self.ring_successor = successor_ip
        except ValueError:
            self.ring_successor = self.local_ip
            print(f"[{self.local_ip}] Could not find my IP in the ring. Setting successor to self.")
        return all_nodes

    def initiate_election(self):
        """
        Initiates the LCR election algorithm by broadcasting to all nodes.
        Then starts the token passing process.
        """
        # Reset election state
        self.participant = False
        self.current_leader = None
        self.election_active = True
        
        # broadcast election initiation to all nodes
        try:
            msg = f"ELECTION_INIT:{self.local_ip}:{self.pc_name}"
            for addr in self.get_broadcast_addresses():
                try:
                    self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
                    self.run_election_simulation()
                except:
                    pass
        except Exception as e:
            print(f"Error broadcasting election initiation: {e}")
    
    def run_election_simulation(self):
        """
        Runs the LCR election algorithm by sending tokens around the ring.
        """
        print("============================================================")
        print("======LEADER ELECTION SIMULATION HAS BEEN INITIATED =======")
        print("============================================================")

        # 1. Establish Ring
        ring_order_ips = self.calculate_ring_topology()
        print("=| RING DONE |==============================================>")
        print(f"[{self.local_ip}] Ring Order IPs:", ring_order_ips)

        # 2. Get Neighbour (Successor)
        if len(ring_order_ips) == 0:
            print(f"[{self.local_ip}] No nodes in ring")
            return None
            
        successor_index = (ring_order_ips.index(self.local_ip) + 1) % len(ring_order_ips)
        self.ring_successor = ring_order_ips[successor_index]
        print("=| SUCCESSOR DONE |==============================================>")
        print(f"[{self.local_ip}] Successor IP: {self.ring_successor}")

        # 3. Run LCR By Sending my UID (score, IP) around the ring
        print("=| STARTING LCR |==============================================>")
        if not self.participant:
            self.participant = True
            print(f"[{self.local_ip}] IS Sending initial LCR token with my score={self.current_score}, IP={self.local_ip}")
            self.send_lcr_token(self.current_score, self.local_ip, is_leader=False)
        
        self.election_results = {
            "initiator_ip": self.local_ip,
            "ring_topology": ring_order_ips,
            "successor": self.ring_successor
        }
            
        return self.election_results
    
    def send_lcr_token(self, mid_score, mid_ip, is_leader):
        """
        Sends an LCR token to the successor node in the ring.
        Format: LCR_TOKEN:MID_SCORE:MID_IP:IS_LEADER
        """
        try:
            msg = f"LCR_TOKEN:{mid_score}:{mid_ip}:{is_leader}"
            # Send directly to successor's IP
            self.socket.sendto(msg.encode(), (self.ring_successor, self.broadcast_port))
            print(f"[{self.local_ip}] Sent LCR token: score={mid_score}, ip={mid_ip}, is_leader={is_leader} to {self.ring_successor}")
        except Exception as e:
            print(f"[{self.local_ip}] Error sending LCR token: {e}")
    
    def handle_lcr_token(self, mid_score, mid_ip, is_leader):
        """
        Handles received LCR token according to LCR algorithm rules.
        Uses composite UID: (score, ip) where higher score wins, IP is tiebreaker.
        """
        print(f"\n[{self.local_ip}] Received LCR token: score={mid_score}, ip={mid_ip}, is_leader={is_leader}")
        
        # Ensure ring topology is calculated
        # self.calculate_ring_topology()
        
        # Composite UID comparison: (score, ip)
        # Higher score wins, if equal then higher IP wins
        mid_uid = (mid_score, mid_ip)
        my_uid = (self.current_score, self.local_ip)
        
        if is_leader:
            # If message indicates leader, accept it
            print(f"[{self.local_ip}] Leader elected: {mid_ip} with score {mid_score}")
            self.current_leader = mid_ip
            self.my_role = "Leader" if mid_ip == self.local_ip else "Worker"
            self.participant = False
            
            # Forward leader message to successor (unless I'm the only node)
            if self.ring_successor != self.local_ip:
                self.send_lcr_token(mid_score, mid_ip, is_leader=True)
            
            # Broadcast final result
            device_name = self.discovered_devices.get(mid_ip, {}).get('name', 'Unknown')
            self.broadcast_election_result(mid_ip, device_name)
            
        elif mid_uid < my_uid and not self.participant:
            # My UID is higher, send my own token
            print(f"[{self.local_ip}] My UID is higher {my_uid} > {mid_uid}, sending my token")
            self.participant = True
            self.send_lcr_token(self.current_score, self.local_ip, is_leader=False)
            
        elif mid_uid > my_uid:
            # Higher UID received, forward it
            print(f"[{self.local_ip}] Forwarding higher UID: {mid_uid}")
            self.participant = True
            self.send_lcr_token(mid_score, mid_ip, is_leader=False)
            
        elif mid_ip == self.local_ip:
            # My token came back - I'm the leader!
            print(f"[{self.local_ip}] *** I AM THE LEADER! *** (score={self.current_score}, ip={self.local_ip})")
            self.current_leader = self.local_ip
            self.my_role = "Leader"
            self.participant = False
            
            # Send leader announcement
            self.send_lcr_token(self.current_score, self.local_ip, is_leader=True)
            
            # Broadcast to all nodes
            self.broadcast_election_result(self.local_ip, self.pc_name)
    
    def broadcast_election_result(self, leader_ip, leader_name):
        """
        Broadcasts election result to all nodes in the network.
        Format: ELECTION:LEADER_IP:LEADER_NAME
        """
        try:
            msg = f"ELECTION:{leader_ip}:{leader_name}"
            for addr in self.get_broadcast_addresses():
                try:
                    self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
                    self.election_active = False
                except:
                    pass
        except Exception as e:
            print(f"Error broadcasting election result: {e}")
    
    def get_election_status(self):
        """
        Returns current election status for this node.
        Step 4: Verify all nodes have the same leader.
        """
        # Check if all nodes agree on the leader
        leader_consensus = self.verify_leader_consensus()
        
        return {
            "election_active": self.election_active,
            "current_leader": self.current_leader,
            "my_role": self.my_role,
            "my_ip": self.local_ip,
            "participant": self.participant,
            "ring_successor": self.ring_successor,
            "leader_consensus": leader_consensus,
            "election_results": self.election_results
        }
    
    def verify_leader_consensus(self):
        """
        Step 4: Verify that all nodes in the network have elected the same leader.
        """
        if not self.current_leader:
            return {
                "consensus_reached": False,
                "reason": "No leader elected yet"
            }
        
        # In a real implementation, this would query all nodes
        # For now, we assume consensus once a leader is broadcast
        return {
            "consensus_reached": self.election_active and self.current_leader is not None,
            "agreed_leader": self.current_leader,
            "total_nodes": len(self.discovered_devices)
        }
    
    def get_broadcast_addresses(self):
        """Get all broadcast addresses for network interfaces"""
        broadcast_addresses = ['<broadcast>']
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