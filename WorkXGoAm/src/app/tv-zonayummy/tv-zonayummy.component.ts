import { Component, OnInit, OnDestroy, ElementRef, ViewChild, AfterViewInit, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { invoke } from '@tauri-apps/api/core';

@Component({
  selector: 'app-tv-zonayummy',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './tv-zonayummy.component.html',
  styleUrls: ['./tv-zonayummy.component.css']
})
export class TvZonayummyComponent implements OnInit, OnDestroy, AfterViewInit {
  @ViewChild('youtubeContainer') youtubeContainer!: ElementRef<HTMLDivElement>;

  currentTime = '';
  currentDate = '';
  temperature = '--';
  weatherDescription = '';
  weatherIcon = '🌡️';

  private timeInterval: any = null;
  private weatherInterval: any = null;
  private resizeTimeout: any = null;

  ngOnInit(): void {
    this.updateTime();
    this.timeInterval = setInterval(() => this.updateTime(), 1000);
    
    this.fetchWeather();
    this.weatherInterval = setInterval(() => this.fetchWeather(), 600000); // cada 10 min
  }

  ngAfterViewInit(): void {
    // Esperar un poco para que el layout se estabilice
    setTimeout(() => this.openYouTubeWebview(), 300);
  }

  ngOnDestroy(): void {
    if (this.timeInterval) {
      clearInterval(this.timeInterval);
    }
    if (this.weatherInterval) {
      clearInterval(this.weatherInterval);
    }
    if (this.resizeTimeout) {
      clearTimeout(this.resizeTimeout);
    }
    this.closeYouTubeWebview();
  }

  @HostListener('window:resize')
  onResize(): void {
    // Debounce para evitar llamadas excesivas durante el resize
    if (this.resizeTimeout) {
      clearTimeout(this.resizeTimeout);
    }
    this.resizeTimeout = setTimeout(() => this.updateYouTubePosition(), 100);
  }

  private async updateYouTubePosition(): Promise<void> {
    try {
      const container = this.youtubeContainer?.nativeElement;
      if (container) {
        const rect = container.getBoundingClientRect();
        await invoke('open_youtube_webview', {
          x: Math.floor(rect.left),
          y: Math.floor(rect.top),
          width: Math.floor(rect.width),
          height: Math.floor(rect.height)
        });
      }
    } catch (error) {
      console.error('Error updating YouTube webview position:', error);
    }
  }

  private updateTime(): void {
    const now = new Date();
    this.currentTime = now.toLocaleTimeString('es-MX', { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit',
      hour12: true 
    });
    this.currentDate = now.toLocaleDateString('es-MX', { 
      weekday: 'long', 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    });
  }

  private async fetchWeather(): Promise<void> {
    try {
      const response = await fetch('https://wttr.in/Ecatepec+de+Morelos?format=j1');
      if (response.ok) {
        const data = await response.json();
        const current = data.current_condition?.[0];
        if (current) {
          this.temperature = current.temp_C || '--';
          this.weatherDescription = current.lang_es?.[0]?.value || current.weatherDesc?.[0]?.value || '';
          this.weatherIcon = this.getWeatherIcon(current.weatherCode);
        }
      }
    } catch (error) {
      console.error('Error fetching weather:', error);
    }
  }

  private getWeatherIcon(code: string): string {
    const codeNum = parseInt(code, 10);
    if (codeNum === 113) return '☀️';
    if (codeNum === 116) return '⛅';
    if (codeNum === 119 || codeNum === 122) return '☁️';
    if ([176, 263, 266, 293, 296, 299, 302, 305, 308, 311, 314, 353, 356, 359].includes(codeNum)) return '🌧️';
    if ([179, 182, 185, 281, 284, 317, 320, 323, 326, 329, 332, 335, 338, 350, 362, 365, 368, 371, 374, 377].includes(codeNum)) return '🌨️';
    if ([200, 386, 389, 392, 395].includes(codeNum)) return '⛈️';
    if ([227, 230].includes(codeNum)) return '❄️';
    if ([143, 248, 260].includes(codeNum)) return '🌫️';
    return '🌡️';
  }

  private async openYouTubeWebview(): Promise<void> {
    try {
      const container = this.youtubeContainer?.nativeElement;
      if (container) {
        const rect = container.getBoundingClientRect();
        await invoke('open_youtube_webview', {
          x: Math.floor(rect.left),
          y: Math.floor(rect.top),
          width: Math.floor(rect.width),
          height: Math.floor(rect.height)
        });
      }
    } catch (error) {
      console.error('Error opening YouTube webview:', error);
    }
  }

  private async closeYouTubeWebview(): Promise<void> {
    try {
      await invoke('close_youtube_webview');
    } catch (error) {
      console.error('Error closing YouTube webview:', error);
    }
  }
}

