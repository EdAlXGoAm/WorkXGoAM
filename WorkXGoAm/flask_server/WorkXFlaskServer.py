from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
from connection import find_free_port, save_port_info, connection_bp
from video_service import recortar_video
from floating_face_manager_tk import FloatingFaceManagerTk
from classes.core_hotkey_manager import GlobalHotkeyManager

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

    # ==========================================
    # CONFIGURACIÓN GLOBAL DE HOTKEYS
    # ==========================================
    hotkey_manager = GlobalHotkeyManager(debug_mode=False)
    
    # Iniciar carita flotante (versión Tkinter)
    face_manager = FloatingFaceManagerTk(
        happy_face_url="https://cdn-icons-png.flaticon.com/512/8421/8421363.png",
        surprised_face_url="https://cdn-icons-png.flaticon.com/512/8421/8421352.png"
    )
    face_manager.start()
    
    # Registrar hotkeys globales
    # CTRL+SHIFT+ALT+U -> Alternar always-on-top (topmost)
    hotkey_manager.register_hotkey(
        name="toggle_face_topmost",
        modifiers=['ctrl', 'shift', 'alt'],
        key='u',
        callback=face_manager.toggle_always_on_top,
        enabled=True
    )
    
    # Iniciar el listener de hotkeys
    hotkey_manager.start()
    
    # Mostrar hotkeys registrados
    print("\n" + "="*60)
    print("HOTKEYS GLOBALES CONFIGURADOS:")
    for name, combination in hotkey_manager.get_registered_hotkeys().items():
        print(f"  • {name}: {combination}")
    print("="*60 + "\n")

    extra_files = []

    app.run(host='127.0.0.1', port=port, extra_files=extra_files)
