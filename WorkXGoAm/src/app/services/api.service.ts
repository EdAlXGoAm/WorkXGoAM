import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, from, throwError } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';
import { invoke } from '@tauri-apps/api/core';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private apiBaseUrl = 'http://127.0.0.1:8080'; // Default port
  private apiReadyPromise: Promise<string>;

  constructor(private http: HttpClient) {
    this.apiReadyPromise = this.loadServerPort();
  }

  /**
   * Loads the server port information from the server-port.json file
   */
  private async loadServerPort(): Promise<string> {
    try {
      // Get %LOCALAPPDATA% path
      const localAppData = await invoke<string>('get_env', { variable: 'LOCALAPPDATA' });
      const configPath = `${localAppData}\\WorkXGoAm\\server-port.json`;
      
      // Read the file
      const portConfig = await invoke<string>('read_file', { path: configPath });
      const { port } = JSON.parse(portConfig);
      
      this.apiBaseUrl = `http://127.0.0.1:${port}`;
      console.log(`API configured at: ${this.apiBaseUrl}`);
      
      // Show alert with the server address
      // alert(`Servidor WorkXGoAm configurado en: ${this.apiBaseUrl}`);
      return this.apiBaseUrl;
    } catch (error) {
      console.error('Error reading server port:', error);
      // In case of error, use the default port
      // alert(`Servidor WorkXGoAm configured at the default port: ${this.apiBaseUrl}`);
      return this.apiBaseUrl;
    }
  }

  /**
   * Gets the base API URL ensuring it is initialized
   */
  private getApiUrl(): Observable<string> {
    return from(this.apiReadyPromise);
  }

  /**
   * Checks the server health
   */
  checkHealth(): Observable<boolean> {
    return this.getApiUrl().pipe(
      switchMap(baseUrl => 
        this.http.get<{status: string}>(`${baseUrl}/api/health`).pipe(
          map(response => response.status === 'healthy'),
          catchError(() => of(false))
        )
      )
    );
  }

  /**
   * Corte de video
   */
  cutVideo(input: string, start: string, end: string, output: string): Observable<any> {
    return this.getApiUrl().pipe(
      switchMap(baseUrl =>
        this.http.post<{ status: string; output?: string; message?: string }>(
          `${baseUrl}/video/cut`,
          { input, start, end, output }
        )
      )
    );
  }

  /**
   * Obtiene el estado UI compartido (hover cara, hover popup, rect cara)
   */
  getUiState(): Observable<{ face_hover: boolean; popup_hover: boolean; face_rect: any }>{
    return this.getApiUrl().pipe(
      switchMap(baseUrl =>
        this.http.get<{ status: string; data: { face_hover: boolean; popup_hover: boolean; face_rect: any } }>(`${baseUrl}/ui/state`)
      ),
      map(r => r.data),
      catchError(() => of({ face_hover: false, popup_hover: false, face_rect: null }))
    )
  }
} 