import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, from, throwError } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';
import { invoke } from '@tauri-apps/api/core';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private apiBaseUrl = 'http://127.0.0.1:8080'; // Puerto por defecto
  private apiReadyPromise: Promise<string>;

  constructor(private http: HttpClient) {
    this.apiReadyPromise = this.loadServerPort();
  }

  /**
   * Carga la información del puerto del servidor desde el archivo server-port.json
   */
  private async loadServerPort(): Promise<string> {
    try {
      // Obtenemos la ruta de %LOCALAPPDATA%
      const localAppData = await invoke<string>('get_env', { variable: 'LOCALAPPDATA' });
      const configPath = `${localAppData}\\WorkXGoAm\\server-port.json`;
      
      // Leemos el archivo
      const portConfig = await invoke<string>('read_file', { path: configPath });
      const { port } = JSON.parse(portConfig);
      
      this.apiBaseUrl = `http://127.0.0.1:${port}`;
      console.log(`API configurada en: ${this.apiBaseUrl}`);
      
      // Mostrar alerta con la dirección del servidor
      // alert(`Servidor WorkXGoAm configurado en: ${this.apiBaseUrl}`);
      return this.apiBaseUrl;
    } catch (error) {
      console.error('Error al leer el puerto del servidor:', error);
      // En caso de error usamos el puerto por defecto
      alert(`Servidor WorkXGoAm configurado en el puerto por defecto: ${this.apiBaseUrl}`);
      return this.apiBaseUrl;
    }
  }

  /**
   * Obtiene la URL base del API asegurando que está inicializada
   */
  private getApiUrl(): Observable<string> {
    return from(this.apiReadyPromise);
  }

  /**
   * Verifica la salud del servidor
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
   * Ejemplo de método para llamar al endpoint hello
   */
  getHello(): Observable<{message: string}> {
    return this.getApiUrl().pipe(
      switchMap(baseUrl => 
        this.http.get<{message: string}>(`${baseUrl}/api/hello`).pipe(
          catchError(error => {
            console.error('Error al obtener mensaje de saludo:', error);
            return of({ message: 'Error al conectar con el servidor' });
          })
        )
      )
    );
  }
} 