import { Component, OnInit, OnDestroy, ViewChild, ElementRef, ChangeDetectorRef } from '@angular/core';
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
import { listen } from '@tauri-apps/api/event';
import { Subscription } from 'rxjs';

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
export class TestWindowComponent implements OnInit, OnDestroy {
  dataFromService: string = '';
  audioDevices: AudioDevice[] = [];
  selectedDevice: string = '';
  isRecording: boolean = false;
  isRecording10Secs: boolean = false;
  isContinuousRecording: boolean = false;
  lastCapturedFile: string = '';
  statusMessage: string = '';
  recordingProgress: number = 0;
  continuousRecordingCount: number = 0;
  
  // Propiedad para almacenar las transcripciones
  transcriptions: string = '';
  transcriptionInterval: any = null;
  
  // Propiedad para almacenar las transcripciones en inglés
  transcriptionsEn: string = '';
  
  // Referencia al contenedor de transcripciones para auto-scroll
  @ViewChild('transcriptionContainer') transcriptionContainer!: ElementRef;
  
  // Subscripciones a eventos de Tauri
  private eventUnlisteners: (() => void)[] = [];

  constructor(
    private router: Router, 
    private testWindowService: TestWindowService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.dataFromService = this.testWindowService.getTestData();
    // Cargar dispositivos de audio al iniciar
    this.getAudioDevices();
    
    // Suscribirse a eventos de Tauri
    this.setupEventListeners();
    
    // Iniciar actualización de transcripciones
    this.startTranscriptionUpdates();
  }
  
  ngOnDestroy(): void {
    // Cancelar todas las suscripciones a eventos
    this.eventUnlisteners.forEach(unlisten => unlisten());
    
    // Detener la actualización de transcripciones
    this.stopTranscriptionUpdates();
  }
  
  // Método para iniciar la actualización periódica de transcripciones
  startTranscriptionUpdates(): void {
    // Actualizar inmediatamente la primera vez
    this.updateTranscriptions();
    
    // Configurar actualización periódica cada 2 segundos
    this.transcriptionInterval = setInterval(() => {
      this.updateTranscriptions();
    }, 2000);
  }
  
  // Método para detener la actualización periódica
  stopTranscriptionUpdates(): void {
    if (this.transcriptionInterval) {
      clearInterval(this.transcriptionInterval);
      this.transcriptionInterval = null;
    }
  }
  
  // Método para actualizar las transcripciones
  async updateTranscriptions(): Promise<void> {
    try {
      // Obtener listas de archivos de transcripción separadas
      interface TranscriptionFiles { original: string[]; english: string[]; }
      const filesRes = await invoke<TranscriptionFiles>('get_transcription_files');
      const spanishFiles = filesRes.original || [];
      const englishFiles = filesRes.english || [];

      // Función para construir el contenido a partir de los archivos
      const buildContent = async (files: string[]): Promise<string> => {
        let content = '';
        for (const file of files) {
          // Excluir contexto.txt
          const filenameOnly = file.split(/[\\/]/).pop() || '';
          if (filenameOnly === 'contexto.txt') continue;
          try {
            const fileContent = await invoke<string>('read_transcription_file', { path: file });
            content += `[${this.extractTimestamp(file)}] ${fileContent}\n\n`;
          } catch (error) {
            console.error(`Error al leer el archivo ${file}:`, error);
          }
        }
        return content;
      };

      // Construir ambos contenidos
      const [newSpanishContent, newEnglishContent] = await Promise.all([
        buildContent(spanishFiles),
        buildContent(englishFiles)
      ]);

      // Actualizar propiedades solo si hay cambios
      if (this.transcriptions !== newSpanishContent) {
        this.transcriptions = newSpanishContent;
      }
      if (this.transcriptionsEn !== newEnglishContent) {
        this.transcriptionsEn = newEnglishContent;
      }

      // Forzar la detección de cambios
      this.cdr.detectChanges();

    } catch (error) {
      console.error('Error al actualizar transcripciones:', error);
    }
  }
  
  // Método auxiliar para extraer solo la hora del timestamp del nombre del archivo
  private extractTimestamp(filepath: string): string {
    const filename = filepath.split(/[\\/]/).pop() || '';
    const match = filename.match(/\d{8}_(\d{6})/);
    if (match) {
      const hora = match[1];
      // Formatear HHMMSS a HH:MM:SS
      return `${hora.substring(0, 2)}:${hora.substring(2, 4)}:${hora.substring(4, 6)}`;
    }
    return filename;
  }
  
  // Método para hacer scroll al final del contenedor
  private scrollToBottom(): void {
    setTimeout(() => {
      if (this.transcriptionContainer) {
        const element = this.transcriptionContainer.nativeElement;
        element.scrollTop = element.scrollHeight;
      }
    }, 100);
  }
  
  private async setupEventListeners(): Promise<void> {
    // Eventos para la grabación normal de 10s
    this.eventUnlisteners.push(await listen('recording_started', () => {
      this.isRecording10Secs = true;
      this.statusMessage = 'Grabación iniciada...';
    }));
    
    this.eventUnlisteners.push(await listen('recording_progress', (event) => {
      this.recordingProgress = event.payload as number;
    }));
    
    this.eventUnlisteners.push(await listen('recording_finished', (event) => {
      this.isRecording10Secs = false;
      this.lastCapturedFile = event.payload as string;
      this.statusMessage = `Grabación completada: ${this.lastCapturedFile}`;
      
      // Actualizar transcripciones inmediatamente después de terminar una grabación
      this.updateTranscriptions();
    }));
    
    this.eventUnlisteners.push(await listen('recording_error', (event) => {
      this.isRecording10Secs = false;
      this.statusMessage = `Error: ${event.payload}`;
    }));
    
    // Eventos para la grabación continua
    this.eventUnlisteners.push(await listen('continuous_recording_started', () => {
      this.isContinuousRecording = true;
      this.continuousRecordingCount = 0;
      this.statusMessage = 'Grabación continua iniciada...';
    }));
    
    this.eventUnlisteners.push(await listen('continuous_recording_progress', (event) => {
      this.continuousRecordingCount = event.payload as number;
      this.statusMessage = `Grabación continua en curso: ${this.continuousRecordingCount} archivos generados`;
      
      // Actualizar transcripciones cada vez que se completa una grabación en modo continuo
      this.updateTranscriptions();
    }));
    
    this.eventUnlisteners.push(await listen('continuous_recording_stopped', (event) => {
      this.isContinuousRecording = false;
      const count = event.payload as number;
      this.statusMessage = `Grabación continua detenida: ${count} archivos generados`;
      
      // Actualizar transcripciones una vez más después de detener la grabación continua
      this.updateTranscriptions();
    }));
    
    this.eventUnlisteners.push(await listen('continuous_recording_error', (event) => {
      this.isContinuousRecording = false;
      this.statusMessage = `Error en grabación continua: ${event.payload}`;
    }));
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
    if (this.isRecording || this.isRecording10Secs || this.isContinuousRecording) {
      this.statusMessage = 'Ya hay una grabación en curso';
      return;
    }

    if (!this.selectedDevice) {
      this.statusMessage = 'Por favor selecciona un dispositivo de audio';
      return;
    }

    try {
      this.statusMessage = 'Iniciando grabación de 10 segundos...';
      
      // Llamar a la función Rust para grabar 10 segundos
      await invoke('record_10_secs', {
        deviceid: this.selectedDevice
      });
      
    } catch (error) {
      console.error('Error en grabación de 10 segundos:', error);
      this.statusMessage = `Error: ${error}`;
      this.isRecording10Secs = false;
    }
  }
  
  async startContinuousRecording(): Promise<void> {
    if (this.isRecording || this.isRecording10Secs || this.isContinuousRecording) {
      this.statusMessage = 'Ya hay una grabación en curso';
      return;
    }

    if (!this.selectedDevice) {
      this.statusMessage = 'Por favor selecciona un dispositivo de audio';
      return;
    }

    try {
      this.statusMessage = 'Iniciando grabación continua...';
      
      // Llamar a la función Rust para iniciar grabación continua
      await invoke('start_continuous_recording', {
        deviceid: this.selectedDevice
      });
      
    } catch (error) {
      console.error('Error al iniciar grabación continua:', error);
      this.statusMessage = `Error: ${error}`;
      this.isContinuousRecording = false;
    }
  }
  
  async stopContinuousRecording(): Promise<void> {
    if (!this.isContinuousRecording) {
      this.statusMessage = 'No hay grabación continua en curso';
      return;
    }

    try {
      this.statusMessage = 'Deteniendo grabación continua...';
      
      // Llamar a la función Rust para detener grabación continua
      await invoke('stop_continuous_recording');
      
    } catch (error) {
      console.error('Error al detener grabación continua:', error);
      this.statusMessage = `Error: ${error}`;
    }
  }

  // Métodos para iniciar los wav monitors bajo demanda
  async startWavMonitor(): Promise<void> {
    try {
      this.statusMessage = 'Iniciando Wav Monitor...';
      const response = await invoke<string>('start_wav_monitor_cmd');
      this.statusMessage = response;
    } catch (error) {
      console.error('Error iniciando wav monitor:', error);
      this.statusMessage = `Error iniciando wav monitor: ${error}`;
    }
  }

  async startWavMonitorGui(): Promise<void> {
    try {
      this.statusMessage = 'Iniciando Wav Monitor GUI...';
      const response = await invoke<string>('start_wav_monitor_gui_cmd');
      this.statusMessage = response;
    } catch (error) {
      console.error('Error iniciando wav monitor GUI:', error);
      this.statusMessage = `Error iniciando wav monitor GUI: ${error}`;
    }
  }

  goBack(): void {
    this.router.navigate(['/']);
  }
} 