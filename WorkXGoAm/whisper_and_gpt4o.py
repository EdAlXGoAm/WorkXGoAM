import os
import time
import queue
import threading
import tempfile
import wave
import logging
import pyaudio
from openai import AzureOpenAI
from dotenv import load_dotenv

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno desde un archivo .env
load_dotenv()

# Configuración de Azure OpenAI
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = "2024-02-01"  # Versión actual de la API, puede cambiar en el futuro
WHISPER_DEPLOYMENT_NAME = os.getenv("WHISPER_DEPLOYMENT_NAME")  # Nombre de tu despliegue de Whisper
GPT4_DEPLOYMENT_NAME = os.getenv("GPT4_DEPLOYMENT_NAME")  # Nombre de tu despliegue de GPT-4o

# Parámetros de grabación de audio
RATE = 16000  # Frecuencia de muestreo en Hz (común para Whisper)
CHUNK = 1024  # Tamaño del buffer de audio
FORMAT = pyaudio.paInt16  # Formato de audio
CHANNELS = 1  # Mono
RECORD_SECONDS = 5  # Grabar en segmentos de 5 segundos

class AudioTranscriber:
    def __init__(self):
        # Inicializar cliente de Azure OpenAI
        self.client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        
        # Inicializar PyAudio
        self.audio = pyaudio.PyAudio()
        
        # Cola para almacenar segmentos de audio
        self.audio_queue = queue.Queue()
        
        # Cola para almacenar transcripciones
        self.transcription_queue = queue.Queue()
        
        # Bandera para controlar la ejecución de hilos
        self.running = False
        
        # Almacenar oraciones completas para enviar a GPT-4
        self.current_sentence = ""
        
        # Almacenar la última transcripción parcial
        self.previous_transcription = ""
        
        logger.info("Transcriptor de audio inicializado correctamente")

    def start(self):
        """Inicia la captura de audio, transcripción y traducción"""
        self.running = True
        
        # Iniciar hilos para grabar audio, transcribir y traducir
        self.record_thread = threading.Thread(target=self.record_audio)
        self.transcribe_thread = threading.Thread(target=self.transcribe_audio)
        self.translate_thread = threading.Thread(target=self.translate_text)
        
        self.record_thread.daemon = True
        self.transcribe_thread.daemon = True
        self.translate_thread.daemon = True
        
        self.record_thread.start()
        self.transcribe_thread.start()
        self.translate_thread.start()
        
        logger.info("Sistema iniciado - presione Ctrl+C para detener")
        
        try:
            # Mantener el programa en ejecución
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Detiene todos los procesos"""
        self.running = False
        
        # Esperar a que terminen los hilos
        if hasattr(self, 'record_thread'):
            self.record_thread.join(timeout=1)
        if hasattr(self, 'transcribe_thread'):
            self.transcribe_thread.join(timeout=1)
        if hasattr(self, 'translate_thread'):
            self.translate_thread.join(timeout=1)
        
        # Cerrar PyAudio
        self.audio.terminate()
        
        logger.info("Sistema detenido")

    def record_audio(self):
        """Graba audio continuamente en segmentos y los coloca en la cola"""
        # Abrir stream de micrófono
        stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        logger.info("Grabación de audio iniciada - hable al micrófono")
        
        while self.running:
            # Grabar un segmento de audio
            frames = []
            for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                if not self.running:
                    break
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            
            # Si tenemos audio, crear un archivo temporal y ponerlo en la cola
            if frames and self.running:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                    # Guardar el audio como archivo WAV
                    with wave.open(temp_file.name, 'wb') as wf:
                        wf.setnchannels(CHANNELS)
                        wf.setsampwidth(self.audio.get_sample_size(FORMAT))
                        wf.setframerate(RATE)
                        wf.writeframes(b''.join(frames))
                    
                    # Poner el nombre del archivo en la cola para transcripción
                    self.audio_queue.put(temp_file.name)
        
        # Cerrar el stream cuando termine
        stream.stop_stream()
        stream.close()

    def transcribe_audio(self):
        """Procesa archivos de audio y los transcribe usando Whisper"""
        logger.info("Proceso de transcripción iniciado")
        
        while self.running:
            try:
                # Obtener archivo de audio de la cola (con timeout para permitir finalización del hilo)
                audio_file_path = self.audio_queue.get(timeout=1)
                
                # Transcribir audio con Whisper
                try:
                    with open(audio_file_path, "rb") as audio_file:
                        result = self.client.audio.transcriptions.create(
                            file=audio_file,
                            model=WHISPER_DEPLOYMENT_NAME
                        )
                    
                    # Procesar el resultado
                    transcription = result.text
                    
                    # Añadir la transcripción a la cola para traducción si no está vacía
                    if transcription.strip():
                        # Actualizar la transcripción actual
                        self.process_transcription(transcription)
                    
                    # Eliminar el archivo temporal
                    os.remove(audio_file_path)
                    
                except Exception as e:
                    logger.error(f"Error al transcribir audio: {str(e)}")
                
                # Marcar la tarea como completada
                self.audio_queue.task_done()
                
            except queue.Empty:
                # La cola está vacía, continuar esperando
                pass

    def process_transcription(self, transcription):
        """Procesa la transcripción para identificar oraciones completas"""
        # Eliminar espacios adicionales
        transcription = transcription.strip()
        
        # Si la transcripción está vacía, ignorar
        if not transcription:
            return
        
        # Mostrar la transcripción para depuración
        logger.info(f"Transcripción: {transcription}")
        
        # Buscar oraciones completas (terminadas en puntos, signos de interrogación o exclamación)
        sentence_endings = ['.', '!', '?']
        
        # Determinar si tenemos una oración completa
        if any(ending in transcription for ending in sentence_endings):
            # Si hay una oración completa, añadirla a la transcripción actual y enviarla para traducción
            self.current_sentence += " " + transcription
            self.transcription_queue.put(self.current_sentence.strip())
            self.current_sentence = ""
        else:
            # Si no es una oración completa, acumularla para el siguiente fragmento
            self.current_sentence += " " + transcription
            
            # Si la acumulación es demasiado larga (más de 100 caracteres), enviarla de todos modos
            if len(self.current_sentence) > 100:
                self.transcription_queue.put(self.current_sentence.strip())
                self.current_sentence = ""

    def translate_text(self):
        """Traduce el texto transcrito usando GPT-4o"""
        logger.info("Proceso de traducción iniciado")
        
        while self.running:
            try:
                # Obtener texto para traducir (con timeout para permitir finalización del hilo)
                text_to_translate = self.transcription_queue.get(timeout=1)
                
                # Llamar a GPT-4o para traducir
                try:
                    response = self.client.chat.completions.create(
                        model=GPT4_DEPLOYMENT_NAME,
                        messages=[
                            {"role": "system", "content": "Eres un traductor en tiempo real. Traduce el siguiente texto a español manteniendo el tono y contexto. Responde solo con la traducción, sin explicaciones adicionales."},
                            {"role": "user", "content": text_to_translate}
                        ],
                        temperature=0.3,
                        max_tokens=200
                    )
                    
                    # Obtener la traducción
                    translation = response.choices[0].message.content
                    
                    # Mostrar la traducción
                    print("\n" + "="*50)
                    print(f"Texto original: {text_to_translate}")
                    print(f"Traducción: {translation}")
                    print("="*50 + "\n")
                    
                except Exception as e:
                    logger.error(f"Error al traducir texto: {str(e)}")
                
                # Marcar la tarea como completada
                self.transcription_queue.task_done()
                
            except queue.Empty:
                # La cola está vacía, continuar esperando
                pass

def main():
    """Función principal"""
    # Verificar que las credenciales estén configuradas
    if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
        logger.error("Error: Las variables de entorno AZURE_OPENAI_API_KEY y AZURE_OPENAI_ENDPOINT deben estar configuradas")
        return
    
    if not WHISPER_DEPLOYMENT_NAME or not GPT4_DEPLOYMENT_NAME:
        logger.error("Error: Las variables de entorno WHISPER_DEPLOYMENT_NAME y GPT4_DEPLOYMENT_NAME deben estar configuradas")
        return
    
    # Crear y iniciar el transcriptor de audio
    transcriber = AudioTranscriber()
    
    print("\n" + "="*50)
    print("Sistema de transcripción y traducción en tiempo real")
    print("Usando Whisper y GPT-4o de Azure OpenAI")
    print("Presione Ctrl+C para detener")
    print("="*50 + "\n")
    
    # Iniciar el sistema
    transcriber.start()

if __name__ == "__main__":
    main()
