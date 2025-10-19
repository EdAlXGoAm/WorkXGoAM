import threading
import io
import urllib.request
from typing import Optional, List, Tuple, Callable, Union

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


class ChatWindowTk:
    """Ventana de chat profesional en Tkinter.

    Características:
    - Área de mensajes desplazable (scroll)
    - Burbujas de texto izquierda/derecha (entrantes/salientes)
    - Mensajes con imágenes (archivo o URL)
    - Barra inferior de entrada con botón Enviar y Adjuntar
    - API pública para agregar mensajes
    """

    def __init__(self, title: str = "Chat", width: int = 360, height: int = 560):
        self.title = title
        self.width = width
        self.height = height

        self._root: Optional[tk.Tk] = None
        self._thread: Optional[threading.Thread] = None
        self._messages_frame: Optional[tk.Frame] = None
        self._canvas: Optional[tk.Canvas] = None
        self._scrollbar: Optional[ttk.Scrollbar] = None
        self._entry_var = None
        self._on_send: Optional[Callable[[str], None]] = None

        # Mantener referencias de PhotoImage para que no se liberen
        self._photo_refs: List[ImageTk.PhotoImage] = []

    # ==========================
    # Ciclo de vida
    # ==========================
    def start(self):
        if tk is None:
            print("Tkinter no disponible en este entorno")
            return None
        if self._thread and self._thread.is_alive():
            return self._thread
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self._thread

    def run_blocking(self):
        if tk is None:
            print("Tkinter no disponible en este entorno")
            return
        if self._root is not None:
            try:
                self._root.lift()
                self._root.mainloop()
            except Exception:
                pass
            return
        self._run()

    def stop(self):
        try:
            if self._root is not None:
                self._root.quit()
                self._root.destroy()
        except Exception:
            pass
        finally:
            self._root = None

    def set_on_send(self, callback: Optional[Callable[[str], None]]):
        self._on_send = callback

    # ==========================
    # Construcción UI
    # ==========================
    def _run(self):
        self._root = tk.Tk()
        self._root.title(self.title)
        self._root.minsize(self.width, self.height)
        try:
            self._root.iconbitmap(default='')
        except Exception:
            pass

        # Estilos
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # Contenedor principal
        container = ttk.Frame(self._root)
        container.pack(fill=tk.BOTH, expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        # Área de mensajes desplazable
        self._canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        self._scrollbar = ttk.Scrollbar(container, orient="vertical", command=self._canvas.yview)
        self._messages_frame = ttk.Frame(self._canvas)

        self._messages_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        )

        self._canvas.create_window((0, 0), window=self._messages_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._scrollbar.grid(row=0, column=1, sticky="ns")

        # Barra de entrada
        input_bar = ttk.Frame(container)
        input_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        input_bar.columnconfigure(1, weight=1)

        attach_btn = ttk.Button(input_bar, text="📎", width=3, command=self._on_attach)
        attach_btn.grid(row=0, column=0, padx=(6, 4), pady=6)

        self._entry_var = tk.StringVar()
        entry = ttk.Entry(input_bar, textvariable=self._entry_var)
        entry.grid(row=0, column=1, sticky="ew", padx=4, pady=6)
        entry.bind("<Return>", lambda e: self._handle_send())

        send_btn = ttk.Button(input_bar, text="Enviar", command=self._handle_send)
        send_btn.grid(row=0, column=2, padx=(4, 6), pady=6)

        # Activar rueda del mouse en el canvas
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._root.mainloop()

    def _on_mousewheel(self, event):
        if self._canvas is None:
            return
        delta = -1 * int(event.delta / 120)
        self._canvas.yview_scroll(delta, "units")

    def _on_attach(self):
        # Placeholder para hook de adjuntar; el integrador puede sobreescribir
        # También se puede reemplazar dinámicamente asignando chat._on_attach = tu_funcion
        pass

    def _handle_send(self):
        text = (self._entry_var.get() if self._entry_var is not None else "").strip()
        if not text:
            return
        self.add_text_message(text, sent_by_me=True)
        if self._entry_var is not None:
            self._entry_var.set("")
        if self._on_send is not None:
            try:
                self._on_send(text)
            except Exception:
                pass

    # ==========================
    # API pública
    # ==========================
    def add_text_message(self, text: str, sent_by_me: bool = False):
        if self._messages_frame is None or not text:
            return
        bubble = self._create_bubble(self._messages_frame, text=text, image=None, sent_by_me=sent_by_me)
        bubble.pack(fill=tk.X, padx=10, pady=4, anchor='e' if sent_by_me else 'w')
        self._scroll_to_end()

    def add_image_message(self, image_source: Union[str, bytes], sent_by_me: bool = False):
        if self._messages_frame is None:
            return
        photo = self._load_image_as_photo(image_source)
        bubble = self._create_bubble(self._messages_frame, text=None, image=photo, sent_by_me=sent_by_me)
        bubble.pack(fill=tk.X, padx=10, pady=4, anchor='e' if sent_by_me else 'w')
        self._scroll_to_end()

    def clear_messages(self):
        if self._messages_frame is None:
            return
        for child in list(self._messages_frame.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        self._photo_refs.clear()

    # Alias de compatibilidad con la petición del usuario
    def add_message(self, content: Union[str, bytes], sent_by_me: bool = False, is_image: bool = False):
        if is_image:
            self.add_image_message(content, sent_by_me=sent_by_me)
        else:
            self.add_text_message(str(content), sent_by_me=sent_by_me)

    # ==========================
    # Burbujas
    # ==========================
    def _create_bubble(self, parent: tk.Widget, text: Optional[str], image: Optional[ImageTk.PhotoImage], sent_by_me: bool) -> tk.Frame:
        bubble_frame = ttk.Frame(parent)

        # Línea con avatar opcional y contenido
        line = ttk.Frame(bubble_frame)
        line.pack(fill=tk.X)

        # Contenedor de burbuja con colores
        bg = "#DCF8C6" if sent_by_me else "#FFFFFF"
        fg = "#111111"
        border = "#C5E9A8" if sent_by_me else "#DDDDDD"

        content = tk.Frame(line, bg=bg, highlightbackground=border, highlightthickness=1, bd=0)
        max_width = int(self.width * 0.72)

        if text is not None:
            label = tk.Label(content, text=text, bg=bg, fg=fg, justify=tk.LEFT, wraplength=max_width-16, padx=8, pady=6)
            label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        if image is not None:
            img_label = tk.Label(content, image=image, bg=bg)
            img_label.image = image
            img_label.pack(side=tk.LEFT, padx=2, pady=2)
            self._photo_refs.append(image)

        # Colocar a la izquierda o derecha
        if sent_by_me:
            content.pack(side=tk.RIGHT, padx=(60, 6), pady=2)
        else:
            content.pack(side=tk.LEFT, padx=(6, 60), pady=2)

        return bubble_frame

    # ==========================
    # Utilidades
    # ==========================
    def _scroll_to_end(self):
        try:
            self._canvas.update_idletasks()
            self._canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _load_image_as_photo(self, source: Union[str, bytes]) -> Optional[ImageTk.PhotoImage]:
        if Image is None or ImageTk is None:
            return None
        try:
            if isinstance(source, bytes):
                img = Image.open(io.BytesIO(source))
            elif isinstance(source, str):
                if source.startswith('http://') or source.startswith('https://'):
                    with urllib.request.urlopen(source, timeout=6) as response:
                        data = response.read()
                    img = Image.open(io.BytesIO(data))
                else:
                    img = Image.open(source)
            else:
                return None
            # Escalar a un ancho razonable
            target_w = int(self.width * 0.5)
            w, h = img.size
            if w > target_w:
                scale = target_w / float(w)
                img = img.resize((target_w, int(h * scale)))
            return ImageTk.PhotoImage(img)
        except Exception:
            return None


