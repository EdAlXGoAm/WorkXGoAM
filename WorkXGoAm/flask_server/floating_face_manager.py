import signal
import sys
import os
import time
from floating_face import FloatingFace
from classes.core_window_manager import WindowManagerCore, WindowStrategy
from typing import Optional

class FloatingFaceManager:
    """Gestor completo de la carita flotante con manejo de señales"""
    
    def __init__(self, happy_face_url=None, surprised_face_url=None):
        self.face_instance = None
        self._original_sigint_handler = None
        self.happy_face_url = happy_face_url
        self.surprised_face_url = surprised_face_url
        
        # Gestor de ventanas para traer al frente
        self.window_manager = WindowManagerCore(debug_mode=True)
        
    def _signal_handler(self, sig, frame):
        """Maneja CTRL+C para cerrar limpiamente"""
        print("\n\nRecibido CTRL+C, cerrando servidor...")
        self.stop()
        # Salir inmediatamente sin esperar
        os._exit(0)
    
    def _bring_face_to_front(self):
        """Trae la ventana flotante al frente usando el WindowManager"""
        if self.face_instance and self.face_instance.hwnd:
            try:
                # Verificar el estado actual de la ventana
                import win32gui
                is_visible = win32gui.IsWindowVisible(self.face_instance.hwnd)
                is_iconic = win32gui.IsIconic(self.face_instance.hwnd)
                
                # Usar el window manager para traer la ventana al frente
                success = self.window_manager.bring_window_to_front(
                    self.face_instance.hwnd, 
                    strategy=WindowStrategy.MINIMIZE_FIRST
                )
                
                if success:
                    print("✓ Carita traída al frente")
                else:
                    print("✗ No se pudo traer la carita al frente")
            except Exception as e:
                print(f"[ERROR] Error trayendo carita al frente: {e}")
    
    def bring_face_to_front(self):
        """Método público para traer la carita al frente (puede ser llamado por hotkeys)"""
        self._bring_face_to_front()
    
    def start(self):
        """Inicia la carita flotante y registra manejadores de señales"""
        # Guardar el manejador original de SIGINT
        self._original_sigint_handler = signal.signal(signal.SIGINT, self._signal_handler)
        
        # Crear e iniciar la carita (con URLs opcionales)
        self.face_instance = FloatingFace(
            happy_face_url=self.happy_face_url,
            surprised_face_url=self.surprised_face_url
        )
        self.face_instance.start()
        
        # Esperar un momento para que la ventana se cree
        time.sleep(0.5)
        
        print("Carita flotante iniciada!")
        print("Presiona CTRL+C para cerrar el servidor\n")
    
    def stop(self):
        """Detiene la carita flotante"""
        # Detener la carita
        if self.face_instance:
            self.face_instance.stop()
            self.face_instance = None
    
    def __del__(self):
        """Cleanup al destruir el objeto"""
        self.stop()
