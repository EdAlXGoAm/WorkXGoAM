from flask import Blueprint, jsonify
import json
import os
import socket

connection_bp = Blueprint('connection', __name__, url_prefix='/api')

def find_free_port(default_port=8080):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', default_port))
        s.close()
        return default_port
    except OSError:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', 0))  # Auto-asignación de puerto
        port = s.getsockname()[1]
        s.close()
        return port

def save_port_info(port):
    local_app_data = os.environ.get('LOCALAPPDATA')
    if not local_app_data:
        print("LOCALAPPDATA no encontrado")
        return
    app_data_dir = os.path.join(local_app_data, "WorkXGoAm")
    os.makedirs(app_data_dir, exist_ok=True)
    port_info = {"port": port}
    with open(os.path.join(app_data_dir, "server-port.json"), 'w') as f:
        json.dump(port_info, f)
    print(f"Port info saved in {app_data_dir}/server-port.json")

@connection_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}) 