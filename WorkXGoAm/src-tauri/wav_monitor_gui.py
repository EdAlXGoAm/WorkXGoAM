#!/usr/bin/env python
import os
import time
import subprocess
import threading
import logging
import re
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from typing import List, Set, Dict, Optional
from datetime import datetime
import openai
from dotenv import load_dotenv
from pydub import AudioSegment

# Cargar variables de entorno para la API key
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('wav_monitor_gui')

# Configuración por defecto
DEFAULT_MONITOR_DIR = "D:/git-edalx/WorkXGoAm/WorkXGoAm/src-tauri"
CHECK_INTERVAL = 5  # Segundos entre cada comprobación
FILETOTTEXT_SCRIPT = "FileToText.py"  # Nombre del script principal
CONTEXT_FILE = "contexto.txt"  # Nombre del archivo de contexto
SUMMARY_STATE_FILE = ".summary_state.json"  # Archivo para mantener estado del resumen

# Argumentos fijos para el script FileToText.py
LANGUAGE = "en"
PROMPT = "Transcribe lo que escuchas, no omitas ninguna palabra"

class AudioTranscriber:
    """
    Maneja la transcripción rápida de archivos de audio usando Whisper.
    """
    
    WHISPER_1 = "whisper-1"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el transcriptor de audio.
        
        Args:
            api_key: API key de OpenAI. Si no se proporciona, se intentará cargar de las variables de entorno.
        """
        # Usar la API key proporcionada o intentar cargarla de las variables de entorno
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("No se proporcionó API key y no se encontró en las variables de entorno")
        
        # Inicializar cliente de OpenAI
        self.client = openai.OpenAI(api_key=self.api_key)
    
    def convert_wav_to_mp3(self, wav_file: str) -> str:
        """
        Convierte un archivo WAV a MP3 para mejor compatibilidad con la API.
        
        Args:
            wav_file: Ruta al archivo WAV.
            
        Returns:
            Ruta al archivo MP3 temporal convertido.
        """
        import tempfile
        
        # Crear directorio temporal si no existe
        temp_dir = os.path.join(tempfile.gettempdir(), "file_to_text")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generar nombre para archivo temporal MP3
        mp3_file = os.path.join(temp_dir, f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3")
        
        # Cargar el archivo WAV
        audio = AudioSegment.from_wav(wav_file)
        
        # Exportar como MP3 con buena calidad
        audio.export(mp3_file, format="mp3", bitrate="192k")
        
        return mp3_file
    
    def transcribe_audio(self, audio_file: str, language: str = "en") -> str:
        """
        Transcribe un archivo de audio utilizando Whisper.
        
        Args:
            audio_file: Ruta al archivo de audio.
            language: Código de idioma opcional para mejorar la transcripción.
            
        Returns:
            Texto transcrito del audio.
        """
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"El archivo {audio_file} no existe")
        
        try:
            with open(audio_file, "rb") as file_obj:
                # Preparar los parámetros para la transcripción rápida con Whisper
                params = {
                    "model": self.WHISPER_1,
                    "file": file_obj,
                    "response_format": "text",
                    "language": language
                }
                
                # Realizar la transcripción
                transcript = self.client.audio.transcriptions.create(**params)
                
                # Manejar la respuesta
                if hasattr(transcript, 'text'):
                    return transcript.text
                elif isinstance(transcript, str):
                    return transcript
                else:
                    # Intentar convertir a string como último recurso
                    return str(transcript)
                
        except Exception as e:
            return f"Error al transcribir el audio: {str(e)}"

class ContextGenerator:
    """
    Genera y actualiza un archivo de contexto basado en las transcripciones más recientes.
    """
    
    def __init__(self, directory: str, status_callback=None):
        """
        Inicializa el generador de contexto.
        
        Args:
            directory: Directorio donde se encuentran los archivos de transcripción.
            status_callback: Función para reportar el estado de las operaciones.
        """
        self.directory = directory
        self.context_file = os.path.join(directory, CONTEXT_FILE)
        self.summary_state_file = os.path.join(directory, SUMMARY_STATE_FILE)
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.status_callback = status_callback
        
        if self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
        
        logger.info(f"Generador de contexto inicializado para: {directory}")
    
    def get_most_recent_txt_files(self, count: int = 10) -> List[str]:
        """
        Obtiene los archivos TXT más recientes en el directorio, excluyendo archivos con silencio.
        
        Args:
            count: Número de archivos a retornar (hasta 10).
            
        Returns:
            Lista de rutas a los archivos TXT más recientes que contienen contenido.
        """
        txt_files = []
        for filename in os.listdir(self.directory):
            if filename.lower().endswith('.txt') and filename != CONTEXT_FILE and not filename.startswith('.'):
                full_path = os.path.join(self.directory, filename)
                
                # Verificar si el archivo contiene la etiqueta de silencio
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content.startswith("[silence]"):
                            # Omitir archivos que contienen solo silencio
                            continue
                except Exception:
                    # Si hay error al leer, incluir el archivo por precaución
                    pass
                
                mod_time = os.path.getmtime(full_path)
                txt_files.append((full_path, mod_time))
        
        # Ordenar por tiempo de modificación (más reciente primero)
        txt_files.sort(key=lambda x: x[1], reverse=True)
        
        # Devolver los archivos más recientes
        return [file_path for file_path, _ in txt_files[:count]]
    
    def get_most_recent_wav_files(self, count: int = 3) -> List[str]:
        """
        Obtiene los archivos WAV más recientes en el directorio.
        
        Args:
            count: Número de archivos a retornar.
            
        Returns:
            Lista de rutas a los archivos WAV más recientes.
        """
        wav_files = []
        for filename in os.listdir(self.directory):
            if filename.lower().endswith('.wav'):
                full_path = os.path.join(self.directory, filename)
                mod_time = os.path.getmtime(full_path)
                wav_files.append((full_path, mod_time))
        
        # Ordenar por tiempo de modificación (más reciente primero)
        wav_files.sort(key=lambda x: x[1], reverse=True)
        
        # Devolver los archivos más recientes
        return [file_path for file_path, _ in wav_files[:count]]
    
    def extract_keywords(self, text: str, count: int = 15) -> List[str]:
        """
        Extrae palabras clave de un texto.
        
        Args:
            text: Texto del que extraer palabras clave.
            count: Número máximo de palabras clave a extraer.
            
        Returns:
            Lista de palabras clave.
        """
        # Eliminar símbolos de puntuación y convertir a minúsculas
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        
        # Dividir en palabras
        words = text.split()
        
        # Palabras vacías comunes en inglés y español
        stop_words = set([
            "a", "an", "the", "and", "or", "but", "is", "are", "was", "were", 
            "el", "la", "los", "las", "un", "una", "y", "o", "pero", "es", "son", "era", "eran",
            "in", "on", "at", "to", "for", "with", "by", "from", "en", "sobre", "para", "con", "por", "de",
            "i", "you", "he", "she", "it", "we", "they", "yo", "tú", "él", "ella", "nosotros", "ellos",
            "this", "that", "these", "those", "esto", "eso", "estos", "esos",
            "que", "como", "cuando", "donde", "what", "how", "when", "where", "why", "who"
        ])
        
        # Filtrar palabras vacías
        filtered_words = [word for word in words if word not in stop_words and len(word) > 3]
        
        # Contar frecuencias
        from collections import Counter
        word_counts = Counter(filtered_words)
        
        # Obtener las palabras más comunes
        return [word for word, _ in word_counts.most_common(count)]
    
    def load_summary_state(self) -> Dict:
        """
        Carga el estado del resumen para mantener continuidad entre actualizaciones.
        
        Returns:
            Diccionario con el estado del resumen o diccionario vacío si no existe.
        """
        if os.path.exists(self.summary_state_file):
            try:
                with open(self.summary_state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error al cargar estado del resumen: {str(e)}")
                if self.status_callback:
                    self.status_callback(f"Error al cargar estado del resumen: {str(e)}")
        
        # Estado inicial
        return {
            "processed_files": [],
            "summary": "",
            "iteration": 0,
            "keywords": []
        }
    
    def save_summary_state(self, state: Dict):
        """
        Guarda el estado del resumen para mantener continuidad.
        
        Args:
            state: Diccionario con el estado actual del resumen.
        """
        try:
            with open(self.summary_state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error al guardar estado del resumen: {str(e)}")
            if self.status_callback:
                self.status_callback(f"Error al guardar estado del resumen: {str(e)}")
    
    def is_file_empty_or_silence(self, file_path: str) -> bool:
        """
        Determina si un archivo de transcripción está vacío o contiene silencio.
        
        Args:
            file_path: Ruta al archivo de transcripción.
            
        Returns:
            True si el archivo está vacío o solo contiene silencio, False en caso contrario.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return not content or content.startswith("[silence]")
        except Exception:
            # En caso de error, asumir que no está vacío
            return False
    
    def generate_iterative_summary(self, new_files: List[str], previous_state: Dict) -> Dict:
        """
        Genera un resumen iterativo basado en archivos nuevos y el estado anterior.
        
        Args:
            new_files: Lista de rutas a archivos nuevos a procesar.
            previous_state: Estado anterior del resumen.
            
        Returns:
            Diccionario con el nuevo estado del resumen.
        """
        # Filtrar archivos vacíos o con silencio
        valid_files = [f for f in new_files if not self.is_file_empty_or_silence(f)]
        
        if not valid_files:
            # Si no hay archivos válidos, mantener el estado anterior
            logger.info("No hay transcripciones válidas para actualizar el resumen")
            if self.status_callback:
                self.status_callback("No hay transcripciones válidas para actualizar el resumen")
            return previous_state
            
        if not self.api_key:
            # Si no hay API key, usar método basado en extractos
            return self.generate_extract_based_summary(valid_files, previous_state)
        
        # Extraer contenido de los nuevos archivos
        new_content = ""
        for file_path in valid_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        filename = os.path.basename(file_path)
                        new_content += f"\n--- {filename} ---\n{content}\n\n"
            except Exception as e:
                logger.error(f"Error al leer {os.path.basename(file_path)}: {str(e)}")
                if self.status_callback:
                    self.status_callback(f"Error al leer {os.path.basename(file_path)}: {str(e)}")
        
        if not new_content.strip():
            # No hay contenido nuevo relevante
            return previous_state
        
        # Preparar mensaje para GPT
        system_message = """
Eres un asistente especializado en resumir conversaciones. Tu tarea es actualizar un resumen existente 
incorporando nueva información de transcripciones recientes. Sigue estas reglas:

1. Mantén un tono conciso pero informativo.
2. Conserva los términos técnicos en inglés (estilo "Spanglish") que aparezcan en las transcripciones.
3. Si es la primera iteración, genera un resumen inicial de las transcripciones proporcionadas.
4. Si ya existe un resumen, incorpóralo como base y añade los nuevos elementos de la conversación.
5. Con cada iteración, refina y expande el resumen, sin repetir información.
6. Organiza el contenido de forma lógica, siguiendo el flujo temporal de la conversación.
7. NO incluyas metadatos como "Transcripción reciente:" o "Actualización:".
8. NO menciones el proceso de refinamiento ni el número de iteración.
9. Responde SÓLO con el resumen actualizado, sin introducciones ni conclusiones.
"""

        # Contenido del mensaje
        user_message = f"""
ITERACIÓN ACTUAL: {previous_state['iteration'] + 1}

RESUMEN ACTUAL:
{previous_state['summary'] if previous_state['summary'] else "No hay resumen previo. Esta es la primera iteración."}

NUEVAS TRANSCRIPCIONES:
{new_content}

Actualiza el resumen incorporando el contenido de las nuevas transcripciones.
Genera un resumen conciso que capture progresivamente los aspectos importantes de la conversación.
"""

        if self.status_callback:
            self.status_callback("Generando resumen con GPT-4o...")
        
        try:
            # Llamar a la API de Chat Completions
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3  # Temperatura baja para mayor consistencia
            )
            
            # Extraer el resumen generado
            updated_summary = response.choices[0].message.content.strip()
            
            # Actualizar palabras clave combinando las anteriores con nuevas
            all_text = previous_state.get('summary', '') + ' ' + new_content
            updated_keywords = self.extract_keywords(all_text)
            
            # Actualizar y devolver el nuevo estado
            return {
                "processed_files": previous_state["processed_files"] + [os.path.basename(f) for f in valid_files],
                "summary": updated_summary,
                "iteration": previous_state["iteration"] + 1,
                "keywords": updated_keywords,
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            logger.error(f"Error al generar resumen con GPT: {str(e)}")
            if self.status_callback:
                self.status_callback(f"Error al generar resumen con GPT: {str(e)}")
            # Si falla, usar método basado en extractos
            return self.generate_extract_based_summary(valid_files, previous_state)
    
    def generate_extract_based_summary(self, new_files: List[str], previous_state: Dict) -> Dict:
        """
        Genera un resumen basado en extractos cuando no es posible usar GPT.
        
        Args:
            new_files: Lista de rutas a archivos nuevos a procesar.
            previous_state: Estado anterior del resumen.
            
        Returns:
            Diccionario con el nuevo estado del resumen.
        """
        # Filtrar archivos vacíos o con silencio
        valid_files = [f for f in new_files if not self.is_file_empty_or_silence(f)]
        
        if not valid_files:
            # Si no hay archivos válidos, mantener el estado anterior
            return previous_state
        
        # Extraer contenido significativo de los nuevos archivos
        new_extracts = []
        all_text = previous_state.get('summary', '')
        
        for file_path in valid_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    all_text += ' ' + content
                    
                    # Tomar el primer párrafo significativo (más de 50 caracteres)
                    paragraphs = content.split('\n\n')
                    for paragraph in paragraphs:
                        clean_para = paragraph.strip()
                        if len(clean_para) > 50 and not clean_para.startswith('['):
                            new_extracts.append(f"- {clean_para}")
                            break
            except Exception as e:
                logger.error(f"Error al leer {os.path.basename(file_path)}: {str(e)}")
                if self.status_callback:
                    self.status_callback(f"Error al leer {os.path.basename(file_path)}: {str(e)}")
        
        # Actualizar el resumen
        updated_summary = previous_state.get('summary', '')
        if new_extracts:
            if updated_summary:
                updated_summary += "\n\nActualizaciones recientes:\n" + "\n".join(new_extracts)
            else:
                updated_summary = "Resumen de la conversación:\n" + "\n".join(new_extracts)
        
        # Actualizar palabras clave
        updated_keywords = self.extract_keywords(all_text)
        
        # Devolver el nuevo estado
        return {
            "processed_files": previous_state["processed_files"] + [os.path.basename(f) for f in valid_files],
            "summary": updated_summary,
            "iteration": previous_state["iteration"] + 1,
            "keywords": updated_keywords,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def update_context_file(self):
        """
        Actualiza el archivo de contexto con la información más reciente.
        
        Returns:
            Contenido del archivo de contexto actualizado o None si hubo error.
        """
        try:
            # Cargar el estado actual del resumen
            summary_state = self.load_summary_state()
            
            # Obtener archivos más recientes (hasta 10)
            recent_files = self.get_most_recent_txt_files(10)
            
            if not recent_files:
                logger.info("No hay archivos de transcripción para generar contexto")
                if self.status_callback:
                    self.status_callback("No hay archivos de transcripción para generar contexto")
                return None
            
            # Identificar archivos que aún no han sido procesados
            processed_basenames = set(summary_state.get("processed_files", []))
            new_files = [f for f in recent_files if os.path.basename(f) not in processed_basenames]
            
            # Si hay archivos nuevos, actualizar el resumen
            if new_files:
                logger.info(f"Encontrados {len(new_files)} archivos nuevos para actualizar el resumen")
                if self.status_callback:
                    self.status_callback(f"Encontrados {len(new_files)} archivos nuevos para actualizar el resumen")
                
                # Generar resumen iterativo con los nuevos archivos
                new_summary_state = self.generate_iterative_summary(new_files, summary_state)
                
                # Guardar el nuevo estado
                self.save_summary_state(new_summary_state)
                
                summary_state = new_summary_state
            
            # Construir el contenido del archivo de contexto
            context = "CONTEXTO DE CONVERSACIÓN\n"
            context += "=" * 30 + "\n\n"
            
            # Añadir palabras clave
            context += "PALABRAS CLAVE:\n"
            context += ", ".join(summary_state.get("keywords", [])[:20]) + "\n\n"
            
            # Añadir resumen de la conversación
            context += "RESUMEN DE LA CONVERSACIÓN:\n"
            context += summary_state.get("summary", "Sin resumen disponible") + "\n\n"
            
            # Añadir transcripciones completas (solo las 3 más recientes)
            context += "TRANSCRIPCIONES RECIENTES:\n"
            for file_path in recent_files[:3]:
                try:
                    filename = os.path.basename(file_path)
                    context += f"\n--- {filename} ---\n"
                    with open(file_path, 'r', encoding='utf-8') as f:
                        context += f.read() + "\n"
                except Exception:
                    pass
            
            # Escribir al archivo
            with open(self.context_file, 'w', encoding='utf-8') as f:
                f.write(context)
            
            logger.info(f"Archivo de contexto actualizado (iteración {summary_state['iteration']})")
            if self.status_callback:
                self.status_callback(f"Archivo de contexto actualizado (iteración {summary_state['iteration']})")
            
            return context
            
        except Exception as e:
            logger.error(f"Error al actualizar el archivo de contexto: {str(e)}")
            if self.status_callback:
                self.status_callback(f"Error al actualizar el archivo de contexto: {str(e)}")
            return None

class WavMonitorGUI:
    """
    Interfaz gráfica para monitorear y transcribir archivos WAV.
    """
    
    def __init__(self, root):
        self.root = root
        self.root.title("Monitor de Archivos de Audio")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Variables
        self.monitor_dir = tk.StringVar(value=DEFAULT_MONITOR_DIR)
        self.status_var = tk.StringVar(value="Listo para comenzar")
        
        # Componentes para monitoreo
        self.setup_ui()
        
        # Estado del procesador
        self.monitoring = False
        self.processor = None
        self.context_generator = None
        self.transcriber = None
        
        # Intentar inicializar el transcriptor
        try:
            self.transcriber = AudioTranscriber()
        except Exception as e:
            logger.error(f"Error al inicializar transcriptor: {str(e)}")
            self.update_status(f"Error: {str(e)}")
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Panel superior para configuración
        config_frame = ttk.LabelFrame(self.root, text="Configuración")
        config_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(config_frame, text="Directorio a monitorear:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(config_frame, textvariable=self.monitor_dir, width=50).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(config_frame, text="Explorar", command=self.select_directory).grid(row=0, column=2, padx=5, pady=5)
        
        # Panel de estado
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(status_frame, text="Estado:").pack(side="left", padx=5)
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left", padx=5, fill="x", expand=True)
        
        # Panel de botones de acción
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(action_frame, text="Generar Contexto", command=self.generate_context).pack(side="left", padx=5, pady=5)
        ttk.Button(action_frame, text="Transcribir Últimos Audios", command=self.transcribe_recent_audios).pack(side="left", padx=5, pady=5)
        
        # Panel de contenido
        content_frame = ttk.LabelFrame(self.root, text="Contenido")
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Area de texto con scroll
        self.text_area = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.text_area.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Barra de estado inferior
        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill="x", side="bottom", padx=10, pady=5)
        
        ttk.Label(status_bar, text="Monitor de Archivos de Audio").pack(side="left")
        quit_button = ttk.Button(status_bar, text="Salir", command=self.root.destroy)
        quit_button.pack(side="right")
    
    def select_directory(self):
        """Abre un diálogo para seleccionar el directorio a monitorear"""
        directory = filedialog.askdirectory(
            initialdir=self.monitor_dir.get(),
            title="Seleccionar directorio para monitorear"
        )
        if directory:
            self.monitor_dir.set(directory)
            self.update_status(f"Directorio cambiado a: {directory}")
    
    def update_status(self, message):
        """Actualiza el mensaje de estado y lo añade al historial"""
        self.status_var.set(message)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.text_area.see(tk.END)
        logger.info(message)
    
    def clear_content(self):
        """Limpia el área de contenido"""
        self.text_area.delete(1.0, tk.END)
    
    def generate_context(self):
        """Genera el archivo de contexto con los archivos actuales"""
        directory = self.monitor_dir.get()
        
        if not os.path.exists(directory):
            self.update_status(f"Error: El directorio {directory} no existe")
            return
        
        self.update_status("Generando contexto...")
        
        # Inicializar el generador de contexto si no existe
        if not self.context_generator or self.context_generator.directory != directory:
            self.context_generator = ContextGenerator(
                directory=directory,
                status_callback=self.update_status
            )
        
        # Ejecutar en un hilo separado para no bloquear la interfaz
        threading.Thread(
            target=self._generate_context_thread,
            daemon=True
        ).start()
    
    def _generate_context_thread(self):
        """Función que se ejecuta en un hilo para generar el contexto"""
        try:
            context = self.context_generator.update_context_file()
            
            # Actualizar la interfaz
            self.root.after(0, lambda: self.clear_content())
            if context:
                self.root.after(0, lambda: self.text_area.insert(tk.END, context))
                self.root.after(0, lambda: self.update_status("Contexto generado con éxito"))
            else:
                self.root.after(0, lambda: self.update_status("No se pudo generar el contexto"))
                
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"Error al generar contexto: {str(e)}"))
    
    def transcribe_recent_audios(self):
        """Transcribe los tres archivos de audio más recientes usando Whisper"""
        directory = self.monitor_dir.get()
        
        if not os.path.exists(directory):
            self.update_status(f"Error: El directorio {directory} no existe")
            return
        
        if not self.transcriber:
            try:
                self.transcriber = AudioTranscriber()
            except Exception as e:
                self.update_status(f"Error al inicializar transcriptor: {str(e)}")
                return
        
        # Inicializar el generador de contexto si no existe
        if not self.context_generator or self.context_generator.directory != directory:
            self.context_generator = ContextGenerator(
                directory=directory,
                status_callback=self.update_status
            )
        
        # Obtener los archivos WAV más recientes
        self.update_status("Buscando archivos de audio recientes...")
        
        # Ejecutar en un hilo separado para no bloquear la interfaz
        threading.Thread(
            target=self._transcribe_recent_thread,
            daemon=True
        ).start()
    
    def _transcribe_recent_thread(self):
        """Función que se ejecuta en un hilo para transcribir los archivos recientes"""
        try:
            recent_files = self.context_generator.get_most_recent_wav_files(3)
            
            if not recent_files:
                self.root.after(0, lambda: self.update_status("No se encontraron archivos WAV para transcribir"))
                return
            
            self.root.after(0, lambda: self.clear_content())
            # self.root.after(0, lambda: self.update_status(f"Transcribiendo {len(recent_files)} archivos..."))
            
            for wav_file in recent_files:
                filename = os.path.basename(wav_file)
                # self.root.after(0, lambda f=filename: self.update_status(f"Transcribiendo {f}..."))
                
                # Convertir a MP3 si es necesario
                audio_file = wav_file
                if wav_file.lower().endswith('.wav'):
                    try:
                        mp3_file = self.transcriber.convert_wav_to_mp3(wav_file)
                        audio_file = mp3_file
                    except Exception as e:
                        self.root.after(0, lambda e=e: self.update_status(f"Error al convertir a MP3: {str(e)}"))
                        continue
                
                # Transcribir con Whisper
                try:
                    transcription = self.transcriber.transcribe_audio(
                        audio_file=audio_file,
                        language="en"  # Usar inglés como se solicitó
                    )
                    
                    self.root.after(0, lambda f=filename, t=transcription: self.text_area.insert(tk.END, f"\n--- {f} ---\n{t}\n\n"))
                    # self.root.after(0, lambda f=filename: self.update_status(f"Transcripción de {f} completada"))
                    
                except Exception as e:
                    self.root.after(0, lambda f=filename, e=e: self.update_status(f"Error al transcribir {f}: {str(e)}"))
                
                # Limpiar archivos temporales
                if 'mp3_file' in locals() and os.path.exists(mp3_file):
                    try:
                        os.remove(mp3_file)
                    except:
                        pass
            
            # self.root.after(0, lambda: self.update_status("Transcripciones completadas"))
            
        except Exception as e:
            self.root.after(0, lambda e=e: self.update_status(f"Error en la transcripción: {str(e)}"))

def main():
    """Función principal para iniciar la aplicación"""
    root = tk.Tk()
    app = WavMonitorGUI(root)
    
    # Configurar cierre de la aplicación
    def on_closing():
        if messagebox.askokcancel("Salir", "¿Desea salir de la aplicación?"):
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Iniciar ciclo de eventos
    root.mainloop()

if __name__ == "__main__":
    main() 