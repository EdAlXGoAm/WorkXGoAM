import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { TestWindowService } from '../services/test-window.service';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { FormsModule } from '@angular/forms';
import { invoke } from '@tauri-apps/api/core';
import { appLocalDataDir } from '@tauri-apps/api/path';

interface AudioDevice {
  name: string;
  id: string;
}

@Component({
  selector: 'app-test-window',
  standalone: true,
  imports: [
    CommonModule, 
    MatCardModule, 
    MatButtonModule, 
    MatSelectModule,
    MatFormFieldModule,
    FormsModule
  ],
  templateUrl: './test-window.component.html',
  styleUrls: ['./test-window.component.css']
})
export class TestWindowComponent implements OnInit {
  dataFromService: string = '';
  audioDevices: AudioDevice[] = [];
  selectedDevice: string = '';
  isRecording: boolean = false;
  isRecording10Secs: boolean = false;
  lastCapturedFile: string = '';
  statusMessage: string = '';

  constructor(private router: Router, private testWindowService: TestWindowService) {}

  ngOnInit(): void {
    this.dataFromService = this.testWindowService.getTestData();
    // Cargar dispositivos de audio al iniciar
    this.getAudioDevices();
  }

  async getAudioDevices(): Promise<void> {
    try {
      this.audioDevices = await invoke<AudioDevice[]>('get_audio_devices');
      console.log('Dispositivos de audio:', this.audioDevices);
      
      // Seleccionar el primer dispositivo por defecto si hay dispositivos y no hay uno seleccionado
      if (this.audioDevices.length > 0 && !this.selectedDevice) {
        this.selectedDevice = this.audioDevices[0].id;
      }
    } catch (error) {
      console.error('Error al obtener dispositivos de audio:', error);
      this.statusMessage = `Error: ${error}`;
    }
  }

  async record10Seconds(): Promise<void> {
    if (this.isRecording || this.isRecording10Secs) {
      this.statusMessage = 'Ya hay una grabación en curso';
      return;
    }

    if (!this.selectedDevice) {
      this.statusMessage = 'Por favor selecciona un dispositivo de audio';
      return;
    }

    try {
      this.statusMessage = 'Iniciando grabación de 10 segundos...';
      this.isRecording10Secs = true;
      
      // Llamar a la función Rust para grabar 10 segundos
      const filename = await invoke<string>('record_10_secs', {
        deviceid: this.selectedDevice
      });
      
      this.lastCapturedFile = filename;
      this.statusMessage = `Grabación de 10 segundos completada: ${filename}`;
    } catch (error) {
      console.error('Error en grabación de 10 segundos:', error);
      this.statusMessage = `Error: ${error}`;
    } finally {
      this.isRecording10Secs = false;
    }
  }

  goBack(): void {
    this.router.navigate(['/']);
  }
} 