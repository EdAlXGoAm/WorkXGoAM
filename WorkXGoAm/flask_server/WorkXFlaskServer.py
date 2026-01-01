from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import sys
import time
import ctypes
from connection import find_free_port, save_port_info, connection_bp
from video_service import recortar_video
from floating_face_manager_tk import FloatingFaceManagerTk
from ui_state import set_popup_hover, get_state, set_auto_hide_rdp, get_auto_hide_rdp, set_on_face_hover_callback
from classes.core_hotkey_manager import GlobalHotkeyManager
from classes.core_window_manager import WindowManagerCore
from rtsp_stream_service import rtsp_service

app = Flask(__name__)
CORS(app)
app.register_blueprint(connection_bp)

# Instancia del gestor de ventanas
window_manager = WindowManagerCore(debug_mode=False)

def click_bottom_left_corner():
    """
    Hace clic en el último pixel de la primera columna de la pantalla.
    En Windows 11 con barra de tareas abajo, esta área está vacía.
    Esto "despierta" el sistema de foco para que Alt+Tab funcione.
    """
    try:
        # Obtener resolución de pantalla
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)  # SM_CYSCREEN = 1
        
        # Posición: X=0 (primera columna), Y=altura-1 (último pixel)
        x, y = 0, screen_height - 1
        
        # Guardar posición actual del mouse
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        original_pos = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(original_pos))
        
        # Mover mouse a la esquina
        ctypes.windll.user32.SetCursorPos(x, y)
        
        # Simular clic (mouse_event: MOUSEEVENTF_LEFTDOWN=0x0002, MOUSEEVENTF_LEFTUP=0x0004)
        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # Left down
        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # Left up
        
        # Restaurar posición original del mouse
        time.sleep(0.01)
        ctypes.windll.user32.SetCursorPos(original_pos.x, original_pos.y)
    except Exception as e:
        print(f"Error en click_bottom_left_corner: {e}")


def minimize_rdp_and_focus():
    """
    Función para minimizar RDP y transferir foco.
    Usada tanto por el endpoint como por el callback de hover.
    """
    try:
        # Buscar por proceso mstsc.exe (Remote Desktop Connection)
        rdp_windows = window_manager.get_windows_by_process('mstsc.exe')
        rdp_hwnds = set(w['hwnd'] for w in rdp_windows)
        
        # También buscar por título que contenga patrones comunes de RDP
        title_patterns = ['Remote Desktop', 'Escritorio remoto', 'Conexión a Escritorio remoto']
        for pattern in title_patterns:
            title_matches = window_manager.get_windows_by_title(pattern)
            for w in title_matches:
                if w['hwnd'] not in rdp_hwnds:
                    rdp_windows.append(w)
                    rdp_hwnds.add(w['hwnd'])
        
        if not rdp_windows:
            return {"minimized_count": 0, "focus_transferred": False}
        
        # Minimizar todas las ventanas RDP encontradas
        minimized_count = 0
        for window in rdp_windows:
            if window_manager.minimize_window(window['hwnd']):
                minimized_count += 1
        
        # Pequeña pausa para que Windows procese la minimización
        time.sleep(0.05)
        
        # Clic en esquina inferior izquierda para "despertar" el sistema de foco
        # Esto permite que Alt+Tab funcione sin necesidad de hacer clic manual
        click_bottom_left_corner()
        
        return {"minimized_count": minimized_count, "focus_transferred": True}
    except Exception as e:
        print(f"Error en minimize_rdp_and_focus: {e}")
        return {"minimized_count": 0, "focus_transferred": False}


# Registrar el callback para cuando el mouse entre al sol con auto activo
set_on_face_hover_callback(minimize_rdp_and_focus)

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

# ==========================
# UI state para coordinación con Tauri
# ==========================
@app.route('/ui/state', methods=['GET'])
def ui_state_get():
    try:
        return jsonify({"status": "ok", "data": get_state()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/ui/popup/hover', methods=['POST'])
def ui_popup_hover():
    try:
        data = request.get_json() or {}
        hovering = bool(data.get('hover', False))
        set_popup_hover(hovering)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/ui/auto-hide-rdp', methods=['POST'])
def ui_auto_hide_rdp():
    """
    Activa/desactiva el modo automático para minimizar RDP al pasar sobre el sol.
    """
    try:
        data = request.get_json() or {}
        enabled = bool(data.get('enabled', False))
        set_auto_hide_rdp(enabled)
        return jsonify({"status": "ok", "auto_hide_rdp": enabled})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================
# Window Management Endpoints
# ==========================
@app.route('/windows/minimize-remote-desktop', methods=['POST'])
def minimize_remote_desktop():
    """
    Busca y minimiza ventanas de escritorio remoto (Remote Desktop / mstsc.exe).
    Después de minimizar, activa otra ventana para mantener el foco del sistema.
    """
    try:
        result = minimize_rdp_and_focus()
        return jsonify({
            "status": "ok",
            "message": f"Minimizadas {result['minimized_count']} ventana(s) de escritorio remoto",
            "minimized_count": result['minimized_count'],
            "focus_transferred": result['focus_transferred']
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================
# RTSP Stream Endpoints
# ==========================
@app.route('/stream/start', methods=['POST'])
def stream_start():
    """
    Inicia un stream RTSP.
    Body JSON: { 
        "stream_id": "camera1", 
        "rtsp_url": "rtsp://...",
        "with_audio": true  // true=HLS con audio, false=MJPEG sin audio
    }
    """
    try:
        data = request.get_json() or {}
        stream_id = data.get('stream_id', 'default')
        rtsp_url = data.get('rtsp_url')
        with_audio = data.get('with_audio', True)
        
        if not rtsp_url:
            return jsonify({"status": "error", "message": "rtsp_url es requerido"}), 400
        
        success = rtsp_service.start_stream(stream_id, rtsp_url, with_audio=with_audio)
        if success:
            mode = rtsp_service.get_stream_mode(stream_id)
            if mode == 'hls':
                stream_url = f"/stream/hls/{stream_id}/stream.m3u8"
            else:
                stream_url = f"/stream/feed/{stream_id}"
            
            return jsonify({
                "status": "ok",
                "message": f"Stream '{stream_id}' iniciado",
                "stream_url": stream_url,
                "mode": mode
            })
        else:
            return jsonify({"status": "error", "message": "Error iniciando stream"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stream/stop', methods=['POST'])
def stream_stop():
    """
    Detiene un stream RTSP.
    Body JSON: { "stream_id": "camera1" }
    """
    try:
        data = request.get_json() or {}
        stream_id = data.get('stream_id', 'default')
        
        success = rtsp_service.stop_stream(stream_id)
        return jsonify({
            "status": "ok",
            "message": f"Stream '{stream_id}' detenido" if success else f"Stream '{stream_id}' no encontrado"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stream/feed/<stream_id>')
def stream_feed(stream_id: str):
    """
    Endpoint que sirve el stream MJPEG.
    Usar como src de un tag <img> para visualizar.
    """
    generator = rtsp_service.get_frame_generator(stream_id)
    if generator is None:
        return jsonify({"status": "error", "message": f"Stream '{stream_id}' no encontrado o no es MJPEG"}), 404
    
    return Response(
        generator,
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/stream/hls/<stream_id>/<path:filename>')
def stream_hls(stream_id: str, filename: str):
    """
    Sirve archivos HLS (.m3u8 y .ts) para un stream.
    """
    from flask import send_from_directory
    
    stream_dir = rtsp_service.get_hls_directory(stream_id)
    if stream_dir is None:
        return jsonify({"status": "error", "message": f"Stream HLS '{stream_id}' no encontrado"}), 404
    
    # Determinar el mimetype correcto
    if filename.endswith('.m3u8'):
        mimetype = 'application/vnd.apple.mpegurl'
    elif filename.endswith('.ts'):
        mimetype = 'video/mp2t'
    else:
        mimetype = 'application/octet-stream'
    
    response = send_from_directory(stream_dir, filename, mimetype=mimetype)
    # Headers para evitar cache y permitir CORS
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/stream/status')
def stream_status():
    """
    Retorna el estado de los streams activos.
    """
    try:
        active_streams = rtsp_service.get_active_streams()
        streams_info = []
        for sid in active_streams:
            mode = rtsp_service.get_stream_mode(sid)
            streams_info.append({"id": sid, "mode": mode})
        return jsonify({
            "status": "ok",
            "active_streams": streams_info
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
