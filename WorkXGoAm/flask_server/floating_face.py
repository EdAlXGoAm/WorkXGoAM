import pygame
import threading
import sys
import urllib.request
import io
from pygame.locals import *

class FloatingFace:
    def __init__(self, happy_face_url=None, surprised_face_url=None):
        self.size = 150
        self.running = False
        self.is_surprised = False
        
        # URLs de las imágenes (opcionales)
        self.happy_face_url = happy_face_url or "https://i.imgur.com/your_happy_face.png"
        self.surprised_face_url = surprised_face_url or "https://i.imgur.com/your_surprised_face.png"
        
        # Almacenar las imágenes cargadas
        self.happy_face_image = None
        self.surprised_face_image = None
        self.use_images = False
        
        # Variables para el drag & drop
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Handle de la ventana para acceso externo
        self.hwnd = None
        
    def draw_happy_face(self, screen):
        """Dibuja una carita feliz"""
        # Cara (círculo amarillo)
        pygame.draw.circle(screen, (255, 255, 0), (self.size//2, self.size//2), self.size//2 - 10)
        pygame.draw.circle(screen, (0, 0, 0), (self.size//2, self.size//2), self.size//2 - 10, 3)
        
        # Ojos
        eye_y = self.size//2 - 20
        pygame.draw.circle(screen, (0, 0, 0), (self.size//2 - 25, eye_y), 8)
        pygame.draw.circle(screen, (0, 0, 0), (self.size//2 + 25, eye_y), 8)
        
        # Sonrisa
        mouth_rect = pygame.Rect(self.size//2 - 35, self.size//2 + 5, 70, 35)
        pygame.draw.arc(screen, (0, 0, 0), mouth_rect, 3.14, 6.28, 4)
        
    def draw_surprised_face(self, screen):
        """Dibuja una carita sorprendida"""
        # Cara (círculo amarillo)
        pygame.draw.circle(screen, (255, 255, 0), (self.size//2, self.size//2), self.size//2 - 10)
        pygame.draw.circle(screen, (0, 0, 0), (self.size//2, self.size//2), self.size//2 - 10, 3)
        
        # Ojos grandes (sorprendidos)
        eye_y = self.size//2 - 20
        pygame.draw.circle(screen, (0, 0, 0), (self.size//2 - 25, eye_y), 12)
        pygame.draw.circle(screen, (255, 255, 255), (self.size//2 - 25, eye_y - 3), 5)
        pygame.draw.circle(screen, (0, 0, 0), (self.size//2 + 25, eye_y), 12)
        pygame.draw.circle(screen, (255, 255, 255), (self.size//2 + 25, eye_y - 3), 5)
        
        # Boca (círculo O)
        pygame.draw.circle(screen, (0, 0, 0), (self.size//2, self.size//2 + 25), 15)
        pygame.draw.circle(screen, (255, 100, 100), (self.size//2, self.size//2 + 25), 12)
    
    def load_image_from_url(self, url):
        """Intenta cargar una imagen desde una URL"""
        try:
            print(f"Intentando cargar imagen desde: {url}")
            with urllib.request.urlopen(url, timeout=5) as response:
                image_data = response.read()
                image_file = io.BytesIO(image_data)
                image = pygame.image.load(image_file)
                # Escalar la imagen al tamaño de la ventana
                image = pygame.transform.scale(image, (self.size, self.size))
                print(f"✓ Imagen cargada exitosamente desde {url}")
                return image
        except Exception as e:
            print(f"✗ Error cargando imagen desde {url}: {str(e)}")
            return None
    
    def try_load_images(self):
        """Intenta cargar las imágenes desde las URLs"""
        print("Intentando cargar imágenes PNG...")
        self.happy_face_image = self.load_image_from_url(self.happy_face_url)
        self.surprised_face_image = self.load_image_from_url(self.surprised_face_url)
        
        # Solo usar imágenes si ambas se cargaron correctamente
        if self.happy_face_image and self.surprised_face_image:
            self.use_images = True
            print("✓ Usando imágenes PNG para las caritas")
        else:
            self.use_images = False
            print("✓ Usando dibujo manual para las caritas (fallback)")
    
    def render_face(self, screen):
        """Renderiza la cara apropiada (imagen o dibujada)"""
        if self.use_images:
            # Usar imágenes
            if self.is_surprised:
                screen.blit(self.surprised_face_image, (0, 0))
            else:
                screen.blit(self.happy_face_image, (0, 0))
        else:
            # Usar dibujo manual
            if self.is_surprised:
                self.draw_surprised_face(screen)
            else:
                self.draw_happy_face(screen)
    
    def move_window(self, x, y):
        """Mueve la ventana a la posición especificada"""
        if sys.platform == 'win32':
            import ctypes
            hwnd = pygame.display.get_wm_info()['window']
            HWND_TOPMOST = -1
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_SHOWWINDOW = 0x0040
            # Usar MoveWindow en lugar de SetWindowPos para ventanas con estilos especiales
            ctypes.windll.user32.MoveWindow(hwnd, x, y, self.size, self.size, True)
            # Asegurar que sigue siendo topmost después de mover
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        
    def run(self):
        """Ejecuta la ventana flotante"""
        pygame.init()
        
        # Intentar cargar imágenes antes de crear la ventana
        self.try_load_images()
        
        # Crear ventana sin bordes
        screen = pygame.display.set_mode((self.size, self.size), NOFRAME)
        pygame.display.set_caption("WorkX Face")
        
        # Centrar la ventana en la pantalla y hacer transparente el fondo
        if sys.platform == 'win32':
            import ctypes
            # Obtener dimensiones de la pantalla
            user32 = ctypes.windll.user32
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            
            # Calcular posición central
            x = (screen_width - self.size) // 2
            y = (screen_height - self.size) // 2
            
            # Obtener el handle de la ventana
            hwnd = pygame.display.get_wm_info()['window']
            self.hwnd = hwnd  # Guardar para acceso externo
            
            # Mover la ventana al centro
            ctypes.windll.user32.SetWindowPos(hwnd, -1, x, y, 0, 0, 0x0001)
            
            # Hacer la ventana siempre visible (topmost)
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            HWND_TOPMOST = -1
            ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            
            # Hacer el fondo transparente usando color key (magenta)
            # Constantes de Windows
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            LWA_COLORKEY = 0x1
            
            # Obtener el estilo actual
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            # Agregar solo estilo LAYERED (transparencia) - SIN TOOLWINDOW para que sea visible en barra de tareas
            new_style = ex_style | WS_EX_LAYERED
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            
            # Establecer el color magenta (255, 0, 255) como transparente
            # El color debe estar en formato BGR para Windows
            magenta_bgr = 0x00FF00FF  # BGR: Blue=FF, Green=00, Red=FF
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, magenta_bgr, 0, LWA_COLORKEY)
        
        clock = pygame.time.Clock()
        self.running = True
        
        print("\n=== Carita flotante iniciada ===")
        print("Instrucciones:")
        print("  - Click y arrastra para mover")
        print("  - Hover para sorprender")
        print("  - ESC para cerrar")
        print("================================\n")
        
        while self.running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    self.running = False
                elif event.type == KEYDOWN:
                    if event.key == K_ESCAPE:
                        self.running = False
                elif event.type == MOUSEBUTTONDOWN:
                    if event.button == 1:  # Click izquierdo
                        # Iniciar arrastre
                        self.dragging = True
                        # Guardar offset del mouse respecto a la ventana
                        if sys.platform == 'win32':
                            import ctypes
                            hwnd = pygame.display.get_wm_info()['window']
                            rect = ctypes.wintypes.RECT()
                            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                            # Calcular posición global del mouse
                            cursor_pos = ctypes.wintypes.POINT()
                            ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pos))
                            self.drag_offset_x = cursor_pos.x - rect.left
                            self.drag_offset_y = cursor_pos.y - rect.top
                elif event.type == MOUSEBUTTONUP:
                    if event.button == 1:  # Soltar click izquierdo
                        self.dragging = False
                elif event.type == MOUSEMOTION:
                    if self.dragging:
                        if sys.platform == 'win32':
                            import ctypes
                            # Obtener posición global del cursor
                            cursor_pos = ctypes.wintypes.POINT()
                            ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pos))
                            # Calcular nueva posición de la ventana
                            new_x = cursor_pos.x - self.drag_offset_x
                            new_y = cursor_pos.y - self.drag_offset_y
                            # Mover ventana
                            self.move_window(new_x, new_y)
            
            # Detectar si el mouse está sobre la ventana
            mouse_pos = pygame.mouse.get_pos()
            center_x, center_y = self.size//2, self.size//2
            distance = ((mouse_pos[0] - center_x)**2 + (mouse_pos[1] - center_y)**2)**0.5
            mouse_over_window = distance < (self.size//2)
            
            # Gestión de topmost y foco
            if sys.platform == 'win32':
                import ctypes
                hwnd = pygame.display.get_wm_info()['window']
                HWND_TOPMOST = -1
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOACTIVATE = 0x0010
                SWP_SHOWWINDOW = 0x0040
                
                if mouse_over_window or self.dragging:
                    # Si el mouse está sobre la ventana o está arrastrando, traerla al frente AGRESIVAMENTE
                    # Primero: BringWindowToTop para traerla al frente del Z-order
                    ctypes.windll.user32.BringWindowToTop(hwnd)
                    # Segundo: SetWindowPos con TOPMOST SIN noactivate para forzar que esté arriba
                    ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    # Tercero: SetForegroundWindow para darle el foco completo
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                else:
                    # Si el mouse no está encima, mantener topmost pero sin robar foco
                    ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            
            # Cambiar expresión solo si no está arrastrando
            if not self.dragging:
                # Si el mouse está dentro del círculo de la cara
                self.is_surprised = distance < (self.size//2 - 10)
            else:
                # Mientras arrastra, no cambiar la expresión
                pass
            
            # Limpiar pantalla con color magenta para transparencia
            screen.fill((255, 0, 255))
            
            # Renderizar la cara (imagen o dibujada según disponibilidad)
            self.render_face(screen)
            
            pygame.display.flip()
            clock.tick(30)  # 30 FPS
        
        # Cerrar pygame limpiamente
        try:
            pygame.quit()
        except:
            pass
    
    def start(self):
        """Inicia la carita en un thread separado"""
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        return thread
    
    def stop(self):
        """Detiene la carita"""
        self.running = False
        # Como es un thread daemon, morirá cuando el programa principal termine
