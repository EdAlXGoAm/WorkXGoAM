#!/usr/bin/env python
import os
import time
import subprocess
import threading
import logging
import re
import json
from typing import List, Set, Dict
from datetime import datetime
import heapq
from collections import Counter
import openai
import sys
import argparse
from FileToText import AudioTranscriber as FTTranscriber
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('wav_monitor')

# Configuración: monitor-dir obligatorio
parser = argparse.ArgumentParser()
parser.add_argument("--monitor-dir", dest="monitor_dir", type=str, required=True, help="Directorio a monitorear")
args = parser.parse_args()
MONITOR_DIR = args.monitor_dir
CHECK_INTERVAL = 5  # Segundos entre cada comprobación
FILETOTTEXT_SCRIPT = "FileToText.py"  # Nombre del script principal
CONTEXT_INTERVAL = 60  # Segundos entre actualizaciones de contexto
CONTEXT_FILE = "contexto.txt"  # Nombre del archivo de contexto
SUMMARY_STATE_FILE = ".summary_state.json"  # Archivo para mantener estado del resumen

# Argumentos fijos para el script FileToText.py
LANGUAGE = "en"
PROMPT = "Transcribe lo que escuchas, no omitas ninguna palabra"

# Cargar API key desde el archivo .env
API_KEY = os.getenv("OPENAI_API_KEY")

class ContextGenerator:
    """
    Genera y actualiza un archivo de contexto basado en las transcripciones más recientes.
    """
    
    def __init__(self, directory: str):
        """
        Inicializa el generador de contexto.
        
        Args:
            directory: Directorio donde se encuentran los archivos de transcripción.
        """
        self.directory = directory
        self.context_file = os.path.join(directory, CONTEXT_FILE)
        self.summary_state_file = os.path.join(directory, SUMMARY_STATE_FILE)
        self.running = False
        self.thread = None
        self.api_key = API_KEY
        if self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
        logger.info(f"Generador de contexto inicializado para: {directory}")
    
    def get_most_recent_txt_files(self, count: int = 10) -> List[str]:
        """
        Obtiene los archivos TXT más recientes en el directorio, excluyendo archivos con silencio.
        
        Args:
            count: Número de archivos a retornar (ahora hasta 10).
            
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
        """
        try:
            # Cargar el estado actual del resumen
            summary_state = self.load_summary_state()
            
            # Obtener archivos más recientes (hasta 10)
            recent_files = self.get_most_recent_txt_files(10)
            
            if not recent_files:
                logger.info("No hay archivos de transcripción para generar contexto")
                return
            
            # Identificar archivos que aún no han sido procesados
            processed_basenames = set(summary_state.get("processed_files", []))
            new_files = [f for f in recent_files if os.path.basename(f) not in processed_basenames]
            
            if new_files:
                logger.info(f"Encontrados {len(new_files)} archivos nuevos para actualizar el resumen")
                
                # Generar resumen iterativo con los nuevos archivos
                new_summary_state = self.generate_iterative_summary(new_files, summary_state)
                
                # Guardar el nuevo estado
                self.save_summary_state(new_summary_state)
                
                # Construir el contenido del archivo de contexto
                context = "CONTEXTO DE CONVERSACIÓN\n"
                context += "=" * 30 + "\n\n"
                
                # Añadir palabras clave
                context += "PALABRAS CLAVE:\n"
                context += ", ".join(new_summary_state.get("keywords", [])[:20]) + "\n\n"
                
                # Añadir resumen de la conversación
                context += "RESUMEN DE LA CONVERSACIÓN:\n"
                context += new_summary_state.get("summary", "Sin resumen disponible") + "\n\n"
                
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
                
                logger.info(f"Archivo de contexto actualizado (iteración {new_summary_state['iteration']}, {len(new_files)} transcripciones nuevas)")
            else:
                logger.info("No hay transcripciones nuevas para actualizar el resumen")
            
        except Exception as e:
            logger.error(f"Error al actualizar el archivo de contexto: {str(e)}")
    
    def context_thread_func(self):
        """
        Función principal del hilo de actualización de contexto.
        """
        logger.info("Iniciando hilo de actualización de contexto")
        
        while self.running:
            try:
                # Actualizar el archivo de contexto
                self.update_context_file()
            except Exception as e:
                logger.error(f"Error en el hilo de contexto: {str(e)}")
            
            # Esperar hasta la próxima actualización
            time.sleep(CONTEXT_INTERVAL)
    
    def start(self):
        """
        Inicia el hilo de actualización de contexto.
        """
        if self.thread is not None and self.thread.is_alive():
            logger.warning("El hilo de contexto ya está en ejecución")
            return
        
        self.running = True
        self.thread = threading.Thread(
            target=self.context_thread_func,
            daemon=True
        )
        self.thread.start()
        logger.info("Hilo de actualización de contexto iniciado")
    
    def stop(self):
        """
        Detiene el hilo de actualización de contexto.
        """
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=5)
            logger.info("Hilo de actualización de contexto detenido")


class WavProcessor:
    """
    Monitorea un directorio en busca de archivos WAV sin archivos TXT correspondientes
    y los procesa automáticamente.
    """
    
    def __init__(self, directory: str, check_interval: int = 5):
        """
        Inicializa el monitor de archivos WAV.
        
        Args:
            directory: Directorio a monitorear.
            check_interval: Intervalo de tiempo entre comprobaciones (segundos).
        """
        self.directory = os.path.abspath(directory)
        self.check_interval = check_interval
        self.processing_files = set()  # Archivos actualmente en procesamiento
        self.lock = threading.Lock()   # Para acceso seguro a processing_files
        
        # Inicializar el generador de contexto
        self.context_generator = ContextGenerator(self.directory)
        # Inicializar transcriptor de FileToText como librería
        self.ft_transcriber = FTTranscriber(api_key=API_KEY)
        
        # Verificar que el directorio exista
        if not os.path.exists(self.directory):
            raise FileNotFoundError(f"El directorio {self.directory} no existe")
            
        logger.info(f"Iniciando monitoreo en: {self.directory}")
        logger.info(f"Usando idioma: {LANGUAGE}")
        logger.info(f"Usando prompt: {PROMPT}")
    
    def get_wav_files(self) -> List[str]:
        """
        Obtiene la lista de archivos WAV en el directorio.
        
        Returns:
            Lista de rutas absolutas a archivos WAV.
        """
        wav_files = []
        for filename in os.listdir(self.directory):
            if filename.lower().endswith('.wav'):
                wav_files.append(os.path.join(self.directory, filename))
        return wav_files
    
    def get_txt_files(self) -> Set[str]:
        """
        Obtiene el conjunto de nombres base de archivos TXT en el directorio.
        
        Returns:
            Conjunto de nombres base de archivos TXT (sin extensión).
        """
        txt_base_names = set()
        for filename in os.listdir(self.directory):
            if filename.lower().endswith('.txt') and filename != CONTEXT_FILE:
                # Obtener el nombre base sin extensión
                base_name = os.path.splitext(filename)[0]
                txt_base_names.add(base_name)
        return txt_base_names
    
    def is_txt_in_progress(self, wav_base_name: str) -> bool:
        """
        Verifica si hay un archivo temporal que indica que el procesamiento está en curso.
        
        Args:
            wav_base_name: Nombre base del archivo WAV (sin extensión).
            
        Returns:
            True si hay un procesamiento en curso, False en caso contrario.
        """
        temp_marker = os.path.join(self.directory, f".{wav_base_name}.inprogress")
        return os.path.exists(temp_marker)
    
    def mark_txt_in_progress(self, wav_base_name: str) -> bool:
        """
        Marca un archivo como "en procesamiento" creando un archivo temporal.
        
        Args:
            wav_base_name: Nombre base del archivo WAV (sin extensión).
            
        Returns:
            True si se pudo marcar exitosamente, False si ya está marcado.
        """
        temp_marker = os.path.join(self.directory, f".{wav_base_name}.inprogress")
        if os.path.exists(temp_marker):
            return False
        
        try:
            # Crear archivo temporal con timestamp
            with open(temp_marker, 'w') as f:
                f.write(str(time.time()))
            return True
        except:
            return False
    
    def unmark_txt_in_progress(self, wav_base_name: str):
        """
        Elimina la marca de "en procesamiento".
        
        Args:
            wav_base_name: Nombre base del archivo WAV (sin extensión).
        """
        temp_marker = os.path.join(self.directory, f".{wav_base_name}.inprogress")
        if os.path.exists(temp_marker):
            try:
                os.remove(temp_marker)
            except:
                logger.warning(f"No se pudo eliminar el marcador temporal para {wav_base_name}")
    
    def process_wav_file(self, wav_file: str):
        """
        Procesa un archivo WAV usando FileToText.py y guarda la salida en un archivo TXT.
        
        Args:
            wav_file: Ruta al archivo WAV a procesar.
        """
        try:
            base_name = os.path.basename(wav_file)
            wav_base_name = os.path.splitext(base_name)[0]
            output_file = os.path.join(self.directory, f"{wav_base_name}.txt")
            
            # Marcar como en procesamiento con un archivo temporal
            if not self.mark_txt_in_progress(wav_base_name):
                logger.warning(f"El archivo {base_name} ya está siendo procesado por otro hilo")
                return
            
            logger.info(f"Procesando: {base_name}")
            
            # Procesar WAV usando FileToText como librería
            transcriber = self.ft_transcriber
            audio_file = wav_file
            mp3_file = None
            if wav_file.lower().endswith('.wav'):
                mp3_file = transcriber.convert_wav_to_mp3(wav_file)
                audio_file = mp3_file

            # Transcribir con todos los modelos
            results = transcriber.transcribe_with_all_models(
                audio_file,
                language=LANGUAGE,
                prompt=PROMPT
            )

            # Generar transcripción optimizada
            optimized_text = transcriber.optimize_transcription(results)

            # Preparar texto de salida
            if optimized_text == transcriber.SILENCE_TAG:
                logger.info(f"Silencio detectado en archivo: {base_name}")
                output_text = "[silence]\nArchivo de audio vacío o sin contenido audible."
            else:
                output_text = f"\n{optimized_text}\n"

            # # Eliminar archivo MP3 temporal
            # if mp3_file and os.path.exists(mp3_file):
            #     try:
            #         os.remove(mp3_file)
            #     except:
            #         pass

            # Guardar en archivo
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output_text)

            logger.info(f"Archivo guardado: {os.path.basename(output_file)}")
            
        except Exception as e:
            logger.error(f"Error al procesar {os.path.basename(wav_file)}: {str(e)}")
        finally:
            # Eliminar el archivo de la lista de procesamiento
            with self.lock:
                self.processing_files.discard(wav_file)
            
            # Eliminar el marcador de "en procesamiento"
            self.unmark_txt_in_progress(wav_base_name)
    
    def check_and_process(self):
        """
        Verifica si hay archivos WAV sin procesar y los procesa en hilos separados.
        """
        wav_files = self.get_wav_files()
        txt_base_names = self.get_txt_files()
        files_to_process = []
        
        # Primero, identificar todos los archivos que necesitan ser procesados
        for wav_file in wav_files:
            wav_base_name = os.path.splitext(os.path.basename(wav_file))[0]
            
            # Verificar si no existe un archivo TXT correspondiente,
            # no está siendo procesado por este script,
            # y no tiene un marcador .inprogress
            with self.lock:
                if (wav_base_name not in txt_base_names and 
                    wav_file not in self.processing_files and
                    not self.is_txt_in_progress(wav_base_name)):
                    files_to_process.append(wav_file)
        
        # Luego, iniciar el procesamiento de cada archivo
        for wav_file in files_to_process:
            wav_base_name = os.path.splitext(os.path.basename(wav_file))[0]
            
            # Doble verificación antes de iniciar el procesamiento
            with self.lock:
                if wav_file not in self.processing_files:
                    # Marcar como en procesamiento
                    self.processing_files.add(wav_file)
                    
                    # Iniciar un hilo para procesar el archivo
                    thread = threading.Thread(
                        target=self.process_wav_file,
                        args=(wav_file,),
                        daemon=True  # Para que el hilo se cierre cuando el programa principal termina
                    )
                    thread.start()
                    logger.info(f"Iniciado hilo para procesar: {os.path.basename(wav_file)}")
    
    def start_monitoring(self):
        """
        Inicia el monitoreo continuo del directorio.
        """
        try:
            logger.info("Monitoreo iniciado. Presiona Ctrl+C para detener.")
            
            # Iniciar el hilo de actualización de contexto
            self.context_generator.start()
            
            while True:
                self.check_and_process()
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoreo detenido por el usuario.")
            self.context_generator.stop()
        except Exception as e:
            logger.error(f"Error en el monitoreo: {str(e)}")
            self.context_generator.stop()

def main():
    """
    Función principal.
    """
    try:
        # Asegurarse de que el directorio existe
        if not os.path.exists(MONITOR_DIR):
            os.makedirs(MONITOR_DIR)
            logger.info(f"Directorio creado: {MONITOR_DIR}")
        
        # Iniciar el procesador de WAV
        processor = WavProcessor(MONITOR_DIR, CHECK_INTERVAL)
        processor.start_monitoring()
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 