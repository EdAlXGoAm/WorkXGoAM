import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { getCurrentWindow } from '@tauri-apps/api/window';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent {
  isFullscreen = false;

  constructor() {}

  async toggleFullscreen(): Promise<void> {
    try {
      const window = getCurrentWindow();
      this.isFullscreen = await window.isFullscreen();
      await window.setFullscreen(!this.isFullscreen);
      this.isFullscreen = !this.isFullscreen;
    } catch (error) {
      console.error('Error toggling fullscreen:', error);
    }
  }
}
