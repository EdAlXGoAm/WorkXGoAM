"""
RTSP Stream Service - Transcodifica streams RTSP a HLS para visualización web con audio
"""

import subprocess
import threading
import os
import shutil
import tempfile
from typing import Optional, Generator
from queue import Queue, Empty
import time


class RTSPStreamService:
    """
    Servicio para transcodificar streams RTSP usando FFmpeg.
    Soporta dos modos:
    - MJPEG: Solo video, baja latencia
    - HLS: Video + Audio, mayor latencia pero con sonido
    """
    
    def __init__(self):
        self._streams: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._hls_base_dir = os.path.join(tempfile.gettempdir(), 'workx_hls_streams')
        
        # Crear directorio base para HLS si no existe
        os.makedirs(self._hls_base_dir, exist_ok=True)
    
    def start_stream(self, stream_id: str, rtsp_url: str, with_audio: bool = True) -> bool:
        """
        Inicia la captura de un stream RTSP.
        
        Args:
            stream_id: Identificador único para el stream
            rtsp_url: URL del stream RTSP
            with_audio: Si True, usa HLS con audio. Si False, usa MJPEG sin audio.
            
        Returns:
            True si se inició correctamente
        """
        with self._lock:
            if stream_id in self._streams:
                return True  # Ya existe
            
            try:
                if with_audio:
                    return self._start_hls_stream(stream_id, rtsp_url)
                else:
                    return self._start_mjpeg_stream(stream_id, rtsp_url)
            except Exception as e:
                print(f"[RTSPStreamService] Error iniciando stream '{stream_id}': {e}")
                return False
    
    def _start_hls_stream(self, stream_id: str, rtsp_url: str) -> bool:
        """Inicia un stream HLS con audio."""
        # Crear directorio para este stream
        stream_dir = os.path.join(self._hls_base_dir, stream_id)
        if os.path.exists(stream_dir):
            shutil.rmtree(stream_dir)
        os.makedirs(stream_dir, exist_ok=True)
        
        playlist_path = os.path.join(stream_dir, 'stream.m3u8')
        segment_path = os.path.join(stream_dir, 'segment%03d.ts')
        
        # Comando FFmpeg para HLS con audio
        # -hls_time 2: segmentos de 2 segundos
        # -hls_list_size 3: mantener solo 3 segmentos en la playlist
        # -hls_flags delete_segments: borrar segmentos viejos
        ffmpeg_cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-i', rtsp_url,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-f', 'hls',
            '-hls_time', '2',
            '-hls_list_size', '5',
            '-hls_flags', 'delete_segments+append_list',
            '-hls_segment_filename', segment_path,
            playlist_path
        ]
        
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        stop_event = threading.Event()
        
        self._streams[stream_id] = {
            'process': process,
            'stop_event': stop_event,
            'rtsp_url': rtsp_url,
            'mode': 'hls',
            'stream_dir': stream_dir,
            'playlist_path': playlist_path
        }
        
        print(f"[RTSPStreamService] Stream HLS '{stream_id}' iniciado: {rtsp_url}")
        return True
    
    def _start_mjpeg_stream(self, stream_id: str, rtsp_url: str) -> bool:
        """Inicia un stream MJPEG sin audio."""
        frame_queue: Queue = Queue(maxsize=2)
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-i', rtsp_url,
            '-f', 'mjpeg',
            '-q:v', '5',
            '-r', '15',
            '-an',
            '-'
        ]
        
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=10**6,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
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
            'rtsp_url': rtsp_url,
            'mode': 'mjpeg'
        }
        
        print(f"[RTSPStreamService] Stream MJPEG '{stream_id}' iniciado: {rtsp_url}")
        return True
    
    def stop_stream(self, stream_id: str) -> bool:
        """Detiene un stream activo."""
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
            
            # Limpiar directorio HLS si existe
            if stream_data.get('mode') == 'hls' and stream_data.get('stream_dir'):
                try:
                    shutil.rmtree(stream_data['stream_dir'], ignore_errors=True)
                except Exception:
                    pass
            
            print(f"[RTSPStreamService] Stream '{stream_id}' detenido")
            return True
    
    def get_stream_mode(self, stream_id: str) -> Optional[str]:
        """Retorna el modo del stream ('hls' o 'mjpeg')."""
        with self._lock:
            if stream_id in self._streams:
                return self._streams[stream_id].get('mode')
            return None
    
    def get_hls_playlist_path(self, stream_id: str) -> Optional[str]:
        """Retorna la ruta al archivo de playlist HLS."""
        with self._lock:
            if stream_id in self._streams:
                return self._streams[stream_id].get('playlist_path')
            return None
    
    def get_hls_directory(self, stream_id: str) -> Optional[str]:
        """Retorna el directorio donde están los archivos HLS."""
        with self._lock:
            if stream_id in self._streams:
                return self._streams[stream_id].get('stream_dir')
            return None
    
    def get_frame_generator(self, stream_id: str) -> Optional[Generator[bytes, None, None]]:
        """Obtiene un generador de frames para un stream MJPEG."""
        with self._lock:
            if stream_id not in self._streams:
                return None
            if self._streams[stream_id].get('mode') != 'mjpeg':
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
                    continue
                except Exception:
                    break
        
        return generate()
    
    def _frame_reader(self, process: subprocess.Popen, queue: Queue, stop_event: threading.Event):
        """Lee frames JPEG del proceso FFmpeg y los pone en la cola."""
        buffer = b''
        jpeg_start = b'\xff\xd8'
        jpeg_end = b'\xff\xd9'
        
        try:
            while not stop_event.is_set() and process.poll() is None:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                
                buffer += chunk
                
                while True:
                    start_idx = buffer.find(jpeg_start)
                    if start_idx == -1:
                        buffer = b''
                        break
                    
                    end_idx = buffer.find(jpeg_end, start_idx + 2)
                    if end_idx == -1:
                        buffer = buffer[start_idx:]
                        break
                    
                    frame = buffer[start_idx:end_idx + 2]
                    buffer = buffer[end_idx + 2:]
                    
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
                queue.put_nowait(None)
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
