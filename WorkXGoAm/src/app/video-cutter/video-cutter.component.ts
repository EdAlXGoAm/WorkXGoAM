import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../services/api.service';
import { open, save } from '@tauri-apps/plugin-dialog';
import { downloadDir, basename, extname, join } from '@tauri-apps/api/path';

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

  constructor(private apiService: ApiService) {}

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
      const ext = await extname(filePath);
      const nameWithoutExt = name.replace(new RegExp(ext + '$'), '');
      const suggested = nameWithoutExt + '_clip1' + ext;
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

  handleVideoSelect(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.inputPath = file.name;
    this.videoPreviewShow = true;
    const url = URL.createObjectURL(file);
    this.videoPlayer.nativeElement.src = url;
    this.videoInfo = `${file.name} • ${(file.size / (1024 * 1024)).toFixed(2)} MB`;
    this.startTime = '00:00:00';
    this.endTime = '00:00:00';
    this.showStatus('Video cargado correctamente', 'text-green-600');
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
  }

  private showStatus(message: string, colorClass: string): void {
    this.resultMessage = message;
    this.statusColor = colorClass;
    setTimeout(() => this.resultMessage = '', 5000);
  }

  /**
   * Maneja cambios manuales en la ruta de entrada y genera la previsualización leyendo el archivo.
   */
  public handleVideoPathChange(path: string): void {
    this.inputPath = path;
    this.videoPreviewShow = true;
    // Previsualiza con file://
    const url = path.startsWith('file://') ? path : `file://${path}`;
    this.videoPlayer.nativeElement.src = url;
    // Muestra sólo el nombre del archivo
    const segments = path.split(/[\\\/]/);
    this.videoInfo = segments.pop() || path;
    this.showStatus('Ruta de video de entrada actualizada', 'text-green-600');
  }
} 