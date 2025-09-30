import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../services/api.service';
import { Router } from '@angular/router';
import { open, save } from '@tauri-apps/plugin-dialog';
import { downloadDir, basename, extname, join } from '@tauri-apps/api/path';
import { convertFileSrc } from '@tauri-apps/api/core';

@Component({
  selector: 'app-video-cutter',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './video-cutter.component.html',
  styleUrls: ['./video-cutter.component.css']
})
export class VideoCutterComponent implements OnInit {
  inputPath: string = '';
  outputPath: string = '';
  startTime: string = '00:00:00';
  endTime: string = '00:00:10';
  isProcessing: boolean = false;
  resultMessage: string = '';

  @ViewChild('videoPlayer', { static: true }) videoPlayer!: ElementRef<HTMLVideoElement>;

  videoPreviewShow: boolean = false;
  videoInfo: string = '';
  progress: number = 0;
  statusColor: string = 'text-gray-600';

  constructor(private apiService: ApiService, private router: Router) {}

  ngOnInit(): void {}

  async selectInputVideo(): Promise<void> {
    try {
      const defaultDir = await downloadDir();
      const selected = await open({
        multiple: false,
        directory: false,
        filters: [{ name: 'Videos', extensions: ['mp4'] }],
        defaultPath: defaultDir
      });
      if (selected == null) {
        return;
      }
      const filePath = Array.isArray(selected) ? selected[0] : selected;
      this.handleVideoPathChange(filePath);
      const name = await basename(filePath);
      const dotIndex = name.lastIndexOf('.');
      const nameWithoutExt = dotIndex !== -1 ? name.slice(0, dotIndex) : name;
      const ext = dotIndex !== -1 ? name.slice(dotIndex + 1) : '';
      const timeSuffix = this.generateTimeSuffix();
      const suggested = ext ? `${nameWithoutExt}_clip_${timeSuffix}.${ext}` : `${nameWithoutExt}_clip_${timeSuffix}`;
      this.outputPath = await join(defaultDir, suggested);
    } catch (e) {
      console.error('Error seleccionando vídeo de entrada:', e);
    }
  }

  async selectOutputLocation(): Promise<void> {
    try {
      const defaultDir = await downloadDir();
      const defaultSavePath = this.outputPath || defaultDir;
      const selected = await save({
        defaultPath: defaultSavePath,
        filters: [{ name: 'Videos', extensions: ['mp4'] }]
      });
      if (selected == null) {
        return;
      }
        this.outputPath = selected;
    } catch (e) {
      console.error('Error seleccionando ubicación de salida:', e);
    }
  }

  cutVideo(): void {
    if (!this.inputPath || !this.outputPath) {
      this.resultMessage = 'Por favor selecciona ruta de entrada y salida';
      console.log(this.inputPath, this.outputPath);
      return;
    }
    this.isProcessing = true;
    this.resultMessage = '';
    this.apiService.cutVideo(this.inputPath, this.startTime, this.endTime, this.outputPath)
      .subscribe(response => {
        this.isProcessing = false;
        if (response.status === 'success') {
          this.resultMessage = 'Vídeo recortado exitosamente: ' + response.output;
        } else {
          this.resultMessage = 'Error: ' + response.message;
        }
      }, error => {
        this.isProcessing = false;
        this.resultMessage = 'Error en el servidor';
      });
  }

  clearVideo(): void {
    this.inputPath = '';
    this.videoPreviewShow = false;
    this.videoPlayer.nativeElement.src = '';
    this.videoInfo = '';
    this.showStatus('Video eliminado', 'text-gray-600');
  }

  validateTime(inputEl: HTMLInputElement): void {
    if (!inputEl.checkValidity()) {
      inputEl.classList.add('border-red-500');
    } else {
      inputEl.classList.remove('border-red-500');
      // Actualizar el nombre del archivo de salida con los nuevos tiempos
      this.updateOutputPathWithTimes();
    }
  }

  setTimeToCurrent(inputEl: HTMLInputElement): void {
    const player = this.videoPlayer.nativeElement;
    if (!player.src || player.paused) {
      this.showStatus('Reproduce el video para establecer el tiempo actual', 'text-yellow-600');
      return;
    }
    const currentTime = player.currentTime;
    const hours = Math.floor(currentTime / 3600).toString().padStart(2, '0');
    const minutes = Math.floor((currentTime % 3600) / 60).toString().padStart(2, '0');
    const seconds = Math.floor(currentTime % 60).toString().padStart(2, '0');
    inputEl.value = `${hours}:${minutes}:${seconds}`;
    inputEl.classList.remove('border-red-500');
    inputEl.classList.add('border-green-500');
    setTimeout(() => inputEl.classList.remove('border-green-500'), 1000);
    // Actualizar el nombre del archivo de salida con los nuevos tiempos
    this.updateOutputPathWithTimes();
  }

  private showStatus(message: string, colorClass: string): void {
    this.resultMessage = message;
    this.statusColor = colorClass;
    setTimeout(() => this.resultMessage = '', 5000);
  }

  /**
   * Genera un sufijo con los tiempos de inicio y fin para el nombre del archivo.
   * Convierte formato HH:MM:SS a H-MM-SS para usar en nombres de archivo.
   */
  private generateTimeSuffix(): string {
    const formatTime = (time: string): string => {
      // Reemplaza los dos puntos por guiones y elimina ceros iniciales innecesarios
      const parts = time.split(':');
      if (parts.length === 3) {
        const hours = parseInt(parts[0], 10);
        const minutes = parts[1];
        const seconds = parts[2];
        return `${hours}-${minutes}-${seconds}`;
      }
      return time.replace(/:/g, '-');
    };

    const startFormatted = formatTime(this.startTime);
    const endFormatted = formatTime(this.endTime);
    return `${startFormatted}_${endFormatted}`;
  }

  /**
   * Actualiza el nombre del archivo de salida basándose en los tiempos actuales.
   * Se llama cuando el usuario cambia los tiempos de inicio o fin.
   */
  async updateOutputPathWithTimes(): Promise<void> {
    if (!this.inputPath || !this.outputPath) {
      return;
    }

    try {
      // Extraer el directorio, nombre base y extensión del outputPath actual
      const segments = this.outputPath.split(/[\\\/]/);
      const filename = segments.pop() || '';
      const directory = segments.join('\\');

      // Obtener el nombre base del archivo de entrada
      const inputName = await basename(this.inputPath);
      const dotIndex = inputName.lastIndexOf('.');
      const inputNameWithoutExt = dotIndex !== -1 ? inputName.slice(0, dotIndex) : inputName;
      const ext = dotIndex !== -1 ? inputName.slice(dotIndex + 1) : '';

      // Generar nuevo nombre con los tiempos actualizados
      const timeSuffix = this.generateTimeSuffix();
      const newFilename = ext ? `${inputNameWithoutExt}_${timeSuffix}.${ext}` : `${inputNameWithoutExt}_${timeSuffix}`;

      // Actualizar el outputPath
      this.outputPath = directory ? `${directory}\\${newFilename}` : newFilename;
    } catch (e) {
      console.error('Error actualizando nombre de salida:', e);
    }
  }

  /**
   * Maneja cambios manuales en la ruta de entrada y genera la previsualización leyendo el archivo.
   */
  public handleVideoPathChange(path: string): void {
    this.inputPath = path;
    this.videoPreviewShow = true;
    // Convierte la ruta del archivo a una URL segura para Tauri
    const url = convertFileSrc(path);
    this.videoPlayer.nativeElement.src = url;
    // Muestra sólo el nombre del archivo
    const segments = path.split(/[\\\/]/);
    this.videoInfo = segments.pop() || path;
    this.showStatus('Ruta de video de entrada actualizada', 'text-green-600');
  }

  public goHome(): void {
    this.router.navigate(['/']);
  }
} 