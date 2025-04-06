import os
import argparse
import sys
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Union
import openai
from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import tempfile
import concurrent.futures
import time
import re

# Cargar variables de entorno (para la API key)
load_dotenv()

class AudioTranscriber:
    """
    Clase que busca el archivo WAV más reciente en un directorio y lo transcribe usando OpenAI.
    """
    
    # Constantes para modelos de transcripción
    GPT4O_MINI_TRANSCRIBE = "gpt-4o-mini-transcribe"
    WHISPER_1 = "whisper-1"
    GPT4O = "gpt-4o"
    
    # Constantes para detección de silencio
    SILENCE_TAG = "[silence]"
    MIN_SILENCE_LENGTH = 1000  # 1 segundo
    SILENCE_THRESHOLD = -40  # dB (más negativo = más sensible)
    MIN_AUDIO_LENGTH = 0.5  # Duración mínima en segundos
    MIN_TRANSCRIPTION_LENGTH = 5  # Caracteres mínimos para considerar una transcripción válida
    
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
    
    def find_most_recent_wav(self, directory: str) -> Optional[str]:
        """
        Encuentra el archivo WAV más reciente en el directorio especificado.
        
        Args:
            directory: Ruta del directorio donde buscar archivos WAV.
            
        Returns:
            Ruta del archivo WAV más reciente o None si no se encuentra ninguno.
        """
        if not os.path.exists(directory):
            raise FileNotFoundError(f"El directorio {directory} no existe")
        
        wav_files = []
        
        for file in os.listdir(directory):
            if file.lower().endswith('.wav'):
                full_path = os.path.join(directory, file)
                mod_time = os.path.getmtime(full_path)
                wav_files.append((full_path, mod_time))
        
        if not wav_files:
            return None
        
        # Ordenar por tiempo de modificación (más reciente primero)
        wav_files.sort(key=lambda x: x[1], reverse=True)
        
        return wav_files[0][0]
    
    def convert_wav_to_mp3(self, wav_file: str) -> str:
        """
        Convierte un archivo WAV a MP3 para mejor compatibilidad con la API.
        
        Args:
            wav_file: Ruta al archivo WAV.
            
        Returns:
            Ruta al archivo MP3 temporal convertido.
        """
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
    
    def get_audio_info(self, audio_file: str) -> dict:
        """
        Obtiene información sobre un archivo de audio.
        
        Args:
            audio_file: Ruta al archivo de audio.
            
        Returns:
            Diccionario con información del archivo.
        """
        if audio_file.lower().endswith('.wav'):
            audio = AudioSegment.from_wav(audio_file)
        elif audio_file.lower().endswith('.mp3'):
            audio = AudioSegment.from_mp3(audio_file)
        else:
            return {"error": "Formato no soportado"}
        
        # Calcular tamaño en MB
        file_size_mb = os.path.getsize(audio_file) / (1024 * 1024)
        
        return {
            "duración_segundos": len(audio) / 1000,
            "canales": audio.channels,
            "sample_width": audio.sample_width,
            "frame_rate": audio.frame_rate,
            "tamaño_mb": round(file_size_mb, 2)
        }
    
    def is_silent_audio(self, audio_file: str) -> bool:
        """
        Determina si un archivo de audio contiene principalmente silencio.
        
        Args:
            audio_file: Ruta al archivo de audio.
            
        Returns:
            True si el audio es principalmente silencio, False en caso contrario.
        """
        try:
            # Cargar el audio según el formato
            if audio_file.lower().endswith('.wav'):
                audio = AudioSegment.from_wav(audio_file)
            elif audio_file.lower().endswith('.mp3'):
                audio = AudioSegment.from_mp3(audio_file)
            else:
                return False  # No podemos determinar si es silencio para formatos no soportados
            
            # Verificar duración mínima
            if len(audio) / 1000 < self.MIN_AUDIO_LENGTH:
                return True
            
            # Detectar partes no silenciosas
            non_silent_parts = detect_nonsilent(
                audio, 
                min_silence_len=self.MIN_SILENCE_LENGTH,
                silence_thresh=self.SILENCE_THRESHOLD
            )
            
            # Calcular ratio de contenido no silencioso
            total_audio_len = len(audio)
            if total_audio_len == 0:
                return True
                
            non_silent_len = sum((end - start) for start, end in non_silent_parts)
            non_silent_ratio = non_silent_len / total_audio_len
            
            # Si menos del 10% del audio contiene sonido, considerarlo silencio
            return non_silent_ratio < 0.1
            
        except Exception as e:
            # Si hay un error, asumimos que no es silencio para evitar falsos positivos
            return False
    
    def is_empty_transcription(self, text: str) -> bool:
        """
        Determina si una transcripción está vacía o solo contiene elementos no significativos.
        
        Args:
            text: Texto de la transcripción.
            
        Returns:
            True si la transcripción está vacía o solo contiene ruido.
        """
        if not text or text.startswith("ERROR:"):
            return True
        
        # Eliminar espacios y caracteres no significativos
        cleaned_text = re.sub(r'[\s.,;:!?"\'-]+', '', text)
        
        # Verificar longitud mínima
        if len(cleaned_text) < self.MIN_TRANSCRIPTION_LENGTH:
            return True
        
        # Patrones que indican audio vacío o silencio
        silence_patterns = [
            r'\b(no audio|no speech|no sound|silence|empty|nada|vacío|silencio)\b',
            r'\bno (hay|contiene) (audio|sonido|voz|voces|palabras)\b',
            r'\b(cannot|couldn\'t|can\'t) (transcribe|detect|hear)\b',
            r'\b(no se puede|no pude|no puedo) (transcribir|detectar|escuchar)\b',
            r'\bthe audio (is|contains|appears to be) (empty|silence|silent)\b',
            r'\bel audio (está|parece estar|es|contiene) (vacío|silencio|silencioso)\b'
        ]
        
        # Comprobar si algún patrón coincide
        for pattern in silence_patterns:
            if re.search(pattern, text.lower()):
                return True
        
        return False
    
    def transcribe_audio(self, 
                         audio_file: str, 
                         language: Optional[str] = None,
                         prompt: Optional[str] = None,
                         model: Optional[str] = None) -> str:
        """
        Transcribe un archivo de audio utilizando el modelo especificado.
        
        Args:
            audio_file: Ruta al archivo de audio.
            language: Código de idioma opcional para mejorar la transcripción.
            prompt: Texto opcional para guiar la transcripción y mejorar la precisión.
            model: Modelo de transcripción a utilizar.
            
        Returns:
            Texto transcrito del audio o etiqueta de silencio.
        """
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"El archivo {audio_file} no existe")
        
        # Verificar si el audio es silencio
        if self.is_silent_audio(audio_file):
            return self.SILENCE_TAG
        
        try:
            with open(audio_file, "rb") as file_obj:
                # Preparar los parámetros para la transcripción
                params = {
                    "model": model,
                    "file": file_obj,
                    "response_format": "text"
                }
                
                # Añadir parámetros opcionales según el modelo
                if language:
                    params["language"] = language
                
                # Añadir prompt SOLO si es GPT-4o Mini Transcribe
                if prompt and model == self.GPT4O_MINI_TRANSCRIBE:
                    params["prompt"] = prompt
                
                # Realizar la transcripción
                transcript = self.client.audio.transcriptions.create(**params)
                
                # Manejar la respuesta
                if hasattr(transcript, 'text'):
                    transcription_text = transcript.text
                elif isinstance(transcript, str):
                    transcription_text = transcript
                else:
                    # Intentar convertir a string como último recurso
                    transcription_text = str(transcript)
                
                # Verificar si la transcripción está vacía o solo contiene ruido
                if self.is_empty_transcription(transcription_text):
                    return self.SILENCE_TAG
                    
                return transcription_text
                
        except Exception as e:
            raise Exception(f"Error al transcribir el audio con modelo {model}: {str(e)}")
    
    def _transcribe_with_model(self, 
                             audio_file: str, 
                             model: str,
                             language: Optional[str] = None,
                             prompt: Optional[str] = None) -> Tuple[str, str]:
        """
        Función auxiliar para transcribir con un modelo específico.
        Diseñada para ser usada con ThreadPoolExecutor.
        
        Args:
            audio_file: Ruta al archivo de audio.
            model: Modelo de transcripción a utilizar.
            language: Código de idioma opcional.
            prompt: Prompt para la transcripción (solo aplicable a GPT-4o Mini Transcribe).
            
        Returns:
            Tupla (modelo, texto_transcrito) o (modelo, error_message).
        """
        try:
            # El prompt solo se pasa al modelo GPT-4o Mini Transcribe
            current_prompt = prompt if model == self.GPT4O_MINI_TRANSCRIBE else None
            
            result = self.transcribe_audio(
                audio_file=audio_file,
                language=language,
                prompt=current_prompt,
                model=model
            )
            return model, result
        except Exception as e:
            error_msg = f"ERROR: {str(e)}"
            return model, error_msg
    
    def transcribe_with_all_models(self, 
                                 audio_file: str, 
                                 language: Optional[str] = None,
                                 prompt: Optional[str] = None,
                                 verbose: bool = False) -> Dict[str, str]:
        """
        Transcribe un archivo de audio utilizando todos los modelos disponibles en paralelo.
        
        Args:
            audio_file: Ruta al archivo de audio.
            language: Código de idioma opcional para mejorar la transcripción.
            prompt: Texto opcional para guiar la transcripción y mejorar la precisión.
            verbose: Si se deben mostrar mensajes de progreso.
            
        Returns:
            Diccionario con los resultados de cada modelo.
        """
        # Verificar si el audio es silencio antes de intentar transcribir
        if self.is_silent_audio(audio_file):
            if verbose:
                print("Archivo detectado como silencio, omitiendo transcripción")
            return {
                self.GPT4O_MINI_TRANSCRIBE: self.SILENCE_TAG,
                self.WHISPER_1: self.SILENCE_TAG
            }
        
        # Mostrar información del archivo
        audio_info = self.get_audio_info(audio_file)
        # print("\nInformación del archivo de audio:")
        # for key, value in audio_info.items():
        #     print(f"- {key}: {value}")
        
        # Verificar tamaño para advertir sobre posibles problemas
        if audio_info["tamaño_mb"] > 24:
            print("⚠️ ADVERTENCIA: El archivo supera los 24 MB (límite API: 25 MB)")
        
        start_time = time.time()
        
        if verbose:
            print("Iniciando transcripciones en paralelo...")
        
        # Lista de modelos a utilizar
        models = [self.GPT4O_MINI_TRANSCRIBE, self.WHISPER_1]
        results = {}
        
        # Usar ThreadPoolExecutor para ejecutar las transcripciones en paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(models)) as executor:
            # Crear un futuro para cada modelo
            futures = {
                executor.submit(
                    self._transcribe_with_model, 
                    audio_file, 
                    model, 
                    language, 
                    prompt
                ): model for model in models
            }
            
            # Procesar los resultados a medida que se completen
            for future in concurrent.futures.as_completed(futures):
                model = futures[future]
                try:
                    model_name, result = future.result()
                    results[model_name] = result
                    if verbose:
                        print(f"✓ Transcripción completada: {model_name} ({time.time() - start_time:.2f}s)")
                except Exception as e:
                    results[model] = f"ERROR: {str(e)}"
                    if verbose:
                        print(f"✗ Error en transcripción {model}: {str(e)}")
        
        if verbose:
            print(f"Todas las transcripciones completadas en {time.time() - start_time:.2f} segundos")
        
        # Verificar si ambos modelos detectaron silencio
        silence_count = sum(1 for result in results.values() if result == self.SILENCE_TAG)
        if silence_count == len(models):
            if verbose:
                print("Todos los modelos detectaron silencio o audio vacío")
            
        return results
    
    def optimize_transcription(self, transcriptions: Dict[str, str]) -> Union[str, None]:
        """
        Utiliza GPT-4o para generar una versión optimizada combinando ambas transcripciones.
        Si ambas transcripciones indican silencio, devuelve la etiqueta de silencio.
        
        Args:
            transcriptions: Diccionario con las transcripciones de cada modelo.
            
        Returns:
            Transcripción optimizada en español con estilo espanglish o None si es silencio.
        """
        # Extraer las transcripciones
        gpt4o_mini_text = transcriptions.get(self.GPT4O_MINI_TRANSCRIBE, "")
        whisper_text = transcriptions.get(self.WHISPER_1, "")
        
        # Verificar si ambas transcripciones indican silencio
        if gpt4o_mini_text == self.SILENCE_TAG and whisper_text == self.SILENCE_TAG:
            return self.SILENCE_TAG
        
        # Si solo una transcripción indica silencio, usar la otra
        if gpt4o_mini_text == self.SILENCE_TAG:
            return whisper_text
        if whisper_text == self.SILENCE_TAG:
            return gpt4o_mini_text
        
        # Verificar si tenemos ambas transcripciones
        if not gpt4o_mini_text or not whisper_text:
            available = [k for k, v in transcriptions.items() if v and not v.startswith("ERROR")]
            if not available:
                return self.SILENCE_TAG
            elif len(available) == 1:
                return transcriptions[available[0]]
        
        # Crear prompt para GPT-4o
        system_message = """
Eres un TRADUCTOR INGLÉS-ESPAÑOL experto en transcripciones de audio y traducción. Tu tarea es combinar dos transcripciones 
diferentes del mismo audio para crear la mejor versión posible en español, manteniendo ciertos 
términos técnicos o laborales en inglés (estilo "espanglish").

INSTRUCCIONES IMPORTANTES:
1. Responde ÚNICAMENTE con la transcripción optimizada.
2. NO incluyas frases introductorias como "Aquí tienes la transcripción optimizada" o similares.
3. NO añadas comentarios, explicaciones o conclusiones.
4. SOLO debes proporcionar el texto transcrito y traducido.
5. Si ambas transcripciones indican que el audio está vacío o es silencio, responde únicamente con "[silence]".

Reglas para la transcripción:
1. La transcripción de Whisper suele capturar más palabras y contenido, pero puede tener más errores de coherencia.
2. La transcripción de GPT-4o Mini Transcribe puede omitir el inicio o final, pero suele ser más coherente y fiel.
3. Debes generar una transcripción en español que combine lo mejor de ambas.
4. Mantén en inglés términos técnicos, nombres propios y términos laborales comunes (ej. "Project Manager", "deadline", "team leader").
5. El resultado debe sonar natural para un hispanohablante que usa términos técnicos en inglés.
6. No agregues información que no esté en alguna de las transcripciones.
"""

        user_message = f"""
A continuación te presento dos transcripciones del mismo audio:

TRANSCRIPCIÓN GPT-4o MINI:
{gpt4o_mini_text}

TRANSCRIPCIÓN WHISPER:
{whisper_text}

Genera ÚNICAMENTE la transcripción optimizada en español que combine lo mejor de ambas, manteniendo términos técnicos en inglés.
No incluyas frases introductorias ni explicaciones adicionales, solo el texto transcrito.
Si ambas transcripciones indican que el audio está vacío o es silencio, responde únicamente con "[silence]".
"""

        try:
            # Llamar a la API de Chat Completions
            response = self.client.chat.completions.create(
                model=self.GPT4O,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3  # Temperatura baja para mayor consistencia
            )
            
            # Obtener la respuesta generada
            result = response.choices[0].message.content.strip()
            
            # Verificar si la respuesta es la etiqueta de silencio
            if result == self.SILENCE_TAG or self.is_empty_transcription(result):
                return self.SILENCE_TAG
            
            # Devolver la respuesta generada
            return result
            
        except Exception as e:
            return f"Error al optimizar la transcripción: {str(e)}"


def main():
    """
    Función principal que procesa los argumentos de línea de comandos y ejecuta la transcripción.
    """
    parser = argparse.ArgumentParser(description="Transcribe el archivo WAV más reciente en un directorio.")
    parser.add_argument("--dir", "-d", type=str, default=".", 
                        help="Directorio donde buscar archivos WAV (por defecto: directorio actual)")
    parser.add_argument("--file", "-f", type=str,
                        help="Ruta directa a un archivo de audio específico (WAV/MP3)")
    parser.add_argument("--language", "-l", type=str, default="es", 
                        help="Código de idioma para la transcripción (por defecto: es)")
    parser.add_argument("--prompt", "-p", type=str, 
                        help="Prompt para guiar la transcripción (solo aplicable a GPT-4o Mini Transcribe)")
    parser.add_argument("--single-model", "-m", type=str, choices=["gpt-4o-mini-transcribe", "whisper-1"],
                        help="Usar solo un modelo específico en lugar de ambos")
    parser.add_argument("--api-key", "-k", type=str, 
                        help="API key de OpenAI (opcional, por defecto usa la variable de entorno OPENAI_API_KEY)")
    parser.add_argument("--convert", "-c", action="store_true", 
                        help="Convertir a MP3 antes de transcribir")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Mostrar información detallada durante el proceso")
    parser.add_argument("--no-optimize", "-n", action="store_true",
                        help="No generar la transcripción optimizada con GPT-4o")
    
    args = parser.parse_args()
    
    # Determinar si se debe mostrar información detallada
    verbose = args.verbose
    
    try:
        # Crear instancia del transcriptor
        transcriber = AudioTranscriber(api_key=args.api_key)
        
        # Determinar archivo de audio a procesar
        if args.file:
            if not os.path.exists(args.file):
                print(f"Error: El archivo {args.file} no existe")
                return 1
            audio_file = args.file
            if verbose:
                print(f"Usando archivo especificado: {audio_file}")
        else:
            # Buscar el archivo WAV más reciente
            wav_file = transcriber.find_most_recent_wav(args.dir)
            
            if not wav_file:
                print(f"No se encontraron archivos WAV en el directorio {args.dir}")
                return 1
            
            audio_file = wav_file
            if verbose:
                print(f"Archivo WAV más reciente encontrado: {audio_file}")
        
        # Verificar si el audio es silencio antes de continuar
        if transcriber.is_silent_audio(audio_file):
            if verbose:
                print("El archivo de audio contiene principalmente silencio.")
            
            print(f"[{transcriber.GPT4O_MINI_TRANSCRIBE}]")
            print(transcriber.SILENCE_TAG)
            print()
            
            print(f"[{transcriber.WHISPER_1}]")
            print(transcriber.SILENCE_TAG)
            print()
            
            print("[transcripción-optimizada]")
            print(transcriber.SILENCE_TAG)
            
            return 0
        
        # Convertir a MP3 si se solicita
        if args.convert or audio_file.lower().endswith('.wav'):
            mp3_file = transcriber.convert_wav_to_mp3(audio_file)
            audio_file = mp3_file
            if verbose:
                print(f"Archivo convertido a MP3: {mp3_file}")
        
        # Iniciar el proceso de transcripción
        if verbose:
            print("Iniciando proceso de transcripción...")
            if args.prompt:
                print("NOTA: El prompt solo se aplicará al modelo GPT-4o Mini Transcribe, no a Whisper")
        
        start_time = time.time()
        
        # Si se especifica un solo modelo, usar ese, de lo contrario usar todos
        if args.single_model:
            # Si el modelo es whisper y hay un prompt, advertir que no se usará
            if args.single_model == transcriber.WHISPER_1 and args.prompt and verbose:
                print("AVISO: El prompt no se aplicará a Whisper, solo es compatible con GPT-4o Mini Transcribe")
                
            # Aplicar prompt solo si es compatible con el modelo
            current_prompt = args.prompt if args.single_model == transcriber.GPT4O_MINI_TRANSCRIBE else None
            
            transcribed_text = transcriber.transcribe_audio(
                audio_file,
                language=args.language,
                prompt=current_prompt,
                model=args.single_model
            )
            
            print(f"[{args.single_model}]")
            print(transcribed_text)
        else:
            # Transcribir con todos los modelos en paralelo
            results = transcriber.transcribe_with_all_models(
                audio_file,
                language=args.language,
                prompt=args.prompt,
                verbose=verbose
            )
            
            # Verificar si ambos modelos detectaron silencio
            all_silence = all(result == transcriber.SILENCE_TAG for result in results.values())
            
            # Mostrar resultados de cada modelo
            for model, text in results.items():
                print(f"[{model}]")
                print(text)
                print()
            
            # Generar y mostrar la transcripción optimizada si no se detectó silencio en ambos modelos
            if not args.no_optimize and not all_silence:
                if verbose:
                    print("Generando transcripción optimizada con GPT-4o...")
                
                optimize_start = time.time()
                optimized_text = transcriber.optimize_transcription(results)
                
                if verbose:
                    print(f"Transcripción optimizada generada en {time.time() - optimize_start:.2f} segundos")
                
                print("[transcripción-optimizada]")
                print(optimized_text)
            elif all_silence:
                # Si ambos modelos detectaron silencio, mostrar etiqueta de silencio
                print("[transcripción-optimizada]")
                print(transcriber.SILENCE_TAG)
        
        if verbose:
            print(f"Tiempo total de procesamiento: {time.time() - start_time:.2f} segundos")
            
        # Si creamos un archivo MP3 temporal, eliminarlo
        if 'mp3_file' in locals() and os.path.exists(mp3_file) and mp3_file.startswith(tempfile.gettempdir()):
            os.remove(mp3_file)
            if verbose:
                print(f"Archivo temporal eliminado: {mp3_file}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 