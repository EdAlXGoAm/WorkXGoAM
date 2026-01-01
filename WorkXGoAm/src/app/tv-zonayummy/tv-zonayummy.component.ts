import { Component, OnInit, OnDestroy, ElementRef, ViewChild, AfterViewInit, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { invoke } from '@tauri-apps/api/core';

// Declarar Hls como tipo global (cargado desde CDN)
declare var Hls: any;

@Component({
  selector: 'app-tv-zonayummy',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './tv-zonayummy.component.html',
  styleUrls: ['./tv-zonayummy.component.css']
})
export class TvZonayummyComponent implements OnInit, OnDestroy, AfterViewInit {
  @ViewChild('youtubeContainer') youtubeContainer!: ElementRef<HTMLDivElement>;
  @ViewChild('cameraVideo') cameraVideo!: ElementRef<HTMLVideoElement>;

  currentTime = '';
  currentDate = '';
  temperature = '--';
  weatherDescription = '';
  weatherIcon = '🌡️';

  // Stream de cámara
  cameraStreamUrl = '';
  cameraStreamActive = false;
  cameraStreamError = '';
  cameraStreamMode = 'hls'; // 'hls' o 'mjpeg'
  isRefreshing = false;
  private readonly CAMERA_STREAM_ID = 'security_cam';
  private readonly CAMERA_RTSP_URL = 'rtsp://edalxgoam:FeDiPeExNaPo@192.168.100.14:554/stream1';
  private readonly FLASK_BASE_URL = 'http://127.0.0.1:8080';

  private timeInterval: any = null;
  private weatherInterval: any = null;
  private cameraRefreshInterval: any = null;
  private resizeTimeout: any = null;
  private hlsInstance: any = null;

  ngOnInit(): void {
    this.updateTime();
    this.timeInterval = setInterval(() => this.updateTime(), 1000);
    
    this.fetchWeather();
    this.weatherInterval = setInterval(() => this.fetchWeather(), 600000); // cada 10 min

    // Cargar hls.js desde CDN
    this.loadHlsScript().then(() => {
      // Iniciar stream de cámara después de cargar hls.js
      this.startCameraStream();
    });
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
    if (this.cameraRefreshInterval) {
      clearInterval(this.cameraRefreshInterval);
    }
    if (this.resizeTimeout) {
      clearTimeout(this.resizeTimeout);
    }
    if (this.hlsInstance) {
      this.hlsInstance.destroy();
      this.hlsInstance = null;
    }
    this.closeYouTubeWebview();
    this.stopCameraStream();
  }

  private loadHlsScript(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (typeof Hls !== 'undefined') {
        resolve();
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/hls.js@latest';
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Error cargando hls.js'));
      document.head.appendChild(script);
    });
  }

  // ========================
  // Camera Stream Methods
  // ========================
  private async startCameraStream(): Promise<void> {
    try {
      this.cameraStreamError = '';
      const response = await fetch(`${this.FLASK_BASE_URL}/stream/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stream_id: this.CAMERA_STREAM_ID,
          rtsp_url: this.CAMERA_RTSP_URL,
          with_audio: true  // HLS con audio
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.status === 'ok') {
          this.cameraStreamMode = data.mode || 'hls';
          
          // Pausa para que FFmpeg genere los primeros segmentos HLS
          const waitTime = this.cameraStreamMode === 'hls' ? 4000 : 1000;
          await new Promise(resolve => setTimeout(resolve, waitTime));
          
          this.cameraStreamUrl = `${this.FLASK_BASE_URL}${data.stream_url}`;
          this.cameraStreamActive = true;
          console.log(`Camera stream started (${this.cameraStreamMode}):`, this.cameraStreamUrl);
          
          // Si es HLS, inicializar el reproductor
          if (this.cameraStreamMode === 'hls') {
            setTimeout(() => this.initHlsPlayer(), 100);
          }
          
          // Iniciar el intervalo de refresco automático cada 5 minutos para HLS
          this.startAutoRefresh();
        } else {
          this.cameraStreamError = data.message || 'Error iniciando stream';
        }
      } else {
        this.cameraStreamError = 'Error de conexión con el servidor';
      }
    } catch (error) {
      console.error('Error starting camera stream:', error);
      this.cameraStreamError = 'No se pudo conectar al servidor';
    }
  }

  private initHlsPlayer(): void {
    const video = this.cameraVideo?.nativeElement;
    if (!video) {
      console.error('Video element not found');
      return;
    }

    // Destruir instancia anterior si existe
    if (this.hlsInstance) {
      this.hlsInstance.destroy();
      this.hlsInstance = null;
    }

    if (typeof Hls !== 'undefined' && Hls.isSupported()) {
      this.hlsInstance = new Hls({
        debug: false,
        enableWorker: true,
        lowLatencyMode: true,
        backBufferLength: 90
      });
      
      this.hlsInstance.loadSource(this.cameraStreamUrl);
      this.hlsInstance.attachMedia(video);
      
      this.hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch((e: any) => console.log('Autoplay prevented:', e));
      });
      
      this.hlsInstance.on(Hls.Events.ERROR, (event: any, data: any) => {
        if (data.fatal) {
          console.error('HLS fatal error:', data);
          this.cameraStreamError = 'Error en el stream de video';
        }
      });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari nativo
      video.src = this.cameraStreamUrl;
      video.addEventListener('loadedmetadata', () => {
        video.play().catch((e: any) => console.log('Autoplay prevented:', e));
      });
    } else {
      this.cameraStreamError = 'Tu navegador no soporta HLS';
    }
  }

  private async stopCameraStream(): Promise<void> {
    try {
      // Destruir reproductor HLS
      if (this.hlsInstance) {
        this.hlsInstance.destroy();
        this.hlsInstance = null;
      }
      
      await fetch(`${this.FLASK_BASE_URL}/stream/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stream_id: this.CAMERA_STREAM_ID })
      });
      this.cameraStreamActive = false;
      this.cameraStreamUrl = '';
    } catch (error) {
      console.error('Error stopping camera stream:', error);
    }
  }

  onCameraError(): void {
    this.cameraStreamError = 'Error cargando el stream de la cámara';
    this.cameraStreamActive = false;
  }

  private startAutoRefresh(): void {
    if (this.cameraRefreshInterval) {
      clearInterval(this.cameraRefreshInterval);
    }
    
    // Refrescar cada 5 minutos para HLS (menos frecuente que MJPEG)
    const refreshInterval = this.cameraStreamMode === 'hls' ? 300000 : 60000;
    this.cameraRefreshInterval = setInterval(() => {
      this.refreshCameraStream();
    }, refreshInterval);
  }

  async refreshCameraStream(): Promise<void> {
    if (this.isRefreshing) return;
    
    this.isRefreshing = true;
    this.cameraStreamActive = false;
    
    try {
      await this.stopCameraStream();
      await new Promise(resolve => setTimeout(resolve, 500));
      await this.startCameraStream();
    } catch (error) {
      console.error('Error refreshing camera stream:', error);
      this.cameraStreamError = 'Error al refrescar el stream';
    } finally {
      this.isRefreshing = false;
    }
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

