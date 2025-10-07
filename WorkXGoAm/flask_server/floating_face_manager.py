import signal
import sys
import os
from floating_face import FloatingFace

class FloatingFaceManager:
    """Gestor completo de la carita flotante con manejo de señales"""
    
    def __init__(self, happy_face_url=None, surprised_face_url=None):
        self.face_instance = None
        self._original_sigint_handler = None
        self.happy_face_url = happy_face_url
        self.surprised_face_url = surprised_face_url
        
    def _signal_handler(self, sig, frame):
        """Maneja CTRL+C para cerrar limpiamente"""
        print("\n\nRecibido CTRL+C, cerrando servidor...")
        self.stop()
        # Salir inmediatamente sin esperar
        os._exit(0)
    
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
        
        print("Carita flotante iniciada!")
        print("Presiona CTRL+C para cerrar el servidor\n")
    
    def stop(self):
        """Detiene la carita flotante"""
        if self.face_instance:
            self.face_instance.stop()
            self.face_instance = None
    
    def __del__(self):
        """Cleanup al destruir el objeto"""
        self.stop()
