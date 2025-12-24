import threading
import time
import webview

from backend.app import create_app

def run_server():
   app = create_app()
   app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)


if __name__ == "__main__":
   # Start backend in background thread
   server_thread = threading.Thread(target=run_server, daemon=True)
   server_thread.start()

   # Give backend time to start
   time.sleep(1.5)

   # Open native window
   webview.create_window(
       "My App",
       "http://127.0.0.1:5050",
       width=900,
       height=800,
       resizable=False,
       frameless=False,
   )

   webview.start()