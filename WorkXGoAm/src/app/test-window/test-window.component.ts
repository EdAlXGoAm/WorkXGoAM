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

  constructor(private router: Router, private testWindowService: TestWindowService) {}

  ngOnInit(): void {
    this.dataFromService = this.testWindowService.getTestData();
  }

  async getAudioDevices(): Promise<void> {
    try {
      this.audioDevices = await invoke<AudioDevice[]>('get_audio_devices');
      console.log('Dispositivos de audio:', this.audioDevices);
    } catch (error) {
      console.error('Error al obtener dispositivos de audio:', error);
    }
  }

  goBack(): void {
    this.router.navigate(['/']);
  }
} 