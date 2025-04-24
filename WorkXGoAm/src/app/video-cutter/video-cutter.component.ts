import { Component, OnInit } from '@angular/core';
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
  startTime: number = 0;
  endTime: number = 10;
  isProcessing: boolean = false;
  resultMessage: string = '';

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {}

  async selectInputVideo(): Promise<void> {
    try {
      const defaultDir = await downloadDir();
      const selected = await open({
        defaultPath: defaultDir,
        filters: [{ name: 'Videos', extensions: ['mp4'] }],
        multiple: false,
        directory: false
      });
      if (typeof selected === 'string') {
        this.inputPath = selected;
        const name = await basename(this.inputPath);
        const ext = await extname(this.inputPath);
        const nameWithoutExt = name.replace(new RegExp(ext + '$'), '');
        const suggested = nameWithoutExt + '_clip1' + ext;
        this.outputPath = await join(defaultDir, suggested);
      }
    } catch (e) {
      console.error('Error seleccionando vídeo de entrada:', e);
    }
  }

  async selectOutputLocation(): Promise<void> {
    try {
      const defaultDir = await downloadDir();
      const defaultSavePath = this.outputPath || defaultDir;
      const selected = await save({ defaultPath: defaultSavePath });
      if (typeof selected === 'string') {
        this.outputPath = selected;
      }
    } catch (e) {
      console.error('Error seleccionando ubicación de salida:', e);
    }
  }

  cutVideo(): void {
    if (!this.inputPath || !this.outputPath) {
      this.resultMessage = 'Por favor selecciona ruta de entrada y salida';
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
} 