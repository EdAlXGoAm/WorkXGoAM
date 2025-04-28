# -*- coding: utf-8 -*-
import os
import sys
import subprocess

def generar_nombre_salida(input_path, start, end):
    """
    Genera un nombre de archivo de salida basado en el nombre original y rangos de tiempo.
    """
    name, ext = os.path.splitext(os.path.basename(input_path))
    start_fmt = start.replace(':', '')
    end_fmt = end.replace(':', '')
    return f"{name}_from{start_fmt}_to{end_fmt}{ext}"

def recortar_video(input_path, start, end, output_path=None):
    """
    Recorta el video entre start y end sin recodificar (mantiene calidad y fps).
    Devuelve la ruta del archivo de salida.
    """
    print(f"Recortando video desde {start} hasta {end}")
    print(f"Input path: {input_path}")
    if output_path is None:
        output_path = generar_nombre_salida(input_path, start, end)
    print(f"Output path: {output_path}")
    cmd = [
        'ffmpeg',
        '-y',              # sobrescribe si existe
        '-i', input_path,  # archivo de entrada
        '-ss', start,      # tiempo de inicio
        '-to', end,        # tiempo de fin
        '-c', 'copy',      # copia streams sin recodificar
        output_path        # archivo de salida
    ]
    print(f"Command: {' '.join(cmd)}") # Mejor visualización del comando
    try:
        # Usar capture_output=True para obtener stdout y stderr
        proceso = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("FFmpeg stdout:", proceso.stdout)
        print("FFmpeg stderr:", proceso.stderr) # FFmpeg a menudo usa stderr para información
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando FFmpeg. Código de retorno: {e.returncode}", file=sys.stderr)
        print("FFmpeg stdout:", e.stdout, file=sys.stderr)
        print("FFmpeg stderr:", e.stderr, file=sys.stderr) # Aquí estará el error detallado
        # Puedes decidir si relanzar la excepción o devolver None/un error
        raise e # O manejar el error de otra forma
    except FileNotFoundError:
        print("Error: Comando 'ffmpeg' no encontrado. Asegúrate de que esté instalado y en el PATH.", file=sys.stderr)
        raise # O manejar el error
    return output_path 