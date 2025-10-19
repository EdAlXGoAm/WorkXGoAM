import threading
import sys
import time
import io
import urllib.request
from typing import Optional

# Tkinter es parte de la librería estándar
try:
    import tkinter as tk
except Exception as e:
    tk = None

# Carga de imágenes (Pillow)
try:
    from PIL import Image, ImageTk, ImageFilter
except Exception:
    Image = None
    ImageTk = None
    ImageFilter = None


class FloatingFaceTk:
    """Ventana flotante con Tkinter, arrastrable y con modo always-on-top conmutable."""
    def __init__(self, size: int = 150, happy_face_url: Optional[str] = None, surprised_face_url: Optional[str] = None):
        self.size = size
        self.running = False
        self.is_surprised = False
        self.always_on_top_enabled = True
        self.use_images = False

        # URLs opcionales
        self.happy_face_url = happy_face_url
        self.surprised_face_url = surprised_face_url

        self._thread: Optional[threading.Thread] = None
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None

        # Imágenes cargadas
        self._happy_image = None  # PIL.Image
        self._surprised_image = None  # PIL.Image
        self._happy_photo = None  # ImageTk.PhotoImage (referencia viva obligatoria)
        self._surprised_photo = None

        # Estado de arrastre
        self._dragging = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0

    # ==========================
    # Renderizado de la carita
    # ==========================
    def _draw_happy_face(self):
        c = self._canvas
        s = self.size
        # Fondo magenta para poder simular transparencia si se usa wm_attributes('transparentcolor', ...)
        c.create_rectangle(0, 0, s, s, fill="#FF00FF", outline="")
        # Cara
        c.create_oval(10, 10, s-10, s-10, fill="#FFFF00", outline="#000000", width=3)
        # Ojos
        eye_y = s//2 - 20
        c.create_oval(s//2 - 33, eye_y - 8, s//2 - 17, eye_y + 8, fill="#000000", outline="")
        c.create_oval(s//2 + 17, eye_y - 8, s//2 + 33, eye_y + 8, fill="#000000", outline="")
        # Sonrisa
        c.create_arc(s//2 - 35, s//2 + 5, s//2 + 35, s//2 + 40, start=200, extent=140, style=tk.ARC, outline="#000000", width=4)

    def _draw_surprised_face(self):
        c = self._canvas
        s = self.size
        c.create_rectangle(0, 0, s, s, fill="#FF00FF", outline="")
        # Cara
        c.create_oval(10, 10, s-10, s-10, fill="#FFFF00", outline="#000000", width=3)
        # Ojos grandes con brillo
        eye_y = s//2 - 20
        c.create_oval(s//2 - 37, eye_y - 12, s//2 - 13, eye_y + 12, fill="#000000", outline="")
        c.create_oval(s//2 - 31, eye_y - 8, s//2 - 19, eye_y + 0, fill="#FFFFFF", outline="")
        c.create_oval(s//2 + 13, eye_y - 12, s//2 + 37, eye_y + 12, fill="#000000", outline="")
        c.create_oval(s//2 + 19, eye_y - 8, s//2 + 31, eye_y + 0, fill="#FFFFFF", outline="")
        # Boca O
        c.create_oval(s//2 - 15, s//2 + 10, s//2 + 15, s//2 + 40, fill="#000000", outline="")
        c.create_oval(s//2 - 12, s//2 + 13, s//2 + 12, s//2 + 37, fill="#FF6464", outline="")

    def _render(self):
        self._canvas.delete("all")
        if self.use_images and self._happy_photo and self._surprised_photo:
            # Fondo magenta para transparencia por colorkey
            self._canvas.create_rectangle(0, 0, self.size, self.size, fill="#FF00FF", outline="")
            if self.is_surprised:
                self._canvas.create_image(0, 0, image=self._surprised_photo, anchor="nw")
            else:
                self._canvas.create_image(0, 0, image=self._happy_photo, anchor="nw")
        else:
            if self.is_surprised:
                self._draw_surprised_face()
            else:
                self._draw_happy_face()

    # ==========================
    # Eventos de ratón/ventana
    # ==========================
    def _on_mouse_down(self, event):
        self._dragging = True
        self._drag_offset_x = event.x
        self._drag_offset_y = event.y

    def _on_mouse_up(self, event):
        self._dragging = False

    def _on_mouse_move(self, event):
        if self._dragging and self._root is not None:
            # Calcular posición en pantalla (event.x_root / event.y_root)
            new_x = event.x_root - self._drag_offset_x
            new_y = event.y_root - self._drag_offset_y
            self._root.geometry(f"{self.size}x{self.size}+{new_x}+{new_y}")

    def _on_motion(self, event):
        # Detectar si el puntero está dentro del círculo
        cx = self.size // 2
        cy = self.size // 2
        dx = event.x - cx
        dy = event.y - cy
        distance = (dx*dx + dy*dy) ** 0.5
        was_surprised = self.is_surprised
        self.is_surprised = distance < (self.size // 2 - 10)
        if self.is_surprised != was_surprised:
            self._render()

    def _update_hover_state_from_pointer(self):
        # Recalcula el estado de "sorpresa" en base a la posición global del puntero
        if self._root is None:
            return
        try:
            px, py = self._root.winfo_pointerxy()
            rx, ry = self._root.winfo_rootx(), self._root.winfo_rooty()
            x = px - rx
            y = py - ry
            # Limitar a los límites de la ventana para evitar falsos positivos
            inside_window = (0 <= x < self.size) and (0 <= y < self.size)
            cx = self.size // 2
            cy = self.size // 2
            dx = x - cx
            dy = y - cy
            distance = (dx*dx + dy*dy) ** 0.5
            new_state = inside_window and (distance < (self.size // 2 - 10))
            if not self._dragging and new_state != self.is_surprised:
                self.is_surprised = new_state
        except Exception:
            pass

    # ==========================
    # Carga de imágenes remotas
    # ==========================
    def _defringe_alpha(self, img, threshold: int = 16, expand: int = 1):
        # Convierte el alfa a binario (0/255) y expande ligeramente para evitar halos
        try:
            if Image is None:
                return img
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            r, g, b, a = img.split()
            mask = a.point(lambda p: 255 if p >= threshold else 0)
            if ImageFilter is not None and expand > 0:
                size = 3 if expand == 1 else max(3, expand * 2 + 1)
                mask = mask.filter(ImageFilter.MaxFilter(size))
            # Ensamblar imagen con alfa binario (bordes nítidos)
            return Image.merge("RGBA", (r, g, b, mask))
        except Exception:
            return img

    def _load_image_from_url(self, url: str):
        if not url or Image is None:
            return None
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                image_data = response.read()
            img = Image.open(io.BytesIO(image_data)).convert("RGBA")
            img = img.resize((self.size, self.size), Image.LANCZOS)
            img = self._defringe_alpha(img, threshold=12, expand=1)
            return img
        except Exception as e:
            print(f"✗ Error cargando imagen (Tk) desde {url}: {e}")
            return None

    def _try_load_images(self):
        # Cargar PIL images
        self._happy_image = self._load_image_from_url(self.happy_face_url)
        self._surprised_image = self._load_image_from_url(self.surprised_face_url)
        # Convertir a PhotoImage (requiere root activo)
        try:
            if self._happy_image is not None and self._surprised_image is not None and ImageTk is not None:
                self._happy_photo = ImageTk.PhotoImage(self._happy_image)
                self._surprised_photo = ImageTk.PhotoImage(self._surprised_image)
                self.use_images = True
                print("✓ Usando imágenes PNG (Tk)")
            else:
                self.use_images = False
                print("✓ Usando dibujo manual (Tk) como fallback")
        except Exception as e:
            self.use_images = False
            print(f"✗ Error preparando PhotoImage: {e}")

    # ==========================
    # Control de Always-On-Top
    # ==========================
    def set_always_on_top(self, enabled: bool):
        self.always_on_top_enabled = enabled
        if self._root is not None:
            try:
                self._root.wm_attributes("-topmost", 1 if enabled else 0)
            except Exception:
                pass

    def toggle_always_on_top(self):
        self.set_always_on_top(not self.always_on_top_enabled)

    def raise_window(self):
        if self._root is None:
            return
        try:
            self._root.lift()
            # Bostezo de topmost para refrescar Z-order
            self._root.wm_attributes("-topmost", 1)
            self._root.update_idletasks()
        except Exception:
            pass
        finally:
            # Restaurar estado configurado
            try:
                self._root.wm_attributes("-topmost", 1 if self.always_on_top_enabled else 0)
            except Exception:
                pass

    # ==========================
    # Ciclo de vida
    # ==========================
    def run(self):
        if tk is None:
            print("Tkinter no disponible en este entorno")
            return

        self._root = tk.Tk()
        self._root.title("WorkX Face (Tk)")
        self._root.resizable(False, False)
        # Ventana sin borde
        self._root.overrideredirect(True)
        # Fondo magenta para hacer transparencia por color (Windows 10+)
        try:
            self._root.wm_attributes("-transparentcolor", "#FF00FF")
        except Exception:
            pass

        self._canvas = tk.Canvas(self._root, width=self.size, height=self.size, highlightthickness=0, bg="#FF00FF")
        self._canvas.pack()

        # Centrar en pantalla
        try:
            self._root.update_idletasks()
            screen_w = self._root.winfo_screenwidth()
            screen_h = self._root.winfo_screenheight()
            x = (screen_w - self.size) // 2
            y = (screen_h - self.size) // 2
            self._root.geometry(f"{self.size}x{self.size}+{x}+{y}")
        except Exception:
            pass

        # Topmost inicial
        self.set_always_on_top(True)

        # Intentar cargar imágenes si hay URLs
        self._try_load_images()

        # Eventos
        self._canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self._canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self._canvas.bind("<B1-Motion>", self._on_mouse_move)
        self._canvas.bind("<Motion>", self._on_motion)

        # Render inicial
        self._render()

        self.running = True
        # Loop principal (bloqueante). Para poder cerrar desde stop, usamos after para comprobar estado
        def _loop_check():
            if not self.running:
                try:
                    self._root.destroy()
                except Exception:
                    pass
                return
            # Actualizar estado de hover aunque el mouse no se mueva (p.ej., si la ventana se mueve debajo del puntero)
            self._update_hover_state_from_pointer()
            self._render()  # opcional, mantiene ~30 FPS
            self._root.after(33, _loop_check)  # ~30 FPS

        self._root.after(33, _loop_check)
        try:
            self._root.mainloop()
        except Exception:
            pass

    def start(self):
        if self._thread and self._thread.is_alive():
            return self._thread
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self.running = False
        # La destrucción se gestiona en _loop_check


