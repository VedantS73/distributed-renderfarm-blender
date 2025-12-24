# Distributed Blender Render Farm

A **distributed render farm for Blender** that allows you to offload and manage rendering tasks across multiple nodes.

---

## 🚀 Features

- Distributed rendering architecture
- Python-based backend

---

## 🧱 Requirements

Make sure the following are installed on your system:

- **Python 3.12**
- **Node.js v20+**
- **Blender 3D** *(optional for now, required later)*
- **FFmpeg (CLI version)**  *(optional for now, required later)*

Install FFmpeg via:
- **Windows:** `choco install ffmpeg`
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

---

## 🛠️ Setup Instructions

### 1️⃣ Create a Virtual Environment

#### Windows
```bash
python -m venv venv
```
#### Linux
```bash
python3.12 -m venv venv
```
#### macOS
```bash
python3.12 -m venv venv
```

### 2️⃣ Activate the Virtual Environment

#### Windows
```bash
venv\Scripts\activate
```
#### Linux
```bash
source venv/bin/activate
```
#### macOS
```bash
source venv/bin/activate
```

### 3️⃣ Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4️⃣ Run the Application
```bash
python run.py
```

### 5️⃣ Visit the Browser to access the Application
```bash
http://127.0.0.1:5050/
```

