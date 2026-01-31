from backend.app import create_app
from dotenv import load_dotenv

load_dotenv('.env')
app = create_app()

if __name__ == "__main__":
    print("Server running: http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=True, use_reloader=True)