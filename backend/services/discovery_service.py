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
        self.my_role = "Undefined"
        self.election_active = False
        self.election_results = None

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
            ram_score = (ram.available / ram.total) * 50
            cpu_score = (100 - cpu_usage) * 30
            disk_score = (disk.free / disk.total) * 20
            
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
            
        return all_nodes

    def run_election_simulation(self):
        """
        Simulates the LCR algorithm to return the state to the API.
        In a real scenario, this would involve passing tokens between nodes.
        Here we calculate the deterministic result based on the document's rules.
        """
        # 1. Establish Ring
        ring_order_ips = self.calculate_ring_topology()
        
        # 2. Determine Leader based on LCR Rules 
        # Composite ID: (Resource_Score, Unique_ID)
        # Tiebreaker: Higher Unique_ID (IP) wins
        
        candidates = []
        for ip in ring_order_ips:
            device = self.discovered_devices.get(ip)
            if device:
                candidates.append(device)
        
        # Sort by Resource Score (DESC), then by IP (DESC) as tiebreaker
        candidates.sort(key=lambda x: (x['resource_score'], x['ip']), reverse=True)
        
        leader_node = candidates[0] if candidates else None
        
        # Update local state
        if leader_node:
            self.current_leader = leader_node['ip']
            self.my_role = "Leader" if leader_node['ip'] == self.local_ip else "Worker"
            self.election_active = True
            
            # Broadcast election results to all nodes
            self.broadcast_election_result(leader_node['ip'], leader_node['name'])
        
        # 3. Build the visualization structure
        ring_structure = []
        for ip in ring_order_ips:
            device = self.discovered_devices.get(ip)
            role = "Worker"
            if leader_node and ip == leader_node['ip']:
                role = "Leader"
            
            node_data = {
                "ip": ip,
                "name": device['name'],
                "resource_score": device['resource_score'],
                "role": role,
                "is_me": (ip == self.local_ip),
                "successor": ring_order_ips[(ring_order_ips.index(ip) + 1) % len(ring_order_ips)]
            }
            ring_structure.append(node_data)
        
        self.election_results = {
            "initiator_ip": self.local_ip,
            "leader_ip": leader_node['ip'] if leader_node else "None",
            "election_method": "LCR (LeLann-Chang-Roberts)",
            "ring_topology": ring_structure
        }
            
        return self.election_results
    
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
                except:
                    pass
        except Exception as e:
            print(f"Error broadcasting election result: {e}")
    
    def get_election_status(self):
        """
        Returns current election status for this node
        """
        return {
            "election_active": self.election_active,
            "current_leader": self.current_leader,
            "my_role": self.my_role,
            "my_ip": self.local_ip,
            "election_results": self.election_results
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