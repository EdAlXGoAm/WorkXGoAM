"""
RTSP Stream Service - Transcodifica streams RTSP a MJPEG para visualización web
"""

import subprocess
import threading
from typing import Optional, Generator
from queue import Queue, Empty
import time


class RTSPStreamService:
    """
    Servicio para transcodificar streams RTSP a MJPEG usando FFmpeg.
    Sirve los frames como un stream HTTP multipart para visualización en navegadores.
    """
    
    def __init__(self):
        self._streams: dict[str, dict] = {}
        self._lock = threading.Lock()
    
    def start_stream(self, stream_id: str, rtsp_url: str) -> bool:
        """
        Inicia la captura de un stream RTSP.
        
        Args:
            stream_id: Identificador único para el stream
            rtsp_url: URL del stream RTSP (ej: rtsp://user:pass@ip:port/stream)
            
        Returns:
            True si se inició correctamente, False si ya existe o hubo error
        """
        with self._lock:
            if stream_id in self._streams:
                return True  # Ya existe
            
            try:
                # Cola para frames JPEG
                frame_queue: Queue = Queue(maxsize=2)
                
                # Proceso FFmpeg para transcodificar RTSP a MJPEG
                # -rtsp_transport tcp: usar TCP para mayor estabilidad
                # -f mjpeg: formato de salida MJPEG
                # -q:v 5: calidad (1-31, menor es mejor)
                # -r 15: 15 fps para reducir carga
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-rtsp_transport', 'tcp',
                    '-i', rtsp_url,
                    '-f', 'mjpeg',
                    '-q:v', '5',
                    '-r', '15',
                    '-an',  # Sin audio
                    '-'
                ]
                
                process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=10**6
                )
                
                # Thread para leer frames del proceso
                stop_event = threading.Event()
                reader_thread = threading.Thread(
                    target=self._frame_reader,
                    args=(process, frame_queue, stop_event),
                    daemon=True
                )
                reader_thread.start()
                
                self._streams[stream_id] = {
                    'process': process,
                    'queue': frame_queue,
                    'stop_event': stop_event,
                    'thread': reader_thread,
                    'rtsp_url': rtsp_url
                }
                
                print(f"[RTSPStreamService] Stream '{stream_id}' iniciado: {rtsp_url}")
                return True
                
            except Exception as e:
                print(f"[RTSPStreamService] Error iniciando stream '{stream_id}': {e}")
                return False
    
    def stop_stream(self, stream_id: str) -> bool:
        """
        Detiene un stream activo.
        
        Args:
            stream_id: Identificador del stream a detener
            
        Returns:
            True si se detuvo correctamente
        """
        with self._lock:
            if stream_id not in self._streams:
                return False
            
            stream_data = self._streams.pop(stream_id)
            stream_data['stop_event'].set()
            
            process = stream_data['process']
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
            
            print(f"[RTSPStreamService] Stream '{stream_id}' detenido")
            return True
    
    def get_frame_generator(self, stream_id: str) -> Optional[Generator[bytes, None, None]]:
        """
        Obtiene un generador de frames para un stream.
        
        Args:
            stream_id: Identificador del stream
            
        Returns:
            Generador que produce frames JPEG, o None si el stream no existe
        """
        with self._lock:
            if stream_id not in self._streams:
                return None
            queue = self._streams[stream_id]['queue']
        
        def generate():
            while True:
                try:
                    frame = queue.get(timeout=5)
                    if frame is None:
                        break
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                except Empty:
                    # Timeout, enviar frame vacío para mantener conexión
                    continue
                except Exception:
                    break
        
        return generate()
    
    def _frame_reader(self, process: subprocess.Popen, queue: Queue, stop_event: threading.Event):
        """
        Lee frames JPEG del proceso FFmpeg y los pone en la cola.
        """
        buffer = b''
        jpeg_start = b'\xff\xd8'
        jpeg_end = b'\xff\xd9'
        
        try:
            while not stop_event.is_set() and process.poll() is None:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                
                buffer += chunk
                
                # Buscar frames JPEG completos
                while True:
                    start_idx = buffer.find(jpeg_start)
                    if start_idx == -1:
                        buffer = b''
                        break
                    
                    end_idx = buffer.find(jpeg_end, start_idx + 2)
                    if end_idx == -1:
                        # Frame incompleto, mantener desde el inicio
                        buffer = buffer[start_idx:]
                        break
                    
                    # Frame completo encontrado
                    frame = buffer[start_idx:end_idx + 2]
                    buffer = buffer[end_idx + 2:]
                    
                    # Poner en cola, descartar si está llena
                    try:
                        queue.put_nowait(frame)
                    except:
                        try:
                            queue.get_nowait()
                            queue.put_nowait(frame)
                        except:
                            pass
        except Exception as e:
            print(f"[RTSPStreamService] Error en frame_reader: {e}")
        finally:
            try:
                queue.put_nowait(None)  # Señal de fin
            except:
                pass
    
    def is_stream_active(self, stream_id: str) -> bool:
        """Verifica si un stream está activo."""
        with self._lock:
            return stream_id in self._streams
    
    def get_active_streams(self) -> list[str]:
        """Retorna lista de IDs de streams activos."""
        with self._lock:
            return list(self._streams.keys())
    
    def stop_all(self):
        """Detiene todos los streams activos."""
        stream_ids = self.get_active_streams()
        for stream_id in stream_ids:
            self.stop_stream(stream_id)


# Instancia global del servicio
rtsp_service = RTSPStreamService()

