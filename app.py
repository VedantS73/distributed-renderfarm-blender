from flask import Flask, jsonify, request
from flask_cors import CORS
import socket
import threading
import time
import platform
import netifaces
from datetime import datetime

app = Flask(__name__)
CORS(app)

class NetworkDiscoveryServer:
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
        """Get local IP address"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "Unknown"
    
    def get_broadcast_addresses(self):
        """Get all possible broadcast addresses"""
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
    
    def start_discovery(self):
        """Start network discovery"""
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
            
            # Add self to discovered devices
            self.add_device(self.pc_name, self.local_ip)
            
            # Start network threads
            self.broadcast_thread = threading.Thread(target=self.broadcast_presence, daemon=True)
            self.listen_thread = threading.Thread(target=self.listen_for_devices, daemon=True)
            
            self.broadcast_thread.start()
            self.listen_thread.start()
            
            return True, "Discovery started successfully"
            
        except Exception as e:
            return False, f"Failed to start discovery: {str(e)}"
    
    def stop_discovery(self):
        """Stop network discovery"""
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def broadcast_presence(self):
        """Broadcast this PC's presence to the network"""
        broadcast_addresses = self.get_broadcast_addresses()
        
        while self.running:
            try:
                message = f"DISCOVER:{self.pc_name}:{self.local_ip}"
                
                for broadcast_addr in broadcast_addresses:
                    try:
                        self.socket.sendto(message.encode('utf-8'), (broadcast_addr, self.broadcast_port))
                    except Exception as e:
                        print(f"Failed to broadcast to {broadcast_addr}: {e}")
                
                time.sleep(3)
                
            except Exception as e:
                if self.running:
                    print(f"Broadcast error: {e}")
                    time.sleep(5)
    
    def listen_for_devices(self):
        """Listen for other devices broadcasting their presence"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                message = data.decode('utf-8')
                                
                if message.startswith("DISCOVER:"):
                    parts = message.split(":")
                    if len(parts) >= 3:
                        device_name = parts[1]
                        device_ip = parts[2]
                        
                        # Don't add our own broadcasts
                        if device_ip == self.local_ip:
                            continue
                        
                        self.add_device(device_name, device_ip)
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Listen error: {e}")

    def add_device(self, name, ip):
        """Add a device to the discovered list"""
        current_time = datetime.now().strftime("%H:%M:%S")
        device_key = f"{name}@{ip}"
        
        self.discovered_devices[device_key] = {
            'name': name,
            'ip': ip,
            'last_seen': current_time
        }
    
    def get_devices(self):
        """Get list of discovered devices"""
        devices = list(self.discovered_devices.values())
        # Count other devices (excluding self)
        other_devices_count = sum(1 for device in devices if device['ip'] != self.local_ip)
        
        return {
            'devices': devices,
            'stats': {
                'total_devices': len(devices),
                'other_devices': other_devices_count,
                'local_pc_name': self.pc_name,
                'local_ip': self.local_ip
            }
        }
    
    def test_broadcast(self):
        """Test broadcast functionality"""
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            message = f"DISCOVER:{self.pc_name}:{self.local_ip}"
            test_socket.sendto(message.encode('utf-8'), ('<broadcast>', self.broadcast_port))
            test_socket.close()
            return True, "Test broadcast sent successfully"
        except Exception as e:
            return False, f"Broadcast test failed: {str(e)}"

# Global server instance
discovery_server = NetworkDiscoveryServer()

# API Routes
@app.route('/api/start', methods=['POST'])
def start_discovery():
    success, message = discovery_server.start_discovery()
    return jsonify({'success': success, 'message': message})

@app.route('/api/stop', methods=['POST'])
def stop_discovery():
    discovery_server.stop_discovery()
    return jsonify({'success': True, 'message': 'Discovery stopped'})

@app.route('/api/devices', methods=['GET'])
def get_devices():
    return jsonify(discovery_server.get_devices())

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        'running': discovery_server.running,
        'local_pc_name': discovery_server.pc_name,
        'local_ip': discovery_server.local_ip
    })

@app.route('/api/test-broadcast', methods=['POST'])
def test_broadcast():
    success, message = discovery_server.test_broadcast()
    return jsonify({'success': success, 'message': message})

@app.route('/api/clear-devices', methods=['POST'])
def clear_devices():
    discovery_server.discovered_devices.clear()
    # Re-add self if running
    if discovery_server.running:
        discovery_server.add_device(discovery_server.pc_name, discovery_server.local_ip)
    return jsonify({'success': True, 'message': 'Device list cleared'})

if __name__ == '__main__':
    print("Starting Network Discovery Server on http://localhost:5050")
    print("Make sure to run this on the same network as other devices!")
    app.run(debug=True, host='0.0.0.0', port=5050)