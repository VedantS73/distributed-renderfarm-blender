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
       "Distributed Renderer Client",
       "http://127.0.0.1:5050",
       width=1200,
       height=800,
       resizable=True,
       frameless=False,
   )

   webview.start(icon="client/public/logo.png", debug=True)