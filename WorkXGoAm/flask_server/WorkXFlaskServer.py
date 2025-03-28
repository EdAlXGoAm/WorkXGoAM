from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
import json
import os
import socket
import sys

app = Flask(__name__)
CORS(app)

# Get free port
def find_free_port(default_port=8080):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', default_port))
        s.close()
        return default_port
    except OSError:
        # Port in use, try another
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', 0))  # Auto-assigned port
        port = s.getsockname()[1]
        s.close()
        return port

# Save port info as JSON
def save_port_info(port):
    # Get LOCALAPPDATA path
    local_app_data = os.environ.get('LOCALAPPDATA')
    if not local_app_data:
        print("LOCALAPPDATA not found")
        return
    
    # Create dir if missing
    app_data_dir = os.path.join(local_app_data, "WorkXGoAm")
    os.makedirs(app_data_dir, exist_ok=True)
    
    # Save port info
    port_info = {"port": port}
    with open(os.path.join(app_data_dir, "server-port.json"), 'w') as f:
        json.dump(port_info, f)
    
    print(f"Port info saved in {app_data_dir}/server-port.json")

# Health check route
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

# Example route
@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify({"message": "Hello from Flask server!"})

# Set console title (Windows)
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.kernel32.SetConsoleTitleW("WorkXFlaskServer")

if __name__ == '__main__':
    app.debug = False  # Disable debug in prod
    port = find_free_port(default_port=8080)
    print(f"Starting on port: {port}")
    
    # Save port info
    save_port_info(port)
    
    # Extra files for reload (dev)
    extra_files = []
    
    app.run(host='127.0.0.1', port=port, extra_files=extra_files)
