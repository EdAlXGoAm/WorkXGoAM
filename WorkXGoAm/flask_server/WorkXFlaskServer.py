from flask import Flask
from flask_cors import CORS
import sys
from connection import find_free_port, save_port_info, connection_bp

app = Flask(__name__)
CORS(app)
app.register_blueprint(connection_bp)

# Set console title (Windows)
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.kernel32.SetConsoleTitleW("WorkXFlaskServer")

if __name__ == '__main__':
    app.debug = False  # Disable debug in prod
    port = find_free_port(default_port=8080)
    print(f"Starting on port: {port}")

    save_port_info(port)

    extra_files = []

    app.run(host='127.0.0.1', port=port, extra_files=extra_files)
