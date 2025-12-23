import socket
import threading
import time
import platform
import netifaces
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

    def get_local_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "Unknown"

    def get_broadcast_addresses(self):
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

    def start(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if platform.system() == 'Darwin':
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self.socket.settimeout(0.5)
            self.socket.bind(('', self.broadcast_port))

            self.running = True
            self.discovered_devices.clear()
            self.add_device(self.pc_name, self.local_ip)

            self.broadcast_thread = threading.Thread(target=self.broadcast_loop, daemon=True)
            self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.broadcast_thread.start()
            self.listen_thread.start()

            return True, "Discovery started"
        except Exception as e:
            return False, str(e)

    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None

    def broadcast_loop(self):
        broadcast_addresses = self.get_broadcast_addresses()
        while self.running:
            try:
                msg = f"DISCOVER:{self.pc_name}:{self.local_ip}"
                for addr in broadcast_addresses:
                    try:
                        self.socket.sendto(msg.encode(), (addr, self.broadcast_port))
                    except:
                        pass
                time.sleep(3)
            except:
                time.sleep(5)

    def listen_loop(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                msg = data.decode()
                if msg.startswith("DISCOVER:"):
                    parts = msg.split(":")
                    if len(parts) >= 3:
                        name, ip = parts[1], parts[2]
                        if ip != self.local_ip:
                            self.add_device(name, ip)
            except socket.timeout:
                continue

    def add_device(self, name, ip):
        self.discovered_devices[f"{name}@{ip}"] = {
            "name": name,
            "ip": ip,
            "last_seen": datetime.now().strftime("%H:%M:%S")
        }

    def get_devices(self):
        devices = list(self.discovered_devices.values())
        other_count = sum(1 for d in devices if d["ip"] != self.local_ip)
        return {
            "devices": devices,
            "stats": {
                "total_devices": len(devices),
                "other_devices": other_count,
                "local_pc_name": self.pc_name,
                "local_ip": self.local_ip
            }
        }