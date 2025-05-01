import os
import time
import wave
import threading
import queue
from datetime import datetime

import pyaudio
import openai
from openai import AzureOpenAI  # Azure OpenAI SDK

try:
    import soundcard as sc  # type: ignore
except ImportError:
    sc = None  # soundcard no está disponible

try:
    import argostranslate.translate as argos_translate  # type: ignore
except ImportError:
    argos_translate = None  # type: ignore
    print("⚠️  La librería 'argos-translate' no está instalada. Se intentará instalarla automáticamente al primer uso si es necesaria.")

import numpy as np

# ======================== CONFIGURACIÓN =========================
# Ajusta tu clave en la variable de entorno OPENAI_API_KEY o aquí
API_KEY = ""
MODEL = "whisper-1"  # Modelo de transcripción a utilizar

# Parámetros de la captura de audio
CHUNK = 1024           # Tamaño del buffer de PyAudio
FORMAT = pyaudio.paInt16  # Formato de audio (16-bit PCM)
CHANNELS = 1           # Mono
RATE = 44100           # Frecuencia de muestreo (Hz)
SEGMENT_SECONDS = 5    # Duración de cada fragmento a transcribir (s)

# Añadir constante para modelo de traducción
TRANSLATE_MODEL = "gpt-4o"

# Credenciales Azure (se usan sólo si --azure)
AZURE_ENDPOINT = "https://voiceaistudio1905074196.openai.azure.com/"
AZURE_DEPLOYMENT = "gpt-4.1-mini"  # Nombre de la implementación
AZURE_API_VERSION = "2025-01-01-preview"
AZURE_KEY = ""  # Ajusta tu clave en la variable de entorno AZURE_OPENAI_KEY
AZURE_TRANSLATE_MODEL = AZURE_DEPLOYMENT
AZURE_WHISPER_DEPLOYMENT = "whisper"  # Nombre del deployment de Whisper en Azure

# ===============================================================

# Parámetros de línea de comandos
import argparse

parser = argparse.ArgumentParser(description="Transcripción en tiempo real desde micrófono o salida de audio de la PC")
parser.add_argument("--source", choices=["mic", "output"], default="mic", help="Fuente de audio a capturar (mic=micrófono, output=audio del sistema)")
parser.add_argument("--outdir", default="registros", help="Directorio donde guardar los registros de texto")
parser.add_argument("--azure", action="store_true", help="Usar Azure OpenAI para la traducción con GPT-4.1-mini")
parser.add_argument("--local", action="store_true", help="Usar Whisper local en vez de la API de OpenAI/Azure")
parser.add_argument(
    "--local-model",
    default="small",
    help="Modelo de Whisper local a usar (tiny, base, small, medium, large, turbo)",
)
args = parser.parse_args()

# Flag global para activar el uso exclusivo de Argos Translate tras el primer fallo
USE_ARGOS_TRANSLATE_ONLY = False
USE_LOCAL_WHISPER = False


# ---------------------------------------------------------------
# Utilidades para buscar dispositivo de loopback WASAPI (solo Windows)

def find_loopback_device(pa: pyaudio.PyAudio) -> int | None:
    """Devuelve el índice del primer dispositivo WASAPI Loopback disponible (o None)."""
    try:
        host_api_count = pa.get_host_api_count()
    except Exception:
        host_api_count = 0

    wasapi_index = None
    for i in range(host_api_count):
        api_info = pa.get_host_api_info_by_index(i)
        if api_info.get("type") == pyaudio.paWASAPI:
            wasapi_index = api_info["index"]
            break

    if wasapi_index is None:
        return None

    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["hostApi"] == wasapi_index and info.get("isLoopback"):
            return i
    # Fallback: buscar "loopback" en el nombre
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        name = info.get("name", "").lower()
        if "loopback" in name and info["maxInputChannels"] > 0:
            return i
    return None


def grabador(audio_q: "queue.Queue[list[bytes]]", stop_evt: threading.Event):
    """Captura audio desde la fuente seleccionada y lo envía por fragmentos al *queue*."""
    p = pyaudio.PyAudio()

    device_index = None
    use_soundcard = False

    if args.source == "output":
        # Primero intentamos con PyAudio WASAPI
        device_index = find_loopback_device(p)
        if device_index is None:
            # Si falla, intentamos con soundcard
            if sc is not None:
                use_soundcard = True
            else:
                print("⚠️  No se encontró dispositivo loopback ni biblioteca soundcard. Se usará el micrófono por defecto.")

    if use_soundcard:
        # Buscar micrófonos loopback
        loopbacks = [m for m in sc.all_microphones(include_loopback=True) if getattr(m, "isloopback", False)]
        if not loopbacks:
            print("⚠️  No se encontró micrófono loopback en soundcard. Abortando.")
            stop_evt.set()
            return

        mic = loopbacks[0]
        src_txt = f"salida del sistema (soundcard: {mic.name})"
        print(f"🎙️  Grabando desde {src_txt}…  (Ctrl+C para detener)")

        with mic.recorder(samplerate=RATE) as rec:
            while not stop_evt.is_set():
                data = rec.record(numframes=int(RATE * SEGMENT_SECONDS))  # ndarray float32 (-1,1)
                if data.size == 0:
                    continue
                pcm16 = (np.clip(data, -1, 1) * 32767).astype(np.int16).tobytes()
                audio_q.put([pcm16])
            return  # Salimos cuando stop_evt se setea

    # ----- PyAudio path -----
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
        input_device_index=device_index,
    )

    src_txt = (
        "salida del sistema (WASAPI)" if args.source == "output" and device_index is not None else "micrófono"
    )
    print(f"🎙️  Grabando desde {src_txt}…  (Ctrl+C para detener)")

    try:
        while not stop_evt.is_set():
            frames: list[bytes] = []
            for _ in range(int(RATE / CHUNK * SEGMENT_SECONDS)):
                # read() puede lanzar OverflowError si el sistema no da abasto → silenciar
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
                if stop_evt.is_set():
                    break
            if frames:
                audio_q.put(frames)
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


def transcriptor(audio_q: "queue.Queue[list[bytes]]", stop_evt: threading.Event):
    """Recibe fragmentos desde *audio_q*, los guarda en WAV y los transcribe."""
    global USE_LOCAL_WHISPER
    if not API_KEY:
        raise RuntimeError("Se requiere la variable de entorno OPENAI_API_KEY o establecer API_KEY manualmente.")

    # Cliente OpenAI (para Whisper y, si no se usa Azure, para GPT estándar)
    client = openai.OpenAI(api_key=API_KEY)

    # Cliente Azure OpenAI (solo si se solicitó con --azure)
    azure_client = None
    if args.azure:
        if not AZURE_KEY:
            print("⚠️  --azure especificado pero falta la clave 'AZURE_OPENAI_KEY'. Se usará OpenAI estándar para la traducción.")
        else:
            try:
                azure_client = AzureOpenAI(
                    api_version=AZURE_API_VERSION,
                    azure_endpoint=AZURE_ENDPOINT,
                    api_key=AZURE_KEY,
                )
            except Exception as e:
                print(f"⚠️  Error al inicializar AzureOpenAI: {e}. Se usará OpenAI estándar para la traducción.")

    # Preparar modelo Whisper local si se solicitó con --local o si USE_LOCAL_WHISPER está activado
    local_whisper_model = None
    if args.local or USE_LOCAL_WHISPER:
        try:
            import whisper  # type: ignore
        except ImportError:
            print(
                "⚠️  No se encontró la librería 'openai-whisper'. Instálala con 'pip install -U openai-whisper' o desactiva --local."
            )
            stop_evt.set()
            return

        try:
            model_to_load = args.local_model if args.local else "small"
            print(f"🔊 Cargando modelo Whisper local '{model_to_load}'… (puede tardar)")
            local_whisper_model = whisper.load_model(model_to_load)
        except Exception as e:
            print(f"⚠️  Error al cargar el modelo Whisper local: {e}")
            stop_evt.set()
            return

    idx = 0

    # Asegurarnos de que el directorio de salida exista
    os.makedirs(args.outdir, exist_ok=True)

    while not stop_evt.is_set() or not audio_q.empty():
        try:
            frames = audio_q.get(timeout=0.5)
        except queue.Empty:
            continue

        wav_filename = f"segment_{idx}.wav"
        # Guardar el fragmento a WAV temporal
        with wave.open(wav_filename, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b"".join(frames))

        # Transcripción (local o vía API)
        try:
            # Intentar transcripción vía API a menos que USE_LOCAL_WHISPER esté activado
            if USE_LOCAL_WHISPER or (args.local and local_whisper_model is not None):
                # ---- Whisper local ----
                if not local_whisper_model:
                    import whisper  # type: ignore
                    local_whisper_model = whisper.load_model("small")
                result_local = local_whisper_model.transcribe(wav_filename)
                texto = result_local.get("text", "")
            else:
                # ---- Whisper vía API (OpenAI o Azure) ----
                try:
                    with open(wav_filename, "rb") as f:
                        if args.azure and azure_client is not None:
                            respuesta = azure_client.audio.transcriptions.create(
                                model=AZURE_WHISPER_DEPLOYMENT,
                                file=f,
                                response_format="text",
                            )
                        else:
                            respuesta = client.audio.transcriptions.create(
                                model=MODEL,
                                file=f,
                                response_format="text",
                            )
                    texto = respuesta.text if hasattr(respuesta, "text") else str(respuesta)
                except Exception as api_error:
                    print(f"⚠️  Error en API de Whisper: {api_error}. Se activa fallback a Whisper local.")
                    USE_LOCAL_WHISPER = True
                    import whisper  # type: ignore
                    local_whisper_model = whisper.load_model("small")
                    result_local = local_whisper_model.transcribe(wav_filename)
                    texto = result_local.get("text", "")

            # Omitir fragmentos con la palabra "you" (ruido/silencio)
            if texto.strip().lower() == "you":
                # Limpiar WAV y continuar con el siguiente segmento
                try:
                    os.remove(wav_filename)
                except OSError:
                    pass
                idx += 1
                continue

            # Traducir/optimizar con GPT-4o (o Azure GPT-4.1-mini) antes de guardar
            global USE_ARGOS_TRANSLATE_ONLY
            print(f"🔄 Usando Argos Translate: {USE_ARGOS_TRANSLATE_ONLY}")

            if USE_ARGOS_TRANSLATE_ONLY:
                # Se ha decidido usar sólo Argos Translate tras un fallo previo
                texto_final = translate_with_argos(texto)
            else:
                try:
                    if azure_client is not None:
                        # ---- Azure OpenAI ----
                        traduccion_resp = azure_client.chat.completions.create(
                            model=AZURE_TRANSLATE_MODEL,
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "Eres un traductor inglés-español experto en transcripciones. "
                                        "Traduce el siguiente texto al español manteniendo términos técnicos en inglés. "
                                        "Devuelve únicamente la traducción sin comentarios ni explicaciones."
                                    ),
                                },
                                {"role": "user", "content": texto},
                            ],
                            temperature=0.3,
                        )
                    else:
                        # ---- OpenAI estándar ----
                        traduccion_resp = client.chat.completions.create(
                            model=TRANSLATE_MODEL,
                            messages=[
                                {
                                    "role": "system",
                                    "content": (
                                        "Eres un traductor inglés-español experto en transcripciones. "
                                        "Traduce el siguiente texto al español manteniendo términos técnicos en inglés. "
                                        "Devuelve únicamente la traducción sin comentarios ni explicaciones."
                                    ),
                                },
                                {"role": "user", "content": texto},
                            ],
                            temperature=0.3,
                        )

                    texto_final = traduccion_resp.choices[0].message.content.strip()
                except Exception as e:
                    print(f"⚠️  Error al traducir: {e}. Cambiando a Argos-Translate para el resto de la ejecución.")
                    texto_final = translate_with_argos(texto)
                    USE_ARGOS_TRANSLATE_ONLY = True

            texto_a_traducir = suavizar_texto(texto_final)

            marca = datetime.now()
            base_name = f"record_{marca.strftime('%Y%m%d_%H%M%S')}"

            # Ruta para archivo traducido (español)
            archivo_es = os.path.join(args.outdir, f"{base_name}.txt")
            # Ruta para archivo original en inglés con sufijo _EN
            archivo_en = os.path.join(args.outdir, f"{base_name}_EN.txt")

            # Guardar versión en español
            try:
                with open(archivo_es, "w", encoding="utf-8") as f_out:
                    f_out.write(texto_a_traducir)
            except Exception as e:
                print(f"⚠️  Error al guardar transcripción en español: {e}")

            # Guardar versión en inglés
            try:
                with open(archivo_en, "w", encoding="utf-8") as f_out_en:
                    f_out_en.write(texto)
            except Exception as e:
                print(f"⚠️  Error al guardar transcripción en inglés: {e}")
        except Exception as e:
            print(f"⚠️  Error al transcribir: {e}")
        finally:
            # Limpiar archivo temporal
            try:
                os.remove(wav_filename)
            except OSError:
                pass
            idx += 1


def suavizar_texto(texto):
    # Reemplaza 'die' por 'fail' solo si está en contexto técnico
    # Puedes mejorar esta lógica según tus necesidades
    return texto.replace("die", "fail")


def translate_with_argos(text: str, from_code: str = "en", to_code: str = "es") -> str:
    """Traduce *text* usando Argos-Translate si hay paquetes instalados."""
    if argos_translate is None:
        # Biblioteca no disponible
        return text

    try:
        languages = argos_translate.get_installed_languages()
        from_lang = next((l for l in languages if l.code == from_code), None)
        to_lang = next((l for l in languages if l.code == to_code), None)
        if from_lang and to_lang:
            translation = from_lang.get_translation(to_lang)
            print(f"🔄 Traduciendo '{text}' de {from_code} a {to_code}…")
            print(f"🔄 Resultado: {translation.translate(text)}")
            return translation.translate(text)
    except Exception as e:
        print(f"⚠️  Error en Argos Translate: {e}")
    return text


def main():
    print("=== Demo de Transcripción en Tiempo Real con Whisper ===")
    audio_q: "queue.Queue[list[bytes]]" = queue.Queue()
    stop_evt = threading.Event()

    h_grabador = threading.Thread(target=grabador, args=(audio_q, stop_evt), daemon=True)
    h_transcriptor = threading.Thread(target=transcriptor, args=(audio_q, stop_evt), daemon=True)

    h_grabador.start()
    h_transcriptor.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nDeteniendo …")
        stop_evt.set()
        h_grabador.join()
        h_transcriptor.join()

    print("✅ Proceso finalizado")


if __name__ == "__main__":
    main() 