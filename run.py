from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    print("Server running: http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False)