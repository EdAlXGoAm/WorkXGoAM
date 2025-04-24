# -*- coding: utf-8 -*-
import os
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
    if output_path is None:
        output_path = generar_nombre_salida(input_path, start, end)

    cmd = [
        'ffmpeg',
        '-y',              # sobrescribe si existe
        '-i', input_path,  # archivo de entrada
        '-ss', start,      # tiempo de inicio
        '-to', end,        # tiempo de fin
        '-c', 'copy',      # copia streams sin recodificar
        output_path        # archivo de salida
    ]
    subprocess.run(cmd, check=True)
    return output_path 