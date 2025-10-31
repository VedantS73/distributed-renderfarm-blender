#!/usr/bin/env python3
"""
Distributed Blender Rendering System
Core networking, discovery, and coordination module
"""

import socket
import threading
import json
import time
import psutil
import uuid
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Callable
from datetime import datetime
import struct

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class NodeInfo:
    """Information about a node in the network"""
    node_id: str
    hostname: str
    ip_address: str
    cpu_count: int
    cpu_freq: float  # MHz
    total_memory: int  # bytes
    available_memory: int  # bytes
    free_disk: int  # bytes
    has_gpu: bool
    last_seen: float
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)
    
    def compute_score(self):
        """Calculate node score for leader election"""
        # Prioritize storage and memory, then CPU
        storage_score = self.free_disk / (1024**3)  # GB
        memory_score = self.available_memory / (1024**3)  # GB
        cpu_score = self.cpu_count * self.cpu_freq / 1000
        gpu_score = 100 if self.has_gpu else 0
        
        return storage_score * 10 + memory_score * 5 + cpu_score + gpu_score


class MessageType:
    """Message types for network communication"""
    DISCOVERY = "DISCOVERY"
    DISCOVERY_RESPONSE = "DISCOVERY_RESPONSE"
    HEARTBEAT = "HEARTBEAT"
    LEADER_ELECTION = "LEADER_ELECTION"
    LEADER_ANNOUNCE = "LEADER_ANNOUNCE"
    TASK_ASSIGNMENT = "TASK_ASSIGNMENT"
    TASK_STATUS = "TASK_STATUS"
    TASK_COMPLETE = "TASK_COMPLETE"
    FRAME_UPLOAD = "FRAME_UPLOAD"
    REQUEST_RESOURCES = "REQUEST_RESOURCES"
    RESOURCE_REPORT = "RESOURCE_REPORT"


class DistributedRenderNode:
    """Main node class for distributed rendering system"""
    
    BROADCAST_PORT = 5555
    TCP_PORT = 5556
    DISCOVERY_INTERVAL = 5.0
    HEARTBEAT_INTERVAL = 3.0
    NODE_TIMEOUT = 10.0
    
    def __init__(self):
        self.node_id = str(uuid.uuid4())
        self.hostname = socket.gethostname()
        self.ip_address = self._get_local_ip()
        
        # Node information
        self.local_info = self._gather_system_info()
        
        # Network state
        self.known_nodes: Dict[str, NodeInfo] = {}
        self.is_leader = False
        self.leader_id: Optional[str] = None
        
        # Sockets
        self.broadcast_socket = None
        self.tcp_socket = None
        
        # Threading
        self.running = False
        self.threads: List[threading.Thread] = []
        self.lock = threading.Lock()
        
        # Callbacks
        self.callbacks: Dict[str, List[Callable]] = {}
        
        logger.info(f"Node initialized: {self.node_id} ({self.hostname})")
    
    def _get_local_ip(self):
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def _gather_system_info(self):
        """Gather system information for this node"""
        cpu_freq = psutil.cpu_freq()
        disk = psutil.disk_usage('/')
        memory = psutil.virtual_memory()
        
        # Simple GPU detection (can be enhanced)
        has_gpu = False
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            has_gpu = len(gpus) > 0
        except:
            pass
        
        return NodeInfo(
            node_id=self.node_id,
            hostname=self.hostname,
            ip_address=self.ip_address,
            cpu_count=psutil.cpu_count(),
            cpu_freq=cpu_freq.current if cpu_freq else 0,
            total_memory=memory.total,
            available_memory=memory.available,
            free_disk=disk.free,
            has_gpu=has_gpu,
            last_seen=time.time()
        )
    
    def start(self):
        """Start the node"""
        self.running = True
        
        # Setup sockets
        self._setup_broadcast_socket()
        self._setup_tcp_socket()
        
        # Start threads
        self._start_thread(self._discovery_loop, "Discovery")
        self._start_thread(self._heartbeat_loop, "Heartbeat")
        self._start_thread(self._tcp_listener, "TCP Listener")
        self._start_thread(self._node_monitor, "Node Monitor")
        
        logger.info(f"Node started on {self.ip_address}")
        logger.info(f"System: {self.local_info.cpu_count} CPUs, "
                   f"{self.local_info.available_memory/1024**3:.1f}GB RAM, "
                   f"{self.local_info.free_disk/1024**3:.1f}GB free")
    
    def stop(self):
        """Stop the node"""
        logger.info("Stopping node...")
        self.running = False
        
        # Close sockets
        if self.broadcast_socket:
            self.broadcast_socket.close()
        if self.tcp_socket:
            self.tcp_socket.close()
        
        # Wait for threads
        for thread in self.threads:
            thread.join(timeout=2.0)
        
        logger.info("Node stopped")
    
    def _setup_broadcast_socket(self):
        """Setup UDP broadcast socket for discovery"""
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.broadcast_socket.bind(('', self.BROADCAST_PORT))
        self.broadcast_socket.settimeout(1.0)
    
    def _setup_tcp_socket(self):
        """Setup TCP socket for reliable communication"""
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(('', self.TCP_PORT))
        self.tcp_socket.listen(5)
        self.tcp_socket.settimeout(1.0)
    
    def _start_thread(self, target, name):
        """Start a daemon thread"""
        thread = threading.Thread(target=target, name=name, daemon=True)
        thread.start()
        self.threads.append(thread)
    
    def _discovery_loop(self):
        """Broadcast discovery messages and listen for responses"""
        while self.running:
            try:
                # Send discovery broadcast
                message = {
                    'type': MessageType.DISCOVERY,
                    'node_info': self.local_info.to_dict()
                }
                self._broadcast_message(message)
                
                # Listen for discovery messages
                try:
                    data, addr = self.broadcast_socket.recvfrom(4096)
                    self._handle_broadcast_message(data, addr)
                except socket.timeout:
                    pass
                
                time.sleep(self.DISCOVERY_INTERVAL)
            except Exception as e:
                if self.running:
                    logger.error(f"Discovery error: {e}")
    
    def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self.running:
            try:
                # Update local info
                self.local_info = self._gather_system_info()
                
                # Send heartbeat
                message = {
                    'type': MessageType.HEARTBEAT,
                    'node_info': self.local_info.to_dict(),
                    'is_leader': self.is_leader
                }
                self._broadcast_message(message)
                
                time.sleep(self.HEARTBEAT_INTERVAL)
            except Exception as e:
                if self.running:
                    logger.error(f"Heartbeat error: {e}")
    
    def _node_monitor(self):
        """Monitor known nodes and remove stale ones"""
        while self.running:
            try:
                current_time = time.time()
                with self.lock:
                    stale_nodes = []
                    for node_id, node_info in self.known_nodes.items():
                        if current_time - node_info.last_seen > self.NODE_TIMEOUT:
                            stale_nodes.append(node_id)
                    
                    for node_id in stale_nodes:
                        logger.warning(f"Node {node_id} timed out")
                        del self.known_nodes[node_id]
                        
                        # If leader died, trigger re-election
                        if node_id == self.leader_id:
                            logger.warning("Leader died, triggering re-election")
                            self.leader_id = None
                            self.is_leader = False
                            self._trigger_callback('leader_lost')
                
                time.sleep(2.0)
            except Exception as e:
                if self.running:
                    logger.error(f"Monitor error: {e}")
    
    def _tcp_listener(self):
        """Listen for TCP connections"""
        while self.running:
            try:
                conn, addr = self.tcp_socket.accept()
                thread = threading.Thread(
                    target=self._handle_tcp_connection,
                    args=(conn, addr),
                    daemon=True
                )
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"TCP listener error: {e}")
    
    def _handle_tcp_connection(self, conn, addr):
        """Handle incoming TCP connection"""
        try:
            # Receive message length
            length_data = conn.recv(4)
            if not length_data:
                return
            
            msg_length = struct.unpack('!I', length_data)[0]
            
            # Receive message
            data = b''
            while len(data) < msg_length:
                chunk = conn.recv(min(msg_length - len(data), 4096))
                if not chunk:
                    break
                data += chunk
            
            if len(data) == msg_length:
                message = json.loads(data.decode('utf-8'))
                self._handle_tcp_message(message, conn, addr)
        except Exception as e:
            logger.error(f"TCP connection error: {e}")
        finally:
            conn.close()
    
    def _broadcast_message(self, message):
        """Broadcast a message via UDP"""
        try:
            data = json.dumps(message).encode('utf-8')
            self.broadcast_socket.sendto(data, ('<broadcast>', self.BROADCAST_PORT))
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
    
    def send_tcp_message(self, ip_address, message):
        """Send a message via TCP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip_address, self.TCP_PORT))
            
            data = json.dumps(message).encode('utf-8')
            length = struct.pack('!I', len(data))
            
            sock.sendall(length + data)
            sock.close()
            return True
        except Exception as e:
            logger.error(f"TCP send error to {ip_address}: {e}")
            return False
    
    def _handle_broadcast_message(self, data, addr):
        """Handle received broadcast message"""
        try:
            message = json.loads(data.decode('utf-8'))
            msg_type = message.get('type')
            
            if msg_type == MessageType.DISCOVERY:
                node_info = NodeInfo.from_dict(message['node_info'])
                
                # Don't add ourselves
                if node_info.node_id == self.node_id:
                    return
                
                # Add or update node
                with self.lock:
                    self.known_nodes[node_info.node_id] = node_info
                    logger.info(f"Discovered node: {node_info.hostname} ({node_info.ip_address})")
                
                # Send response
                response = {
                    'type': MessageType.DISCOVERY_RESPONSE,
                    'node_info': self.local_info.to_dict()
                }
                self._broadcast_message(response)
            
            elif msg_type == MessageType.DISCOVERY_RESPONSE:
                node_info = NodeInfo.from_dict(message['node_info'])
                
                if node_info.node_id != self.node_id:
                    with self.lock:
                        self.known_nodes[node_info.node_id] = node_info
            
            elif msg_type == MessageType.HEARTBEAT:
                node_info = NodeInfo.from_dict(message['node_info'])
                
                if node_info.node_id != self.node_id:
                    with self.lock:
                        self.known_nodes[node_info.node_id] = node_info
                    
                    # Update leader info
                    if message.get('is_leader') and self.leader_id != node_info.node_id:
                        self.leader_id = node_info.node_id
                        self.is_leader = False
                        logger.info(f"Leader is {node_info.hostname}")
                        self._trigger_callback('leader_changed', node_info)
            
            elif msg_type == MessageType.LEADER_ANNOUNCE:
                node_id = message.get('leader_id')
                if node_id != self.node_id:
                    self.leader_id = node_id
                    self.is_leader = False
                    logger.info(f"Leader announced: {node_id}")
        
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    def _handle_tcp_message(self, message, conn, addr):
        """Handle TCP message"""
        msg_type = message.get('type')
        logger.debug(f"Received TCP message: {msg_type} from {addr}")
        
        # Trigger callbacks
        self._trigger_callback(f'message_{msg_type}', message, conn, addr)
    
    def elect_leader(self):
        """Perform leader election based on system resources"""
        logger.info("Starting leader election...")
        
        with self.lock:
            # Include ourselves
            all_nodes = list(self.known_nodes.values()) + [self.local_info]
            
            if not all_nodes:
                logger.warning("No nodes available for election")
                return None
            
            # Sort by score (highest first)
            all_nodes.sort(key=lambda n: n.compute_score(), reverse=True)
            leader = all_nodes[0]
            
            logger.info(f"Election results:")
            for i, node in enumerate(all_nodes[:3]):
                logger.info(f"  {i+1}. {node.hostname}: {node.compute_score():.2f} points")
            
            # Update leader status
            if leader.node_id == self.node_id:
                self.is_leader = True
                self.leader_id = self.node_id
                logger.info("This node is now the leader!")
                self._trigger_callback('became_leader')
            else:
                self.is_leader = False
                self.leader_id = leader.node_id
                logger.info(f"Leader is {leader.hostname}")
            
            # Announce leader
            message = {
                'type': MessageType.LEADER_ANNOUNCE,
                'leader_id': leader.node_id,
                'leader_info': leader.to_dict()
            }
            self._broadcast_message(message)
            
            return leader
    
    def get_all_nodes(self):
        """Get list of all known nodes including self"""
        with self.lock:
            return list(self.known_nodes.values()) + [self.local_info]
    
    def on(self, event, callback):
        """Register callback for event"""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)
    
    def _trigger_callback(self, event, *args, **kwargs):
        """Trigger callbacks for event"""
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Callback error for {event}: {e}")


def main():
    """Example usage"""
    node = DistributedRenderNode()
    
    # Register callbacks
    def on_leader_changed(leader_info):
        logger.info(f"Leader changed to: {leader_info.hostname}")
    
    node.on('leader_changed', on_leader_changed)
    
    try:
        node.start()
        
        # Wait for discovery
        logger.info("Discovering nodes...")
        time.sleep(10)
        
        # Show discovered nodes
        nodes = node.get_all_nodes()
        logger.info(f"\nDiscovered {len(nodes)} nodes:")
        for n in nodes:
            logger.info(f"  - {n.hostname} ({n.ip_address}): "
                       f"{n.cpu_count} CPUs, {n.available_memory/1024**3:.1f}GB RAM")
        
        # Perform leader election
        leader = node.elect_leader()
        
        # Keep running
        logger.info("\nNode running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        node.stop()


if __name__ == "__main__":
    main()