import signal
import os
import time
from typing import Optional

from floating_face_tk import FloatingFaceTk
from classes.core_window_manager import WindowManagerCore, WindowStrategy


class FloatingFaceManagerTk:
    """Gestor para FloatingFaceTk con manejo de señales y control topmost."""
    def __init__(self, happy_face_url: Optional[str] = None, surprised_face_url: Optional[str] = None):
        self.face: Optional[FloatingFaceTk] = None
        self._original_sigint_handler = None
        self.window_manager = WindowManagerCore(debug_mode=True)
        self.happy_face_url = happy_face_url
        self.surprised_face_url = surprised_face_url

    # ==========================
    # Integración con WindowManagerCore
    # ==========================
    def bring_face_to_front(self):
        # Con Tk/Tcl, la ventana ya está en topmost cuando está activo el flag.
        # Si queremos forzar foco, podemos intentar usar win32, pero la geometría/hwnd
        # de Tk no se obtiene directamente aquí. De momento, alternamos el topmost para
        # refrescar Z-order y luego lo dejamos como estaba.
        if self.face:
            current = self.face.always_on_top_enabled
            self.face.set_always_on_top(False)
            time.sleep(0.05)
            self.face.set_always_on_top(True if current else False)

    # ==========================
    # Control de Always-On-Top
    # ==========================
    def toggle_always_on_top(self):
        if self.face:
            self.face.toggle_always_on_top()
            state = "ACTIVADO" if self.face.always_on_top_enabled else "DESACTIVADO"
            print(f"Always-on-top {state}")

    # ==========================
    # Ciclo de vida
    # ==========================
    def _signal_handler(self, sig, frame):
        print("\n\nRecibido CTRL+C, cerrando Tk face...")
        self.stop()
        os._exit(0)

    def start(self):
        self._original_sigint_handler = signal.signal(signal.SIGINT, self._signal_handler)
        self.face = FloatingFaceTk(size=150, happy_face_url=self.happy_face_url, surprised_face_url=self.surprised_face_url)
        self.face.start()
        time.sleep(0.4)
        print("Carita Tk iniciada! (CTRL+C para cerrar)\n")

    def stop(self):
        if self.face:
            self.face.stop()
            self.face = None

    def __del__(self):
        self.stop()


