import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ApiService } from '../services/api.service';
import { invoke } from '@tauri-apps/api/core';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit {
  serverStatus = false;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.checkServerStatus();
  }

  checkServerStatus(): void {
    this.apiService.checkHealth().subscribe(status => {
      this.serverStatus = status;
      console.log('HomeComponent - Server status:', status ? 'Online' : 'Disconnected');
    });
  }

  async openTestWindow(): Promise<void> {
    try {
      await invoke('open_test_window');
    } catch (error) {
      console.error('Error opening Test Window:', error);
    }
  }

  async openVideoCutter(): Promise<void> {
    try {
      await invoke('open_video_cutter');
    } catch (error) {
      console.error('Error opening Video Cutter:', error);
    }
  }
} 