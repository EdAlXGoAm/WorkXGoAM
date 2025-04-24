#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import subprocess
import os

def parse_args():
    parser = argparse.ArgumentParser(
        description='Recortar un video mp4 manteniendo calidad, fps y demás ajustes.'
    )
    parser.add_argument(
        'input', help='Ruta al archivo de video mp4'
    )
    parser.add_argument(
        'start', help='Tiempo de inicio en formato HH:MM:SS'
    )
    parser.add_argument(
        'end', help='Tiempo de fin en formato HH:MM:SS'
    )
    parser.add_argument(
        '-o', '--output', help='Ruta de salida del video recortado', default=None
    )
    return parser.parse_args()

def generar_nombre_salida(input_path, start, end):
    name, ext = os.path.splitext(os.path.basename(input_path))
    start_fmt = start.replace(':', '')
    end_fmt = end.replace(':', '')
    return f"{name}_from{start_fmt}_to{end_fmt}{ext}"

def recortar_video(input_path, start, end, output_path):
    cmd = [
        'ffmpeg',
        '-y',             # sobrescribe salida si existe
        '-i', input_path,
        '-ss', start,     # tiempo de inicio
        '-to', end,       # tiempo de fin
        '-c', 'copy',     # copia streams sin re-encode para mantener calidad y fps
        output_path
    ]
    subprocess.run(cmd, check=True)

def main():
    args = parse_args()
    salida = args.output or generar_nombre_salida(args.input, args.start, args.end)
    recortar_video(args.input, args.start, args.end, salida)
    print(f'Video recortado guardado en: {salida}')

if __name__ == '__main__':
    main()
