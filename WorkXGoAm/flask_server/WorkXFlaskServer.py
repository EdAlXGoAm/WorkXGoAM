from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
from connection import find_free_port, save_port_info, connection_bp
from video_service import recortar_video
from floating_face_manager import FloatingFaceManager

app = Flask(__name__)
CORS(app)
app.register_blueprint(connection_bp)

# Rutas de servicio de video
@app.route('/video/cut', methods=['POST'])
def cut_video():
    data = request.get_json()
    input_path = data.get('input')
    start = data.get('start')
    end = data.get('end')
    output = data.get('output')
    try:
        result = recortar_video(input_path, start, end, output)
        return jsonify({'status': 'success', 'output': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Set console title (Windows)
if sys.platform == 'win32':
    import ctypes
    ctypes.windll.kernel32.SetConsoleTitleW("WorkXFlaskServer")

if __name__ == '__main__':
    app.debug = False  # Disable debug in prod
    port = find_free_port(default_port=8080)
    print(f"Starting on port: {port}")

    save_port_info(port)

    # Iniciar carita flotante con su gestor
    # Puedes proporcionar URLs personalizadas para las imágenes PNG (opcional)
    # Si no se proporcionan o fallan, usará el dibujo manual como fallback
    face_manager = FloatingFaceManager(
        happy_face_url="https://cdn-icons-png.flaticon.com/512/8421/8421363.png",  # Reemplaza con tu URL
        surprised_face_url="https://cdn-icons-png.flaticon.com/512/8421/8421352.png"  # Reemplaza con tu URL
    )
    face_manager.start()

    extra_files = []

    app.run(host='127.0.0.1', port=port, extra_files=extra_files)
