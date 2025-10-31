#!/usr/bin/env python3
"""
GUI for Distributed Blender Rendering System
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
from datetime import datetime
import logging

# Assuming the DistributedRenderNode is imported from the main module
# from distributed_render import DistributedRenderNode, NodeInfo

# For demonstration, we'll use the class from your document
# In practice, you'd import it from the file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RenderNodeGUI:
   def __init__(self, root):
       self.root = root
       self.root.title("Distributed Render Network")
       self.root.geometry("800x600")
       self.root.minsize(600, 400)
      
       self.node = None
       self.is_connected = False
       self.update_thread = None
       self.running = False
      
       self._setup_ui()
      
   def _setup_ui(self):
       """Setup the user interface"""
       # Configure grid weights for responsive layout
       self.root.grid_rowconfigure(1, weight=1)
       self.root.grid_columnconfigure(0, weight=1)
      
       # Top frame - Join button
       top_frame = ttk.Frame(self.root, padding="10")
       top_frame.grid(row=0, column=0, sticky="ew")
      
       self.join_btn = ttk.Button(
           top_frame,
           text="Join Network",
           command=self.join_network,
           style="Accent.TButton"
       )
       self.join_btn.pack(fill="x", pady=5)
      
       # Status label
       self.status_label = ttk.Label(
           top_frame,
           text="Not connected",
           foreground="gray"
       )
       self.status_label.pack(pady=5)
      
       # Middle frame - Device list
       middle_frame = ttk.Frame(self.root, padding="10")
       middle_frame.grid(row=1, column=0, sticky="nsew")
       middle_frame.grid_rowconfigure(0, weight=1)
       middle_frame.grid_columnconfigure(0, weight=1)
      
       # Title
       ttk.Label(
           middle_frame,
           text="Connected Devices",
           font=("", 12, "bold")
       ).grid(row=0, column=0, sticky="w", pady=(0, 5))
      
       # Create treeview for device list
       tree_frame = ttk.Frame(middle_frame)
       tree_frame.grid(row=1, column=0, sticky="nsew")
       tree_frame.grid_rowconfigure(0, weight=1)
       tree_frame.grid_columnconfigure(0, weight=1)
      
       # Scrollbars
       vsb = ttk.Scrollbar(tree_frame, orient="vertical")
       hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
      
       # Treeview
       self.tree = ttk.Treeview(
           tree_frame,
           columns=("hostname", "ip", "cpu", "memory", "disk", "gpu", "status"),
           show="headings",
           yscrollcommand=vsb.set,
           xscrollcommand=hsb.set
       )
      
       # Configure scrollbars
       vsb.config(command=self.tree.yview)
       hsb.config(command=self.tree.xview)
      
       # Define columns
       self.tree.heading("hostname", text="Hostname")
       self.tree.heading("ip", text="IP Address")
       self.tree.heading("cpu", text="CPU")
       self.tree.heading("memory", text="Memory")
       self.tree.heading("disk", text="Free Disk")
       self.tree.heading("gpu", text="GPU")
       self.tree.heading("status", text="Status")
      
       # Column widths
       self.tree.column("hostname", width=120)
       self.tree.column("ip", width=120)
       self.tree.column("cpu", width=80)
       self.tree.column("memory", width=100)
       self.tree.column("disk", width=100)
       self.tree.column("gpu", width=60)
       self.tree.column("status", width=100)
      
       # Grid layout
       self.tree.grid(row=0, column=0, sticky="nsew")
       vsb.grid(row=0, column=1, sticky="ns")
       hsb.grid(row=1, column=0, sticky="ew")
      
       # Bottom frame - Leave button and log
       bottom_frame = ttk.Frame(self.root, padding="10")
       bottom_frame.grid(row=2, column=0, sticky="ew")
      
       self.leave_btn = ttk.Button(
           bottom_frame,
           text="Leave Network",
           command=self.leave_network,
           state="disabled"
       )
       self.leave_btn.pack(fill="x", pady=(0, 5))
      
       # Log area
       log_frame = ttk.LabelFrame(bottom_frame, text="Log", padding="5")
       log_frame.pack(fill="both", expand=True)
      
       self.log_text = scrolledtext.ScrolledText(
           log_frame,
           height=8,
           wrap=tk.WORD,
           font=("Courier", 9)
       )
       self.log_text.pack(fill="both", expand=True)
       self.log_text.config(state="disabled")
      
   def log(self, message, level="INFO"):
       """Add message to log"""
       timestamp = datetime.now().strftime("%H:%M:%S")
       log_entry = f"[{timestamp}] {level}: {message}\n"
      
       self.log_text.config(state="normal")
       self.log_text.insert(tk.END, log_entry)
       self.log_text.see(tk.END)
       self.log_text.config(state="disabled")
      
   def join_network(self):
       """Join the render network"""
       if self.is_connected:
           return
      
       try:
           self.log("Initializing node...")
          
           # Import here to avoid issues if module not available
           from distributed_render import DistributedRenderNode
          
           self.node = DistributedRenderNode()
          
           # Register callbacks
           self.node.on('leader_changed', self.on_leader_changed)
           self.node.on('became_leader', self.on_became_leader)
           self.node.on('leader_lost', self.on_leader_lost)
          
           # Start node
           self.node.start()
          
           self.is_connected = True
           self.running = True
          
           # Update UI
           self.join_btn.config(state="disabled")
           self.leave_btn.config(state="normal")
           self.status_label.config(
               text="Connected - Discovering nodes...",
               foreground="green"
           )
          
           self.log("Connected to network")
           self.log(f"Node ID: {self.node.node_id[:8]}...")
           self.log(f"IP Address: {self.node.ip_address}")
          
           # Start update thread
           self.update_thread = threading.Thread(
               target=self._update_loop,
               daemon=True
           )
           self.update_thread.start()
          
           # Trigger initial election after discovery
           threading.Timer(5.0, self.trigger_election).start()
          
       except ImportError:
           self.log("ERROR: Cannot import DistributedRenderNode", "ERROR")
           self.log("Make sure distributed_render.py is in the same directory", "ERROR")
       except Exception as e:
           self.log(f"Failed to join network: {e}", "ERROR")
           logger.exception(e)
  
   def leave_network(self):
       """Leave the render network and trigger election"""
       if not self.is_connected:
           return
      
       try:
           self.log("Leaving network...")
          
           # Stop update loop
           self.running = False
          
           # If we're the leader, trigger re-election before leaving
           if self.node and self.node.is_leader:
               self.log("Triggering leader re-election before leaving...")
               # Give other nodes time to detect we're gone
              
           # Stop node
           if self.node:
               self.node.stop()
               self.node = None
          
           self.is_connected = False
          
           # Update UI
           self.join_btn.config(state="normal")
           self.leave_btn.config(state="disabled")
           self.status_label.config(text="Not connected", foreground="gray")
          
           # Clear device list
           for item in self.tree.get_children():
               self.tree.delete(item)
          
           self.log("Disconnected from network")
          
       except Exception as e:
           self.log(f"Error leaving network: {e}", "ERROR")
           logger.exception(e)
  
   def trigger_election(self):
       """Manually trigger leader election"""
       if self.node:
           threading.Thread(
               target=self.node.elect_leader,
               daemon=True
           ).start()
  
   def on_leader_changed(self, leader_info):
        """Callback when leader changes - thread safe"""
        def safe_update():
            self.log(f"Leader changed to: {leader_info.hostname}")
            if hasattr(self, 'node') and self.node:
                status = f"Connected - Leader: {leader_info.hostname}"
                self.status_label.config(text=status, foreground="green")
        
        if self.root and self.root.winfo_exists():
            self.root.after(0, safe_update)
  
   def on_became_leader(self):
    """Callback when this node becomes leader - thread safe"""
    def safe_update():
        self.log("This node is now the LEADER!", "LEADER")
        self.status_label.config(
            text="Connected - THIS IS THE LEADER",
            foreground="blue"
        )
    
    if self.root and self.root.winfo_exists():
        self.root.after(0, safe_update)

   def on_leader_lost(self):
        """Callback when leader is lost - thread safe"""
        def safe_update():
            self.log("Leader lost, re-election needed", "WARNING")
            self.status_label.config(
                text="Connected - No leader",
                foreground="orange"
            )
        
        if self.root and self.root.winfo_exists():
            self.root.after(0, safe_update)
  
   def _update_loop(self):
       """Background thread to update device list"""
       while self.running and self.is_connected:
           try:
               self._update_device_list()
               time.sleep(2.0)  # Update every 2 seconds
           except Exception as e:
               logger.error(f"Update error: {e}")
               time.sleep(1.0)
  
   def _update_device_list(self):
       """Update the device list in the UI"""
       if not self.node:
           return
      
       # Get all nodes
       nodes = self.node.get_all_nodes()
      
       # Update in main thread
       self.root.after(0, self._refresh_tree, nodes)
  
   def _refresh_tree(self, nodes):
        """Refresh the treeview with node data - thread safe"""
        if not self.root or not self.root.winfo_exists():
            return
            
        # Use after_idle for better performance
        self.root.after_idle(self._safe_refresh_tree, nodes)

   def _safe_refresh_tree(self, nodes):
        """Actually update the treeview in main thread"""
        try:
            # Get existing items
            existing_items = {
                self.tree.item(item)['values'][0]: item
                for item in self.tree.get_children()
            }
            
            current_node_ids = set()
            
            for node in nodes:
                node_id = node.node_id
                current_node_ids.add(node_id)
                
                # Format data
                hostname = node.hostname
                if hasattr(self, 'node') and self.node and node.node_id == self.node.node_id:
                    hostname += " (This Node)"
                
                ip = node.ip_address
                cpu = f"{node.cpu_count} cores"
                memory = f"{node.available_memory / 1024**3:.1f} GB"
                disk = f"{node.free_disk / 1024**3:.1f} GB"
                gpu = "Yes" if node.has_gpu else "No"
                
                # Status
                if hasattr(self, 'node') and self.node:
                    if self.node.leader_id == node.node_id:
                        status = "LEADER"
                        tag = "leader"
                    elif node.node_id == self.node.node_id:
                        status = "Connected"
                        tag = "self"
                    else:
                        status = "Online"
                        tag = "normal"
                else:
                    status = "Online"
                    tag = "normal"
                
                values = (hostname, ip, cpu, memory, disk, gpu, status)
                
                # Update or insert
                if node_id in existing_items:
                    self.tree.item(existing_items[node_id], values=values, tags=(tag,))
                else:
                    self.tree.insert("", "end", values=values, tags=(tag,))
            
            # Remove nodes that are no longer present
            for node_id, item in existing_items.items():
                if node_id not in current_node_ids:
                    self.tree.delete(item)
            
            # Configure tags for colors
            self.tree.tag_configure("leader", background="#e3f2fd")
            self.tree.tag_configure("self", background="#f1f8e9")
            self.tree.tag_configure("normal", background="white")
            
        except Exception as e:
            logger.error(f"Tree refresh error: {e}")
   
   def on_closing(self):
       """Handle window close"""
       if self.is_connected:
           self.leave_network()
       self.root.destroy()


def main():
   """Main entry point"""
   root = tk.Tk()
  
   # Set theme
   style = ttk.Style()
   style.theme_use('clam')
  
   app = RenderNodeGUI(root)
  
   # Handle window close
   root.protocol("WM_DELETE_WINDOW", app.on_closing)
  
   root.mainloop()


if __name__ == "__main__":
   main()