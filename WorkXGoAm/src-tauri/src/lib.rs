// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::fs::{remove_file, File, read_dir};
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;
use tauri::Emitter;
use chrono::Local;
use wasapi::{DeviceCollection, Direction};
use serde::Serialize;
use std::collections::VecDeque;
use std::io::Write;
use std::time::{Duration, Instant};
use wasapi::*;
use log::{info, error, warn, debug};
use std::panic::catch_unwind;

#[derive(Serialize)]
struct AudioDevice {
    name: String,
    id: String,
}

// Structure to store the Python server process
struct PythonProcess {
    child: Mutex<Option<Child>>,
}

// Estructuras para almacenar los procesos de los scripts de Python wav_monitor
struct WavMonitorProcess {
    child: Mutex<Option<Child>>,
}

// Estructuras para almacenar los procesos de los scripts de Python wav_monitor_gui
struct WavMonitorGuiProcess {
    child: Mutex<Option<Child>>,
}

// Returns the path of the temporary file in AppData/Local/WorkXGoAm
fn get_temp_flag_path() -> Result<PathBuf, String> {
    let local_app_data = std::env::var("LOCALAPPDATA").map_err(|e| e.to_string())?;
    let app_data_dir = Path::new(&local_app_data).join("WorkXGoAm");
    println!("AppData directory: {:?}", app_data_dir);
    // Ensure directory exists
    std::fs::create_dir_all(&app_data_dir).map_err(|e| e.to_string())?;
    Ok(app_data_dir.join("running_flag.tmp"))
}
struct TempFlagHandler;

impl TempFlagHandler {
    fn new() -> Result<Self, String> {
        let temp_file_path = get_temp_flag_path()?;
        File::create(&temp_file_path).map_err(|e| e.to_string())?;
        println!("Temporary file created at {:?}", temp_file_path);
        Ok(TempFlagHandler)
    }
}

impl Drop for TempFlagHandler {
    fn drop(&mut self) {
        // Remove temporary running_flag.tmp file
        if let Ok(temp_file_path) = get_temp_flag_path() {
            let _ = remove_file(&temp_file_path);
            println!("Temporary file running_flag.tmp removed");
        }

        // Find and terminate WorkXFlaskServer.exe if it exists
        #[cfg(target_os = "windows")]
        {
            match Command::new("taskkill")
                .args(&["/F", "/IM", "WorkXFlaskServer.exe"])
                .status()
            {
                Ok(status) if status.success() => {
                    println!("WorkXFlaskServer.exe terminated successfully.")
                }
                Ok(status) => println!(
                    "Taskkill returned status {} while trying to terminate WorkXFlaskServer.exe",
                    status
                ),
                Err(e) => println!("Error running taskkill: {}", e),
            }
        }
        #[cfg(any(target_os = "linux", target_os = "macos"))]
        {
            match Command::new("pkill").arg("WorkXFlaskServer.exe").status() {
                Ok(status) if status.success() => {
                    println!("WorkXFlaskServer.exe terminated successfully (using pkill).")
                }
                Ok(status) => println!(
                    "Pkill returned status {} while trying to terminate WorkXFlaskServer.exe",
                    status
                ),
                Err(e) => println!("Error running pkill: {}", e),
            }
        }
    }
}

// Structure to store the WorkXFlaskServer process
struct WorkXFlaskServerProcess {
    child: Mutex<Option<Child>>,
}

// Drop implementation to ensure process termination
impl Drop for WorkXFlaskServerProcess {
    fn drop(&mut self) {
        if let Some(mut child) = self.child.lock().unwrap().take() {
            println!("Terminating WorkXFlaskServer...");
            let _ = child.kill(); // Attempt to kill the process
            let _ = child.wait(); // Wait for process to close
        }
    }
}

// Returns the path to the application data directory
fn get_app_data_dir() -> Result<PathBuf, String> {
    let local_app_data = std::env::var("LOCALAPPDATA").map_err(|e| e.to_string())?;
    let app_data_dir = Path::new(&local_app_data).join("WorkXGoAm");
    println!("AppData directory: {:?}", app_data_dir);
    // Ensure directory exists
    std::fs::create_dir_all(&app_data_dir).map_err(|e| e.to_string())?;
    Ok(app_data_dir)
}

#[tauri::command]
fn read_file(path: &str) -> Result<String, String> {
    std::fs::read_to_string(path).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_env(variable: &str) -> Result<String, String> {
    std::env::var(variable).map_err(|e| e.to_string())
}

/// Starts the WorkXFlaskServer and returns the Child for later management
fn start_workx_flask_server() -> Result<Child, String> {
    // Get Tauri executable path
    let exe_path = std::env::current_exe().map_err(|e| e.to_string())?;
    let exe_dir = exe_path
        .parent()
        .ok_or("Failed to get executable directory")?;

    // Look for Python file in flask_server folder
    let python_script = exe_dir.join("WorkXFlaskServer.exe");

    if !python_script.exists() {
        return Err(format!(
            "Python executable not found at: {:?}",
            python_script
        ));
    }

    let mut cmd = Command::new(python_script);
    
    // In Windows we can add the CREATE_NO_WINDOW flag to hide the terminal.
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    // Launch executable in separate background process
    let child = cmd.spawn().map_err(|e| e.to_string())?;

    Ok(child)
}

// Function that encapsulates all cleanup tasks before closing the application
fn cleanup_before_closing() {
    // 1. Remove temporary running_flag.tmp file
    if let Ok(temp_file_path) = get_temp_flag_path() {
        let _ = remove_file(&temp_file_path);
        println!("Temporary file running_flag.tmp removed");
    }

    // 2. Find and terminate WorkXFlaskServer.exe if it exists
    #[cfg(target_os = "windows")]
    {
        match Command::new("taskkill")
            .args(&["/F", "/IM", "WorkXFlaskServer.exe"])
            .status()
        {
            Ok(status) if status.success() => println!("WorkXFlaskServer.exe terminated successfully."),
            Ok(status) => println!(
                "Taskkill returned status {} while trying to terminate WorkXFlaskServer.exe",
                status
            ),
            Err(e) => println!("Error running taskkill: {}", e),
        }
    }
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    {
        match Command::new("pkill").arg("WorkXFlaskServer.exe").status() {
            Ok(status) if status.success() => {
                println!("WorkXFlaskServer.exe terminated successfully (using pkill).")
            }
            Ok(status) => println!(
                "Pkill returned status {} while trying to terminate WorkXFlaskServer.exe",
                status
            ),
            Err(e) => println!("Error running pkill: {}", e),
        }
    }
}

#[tauri::command]
fn get_audio_devices() -> Result<Vec<AudioDevice>, String> {
    let outputs = DeviceCollection::new(&Direction::Render)
        .map_err(|e| e.to_string())?;
    
    let mut devices = Vec::new();
    let count = outputs.get_nbr_devices().map_err(|e| e.to_string())?;
    
    for i in 0..count {
        let device = outputs.get_device_at_index(i).map_err(|e| e.to_string())?;
        let name = device.get_friendlyname().map_err(|e| e.to_string())?;
        let id = device.get_id().map_err(|e| e.to_string())?;
        
        devices.push(AudioDevice {
            name,
            id,
        });
    }
    
    Ok(devices)
}

/// Escribe un encabezado WAV para audio IEEE float (formato 3) de 32 bits.
fn write_wav_header(
    file: &mut File,
    data_len: u32,
    channels: u16,
    sample_rate: u32,
    bits_per_sample: u16,
) -> std::io::Result<()> {
    let byte_rate = sample_rate * channels as u32 * bits_per_sample as u32 / 8;
    let block_align = channels * bits_per_sample / 8;
    let subchunk2_size = data_len;
    let chunk_size = 36 + subchunk2_size;

    let mut header = Vec::with_capacity(44);
    header.extend_from_slice(b"RIFF");
    header.extend_from_slice(&chunk_size.to_le_bytes());
    header.extend_from_slice(b"WAVE");
    header.extend_from_slice(b"fmt ");
    header.extend_from_slice(&16u32.to_le_bytes()); // Tamaño de subchunk (16 para PCM/float)
    header.extend_from_slice(&3u16.to_le_bytes());   // Formato: 3 = IEEE float
    header.extend_from_slice(&channels.to_le_bytes());
    header.extend_from_slice(&sample_rate.to_le_bytes());
    header.extend_from_slice(&byte_rate.to_le_bytes());
    header.extend_from_slice(&block_align.to_le_bytes());
    header.extend_from_slice(&bits_per_sample.to_le_bytes());
    header.extend_from_slice(b"data");
    header.extend_from_slice(&subchunk2_size.to_le_bytes());
    file.write_all(&header)
}

/// Función simplificada para obtener un dispositivo comparando el id.
fn get_device_by_id(deviceid: &str) -> Result<Device, WasapiError> {
    let collection = DeviceCollection::new(&Direction::Render)?;
    let count = collection.get_nbr_devices()?;
    for i in 0..count {
        let dev = collection.get_device_at_index(i)?;
        let id = dev.get_id()?;
        if id == deviceid {
            return Ok(dev);
        }
    }
    Err(WasapiError::DeviceNotFound(deviceid.to_string()))
}

struct ContinuousRecordingState {
    is_recording: bool,
    stop_signal: Mutex<bool>,
}

#[tauri::command]
fn start_continuous_recording(deviceid: String, app_handle: tauri::AppHandle) -> Result<(), String> {
    info!("Iniciando grabación continua con dispositivo ID: {}", deviceid);
    
    // Creamos el estado de grabación continua
    let recording_state = ContinuousRecordingState {
        is_recording: true,
        stop_signal: Mutex::new(false),
    };
    
    // Lo convertimos en un Arc para compartirlo entre hilos
    let recording_state = std::sync::Arc::new(recording_state);
    let recording_state_clone = recording_state.clone();
    
    // Clonamos el app_handle para usar en el hilo
    let app_handle_clone = app_handle.clone();
    
    // Lanzamos la grabación continua en un hilo separado
    std::thread::spawn(move || {
        info!("Hilo de grabación continua iniciado");
        
        // Notificar que la grabación continua ha comenzado
        app_handle_clone.emit("continuous_recording_started", ()).unwrap_or_default();
        
        let mut count = 0;
        
        // Bucle de grabación continua
        while !*recording_state_clone.stop_signal.lock().unwrap() {
            info!("Iniciando grabación #{} en modo continuo", count + 1);
            
            // Ejecutamos record_10_secs_internal directamente sin catch_unwind
            let result = record_10_secs_internal(deviceid.clone(), app_handle_clone.clone());
            
            if let Err(e) = &result {
                error!("Error en grabación continua: {}", e);
                app_handle_clone.emit("continuous_recording_error", e).unwrap_or_default();
                break;
            }
            
            count += 1;
            
            // Verificamos si debemos detener la grabación
            if *recording_state_clone.stop_signal.lock().unwrap() {
                break;
            }
            
            // Emitimos evento con el número de grabaciones completadas
            app_handle_clone.emit("continuous_recording_progress", count).unwrap_or_default();
        }
        
        info!("Grabación continua detenida después de {} grabaciones", count);
        app_handle_clone.emit("continuous_recording_stopped", count).unwrap_or_default();
    });
    
    // Guardamos el estado en el estado de la aplicación para poder detenerlo después
    app_handle.manage(recording_state);
    
    Ok(())
}

#[tauri::command]
fn stop_continuous_recording(app_handle: tauri::AppHandle) -> Result<(), String> {
    info!("Deteniendo grabación continua");
    
    // Obtenemos el estado de grabación del estado de la aplicación
    if let Some(state) = app_handle.try_state::<std::sync::Arc<ContinuousRecordingState>>() {
        // Establecemos la señal de parada
        *state.stop_signal.lock().unwrap() = true;
        info!("Señal de parada enviada a la grabación continua");
        Ok(())
    } else {
        let err_msg = "No hay grabación continua en curso".to_string();
        error!("{}", err_msg);
        Err(err_msg)
    }
}

// Versión interna de record_10_secs para llamarla desde start_continuous_recording
fn record_10_secs_internal(deviceid: String, app_handle: tauri::AppHandle) -> Result<(), String> {
    info!("Iniciando record_10_secs_internal con dispositivo ID: {}", deviceid);
    
    // En Tauri, asumimos que COM ya está inicializado por el framework
    info!("Asumiendo que COM ya está inicializado por Tauri");
    
    // Obtén el dispositivo elegido por el usuario.
    info!("Buscando dispositivo con ID: {}", deviceid);
    let device = match get_device_by_id(&deviceid) {
        Ok(d) => {
            info!("Dispositivo encontrado correctamente");
            d
        },
        Err(e) => {
            let err_msg = format!("Error al obtener el dispositivo: {:?}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    info!("Obteniendo IAudioClient");
    let mut audio_client = match device.get_iaudioclient() {
        Ok(ac) => {
            info!("IAudioClient obtenido correctamente");
            ac
        },
        Err(e) => {
            let err_msg = format!("Error al obtener IAudioClient: {:?}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    // Define el formato deseado: 32 bits float, 44100 Hz, 2 canales.
    info!("Configurando formato de audio");
    let desired_format = WaveFormat::new(32, 32, &SampleType::Float, 44100, 2, None);
    
    info!("Obteniendo períodos de audio");
    let (def_time, _min_time) = match audio_client.get_periods() {
        Ok(periods) => {
            info!("Períodos obtenidos correctamente");
            periods
        },
        Err(e) => {
            let err_msg = format!("Error al obtener períodos: {:?}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    // Inicializa el cliente en modo compartido para captura (loopback).
    info!("Inicializando cliente de audio para loopback");
    match audio_client.initialize_client(
        &desired_format,
        def_time,
        &Direction::Capture,
        &ShareMode::Shared,
        true,
    ) {
        Ok(_) => info!("Cliente de audio inicializado correctamente"),
        Err(e) => {
            let err_msg = format!("Error al inicializar cliente de audio: {:?}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    // Configura el event handle para buffering basado en eventos.
    info!("Configurando event handle");
    let h_event = match audio_client.set_get_eventhandle() {
        Ok(event) => {
            info!("Event handle configurado correctamente");
            event
        },
        Err(e) => {
            let err_msg = format!("Error al configurar event handle: {:?}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    // Obtén el cliente de captura y comienza la transmisión.
    info!("Obteniendo cliente de captura");
    let capture_client = match audio_client.get_audiocaptureclient() {
        Ok(client) => {
            info!("Cliente de captura obtenido correctamente");
            client
        },
        Err(e) => {
            let err_msg = format!("Error al obtener cliente de captura: {:?}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    info!("Iniciando stream de audio");
    match audio_client.start_stream() {
        Ok(_) => info!("Stream de audio iniciado correctamente"),
        Err(e) => {
            let err_msg = format!("Error al iniciar stream de audio: {:?}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    // Notificar que la grabación ha comenzado
    app_handle.emit("recording_started", ()).unwrap_or_default();
    
    let start = Instant::now();
    let mut captured_data = Vec::new();
    let mut sample_queue: VecDeque<u8> = VecDeque::new();
    
    info!("Iniciando captura de audio por 10 segundos");
    // Graba durante 10 segundos esperando la señal del event handle.
    while start.elapsed() < Duration::from_secs(10) {
        if h_event.wait_for_event(100_000).is_ok() {
            match capture_client.read_from_device_to_deque(&mut sample_queue) {
                Ok(_) => {
                    debug!("Leídos {} bytes de audio", sample_queue.len());
                    while let Some(byte) = sample_queue.pop_front() {
                        captured_data.push(byte);
                    }
                    
                    // Enviar progreso a la interfaz
                    let progress = start.elapsed().as_secs_f32() / 10.0 * 100.0;
                    app_handle.emit("recording_progress", progress).unwrap_or_default();
                },
                Err(e) => {
                    let err_msg = format!("Error al leer datos de audio: {:?}", e);
                    error!("{}", err_msg);
                    // Intentamos detener el stream antes de retornar el error
                    let _ = audio_client.stop_stream();
                    app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
                    return Err(err_msg);
                }
            }
        }
    }
    
    info!("Deteniendo stream de audio");
    match audio_client.stop_stream() {
        Ok(_) => info!("Stream de audio detenido correctamente"),
        Err(e) => {
            let err_msg = format!("Error al detener stream de audio: {:?}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    // Crea un nombre de archivo con timestamp.
    let filename = format!("record_{}.wav", Local::now().format("%Y%m%d_%H%M%S"));
    info!("Guardando archivo de audio: {}", filename);
    
    let mut file = match File::create(&filename) {
        Ok(f) => {
            info!("Archivo creado correctamente");
            f
        },
        Err(e) => {
            let err_msg = format!("Error al crear archivo: {}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    let data_len = captured_data.len() as u32;
    info!("Grabados {} bytes de audio", data_len);
    
    match write_wav_header(&mut file, data_len, 2, 44100, 32) {
        Ok(_) => info!("Encabezado WAV escrito correctamente"),
        Err(e) => {
            let err_msg = format!("Error al escribir encabezado WAV: {}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    match file.write_all(&captured_data) {
        Ok(_) => info!("Datos de audio escritos correctamente"),
        Err(e) => {
            let err_msg = format!("Error al escribir datos de audio: {}", e);
            error!("{}", err_msg);
            app_handle.emit("recording_error", err_msg.clone()).unwrap_or_default();
            return Err(err_msg);
        }
    };
    
    info!("Grabación completada exitosamente: {}", filename);
    // Notificar que la grabación ha terminado con éxito
    app_handle.emit("recording_finished", filename).unwrap_or_default();
    
    Ok(())
}

#[tauri::command]
fn record_10_secs(deviceid: String, app_handle: tauri::AppHandle) -> Result<(), String> {
    info!("Iniciando record_10_secs con dispositivo ID: {}", deviceid);
    
    // Clonamos el app_handle para poder usarlo en el hilo
    let app_handle_clone = app_handle.clone();
    
    // Lanzamos la grabación en un hilo separado
    std::thread::spawn(move || {
        info!("Hilo de grabación iniciado");
        
        let result = record_10_secs_internal(deviceid, app_handle_clone);
        if let Err(e) = result {
            error!("Error en record_10_secs: {}", e);
        }
    });
    
    // Retornamos inmediatamente para no bloquear la interfaz
    Ok(())
}

#[tauri::command]
fn read_transcription_file(path: &str) -> Result<String, String> {
    std::fs::read_to_string(path).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_transcription_files() -> Result<Vec<String>, String> {
    // Obtiene el directorio actual donde se ejecuta la aplicación
    let current_dir = std::env::current_dir().map_err(|e| e.to_string())?;
    
    // Lee todos los archivos en el directorio actual
    let entries = read_dir(current_dir).map_err(|e| e.to_string())?;
    
    // Filtra solo los archivos .txt y ordénalos por fecha de modificación (más reciente primero)
    let mut txt_files: Vec<(PathBuf, std::time::SystemTime)> = Vec::new();
    
    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        
        // Verifica si es un archivo .txt
        if path.is_file() && path.extension().map_or(false, |ext| ext == "txt") {
            // Obtiene la fecha de modificación
            if let Ok(metadata) = entry.metadata() {
                if let Ok(modified) = metadata.modified() {
                    txt_files.push((path, modified));
                }
            }
        }
    }
    
    // Ordena por fecha de modificación (más reciente primero)
    txt_files.sort_by(|a, b| b.1.cmp(&a.1));
    
    // Convierte las rutas a cadenas
    let paths: Vec<String> = txt_files
        .into_iter()
        .map(|(path, _)| path.to_string_lossy().to_string())
        .collect();
    
    Ok(paths)
}

// Función para iniciar el script wav_monitor.py en una terminal visible
fn start_wav_monitor() -> Result<Child, String> {
    // Usar la ruta absoluta donde se encuentran los scripts
    let script_path = Path::new("D:\\git-edalx\\WorkXGoAm\\WorkXGoAm\\src-tauri\\wav_monitor.py");
    
    info!("Intentando ejecutar el script de Python: {:?}", script_path);
    
    #[cfg(target_os = "windows")]
    {
        // En Windows, usamos cmd para abrir una nueva terminal con el script
        let mut cmd = Command::new("cmd");
        cmd.args(&["/c", "start", "cmd", "/k", "python"]);
        cmd.arg(script_path);
        
        // Ejecutar el comando
        let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor.py: {}", e))?;
        info!("Script wav_monitor.py iniciado correctamente");
        Ok(child)
    }
    
    #[cfg(target_os = "linux")]
    {
        // En Linux, podemos usar xterm o gnome-terminal
        let mut cmd = Command::new("gnome-terminal");
        cmd.args(&["--", "python"]);
        cmd.arg(script_path);
        
        // Ejecutar el comando
        let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor.py: {}", e))?;
        info!("Script wav_monitor.py iniciado correctamente");
        Ok(child)
    }
    
    #[cfg(target_os = "macos")]
    {
        // En macOS, podemos usar Terminal.app
        let mut cmd = Command::new("open");
        cmd.args(&["-a", "Terminal"]);
        cmd.arg(script_path);
        
        // Ejecutar el comando
        let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor.py: {}", e))?;
        info!("Script wav_monitor.py iniciado correctamente");
        Ok(child)
    }
    
    #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
    {
        Err("Sistema operativo no soportado para iniciar el script wav_monitor.py".to_string())
    }
}

// Función para iniciar el script wav_monitor_gui.py en una terminal visible
fn start_wav_monitor_gui() -> Result<Child, String> {
    // Usar la ruta absoluta donde se encuentran los scripts
    let script_path = Path::new("D:\\git-edalx\\WorkXGoAm\\WorkXGoAm\\src-tauri\\wav_monitor_gui.py");
    
    info!("Intentando ejecutar el script de Python: {:?}", script_path);
    
    #[cfg(target_os = "windows")]
    {
        // En Windows, usamos cmd para abrir una nueva terminal con el script
        let mut cmd = Command::new("cmd");
        cmd.args(&["/c", "start", "cmd", "/k", "python"]);
        cmd.arg(script_path);
        
        // Ejecutar el comando
        let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor_gui.py: {}", e))?;
        info!("Script wav_monitor_gui.py iniciado correctamente");
        Ok(child)
    }
    
    #[cfg(target_os = "linux")]
    {
        // En Linux, podemos usar xterm o gnome-terminal
        let mut cmd = Command::new("gnome-terminal");
        cmd.args(&["--", "python"]);
        cmd.arg(script_path);
        
        // Ejecutar el comando
        let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor_gui.py: {}", e))?;
        info!("Script wav_monitor_gui.py iniciado correctamente");
        Ok(child)
    }
    
    #[cfg(target_os = "macos")]
    {
        // En macOS, podemos usar Terminal.app
        let mut cmd = Command::new("open");
        cmd.args(&["-a", "Terminal"]);
        cmd.arg(script_path);
        
        // Ejecutar el comando
        let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor_gui.py: {}", e))?;
        info!("Script wav_monitor_gui.py iniciado correctamente");
        Ok(child)
    }
    
    #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
    {
        Err("Sistema operativo no soportado para iniciar el script wav_monitor_gui.py".to_string())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Inicializar el sistema de logging
    env_logger::init();
    
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            // Get main window
            let main_window = app
                .get_webview_window("main")
                .expect("Main window not found");

            main_window.on_window_event(|event| {
                // Detect window close button
                if let tauri::WindowEvent::CloseRequested { .. } = event {
                    // Execute cleanup tasks before closing
                    cleanup_before_closing();
                }
            });

            // Start WorkXFlaskServer
            #[cfg(not(debug_assertions))]
            {
                match start_workx_flask_server() {
                    Ok(child) => {
                        println!("WorkXFlaskServer started successfully.");
                        app.manage(WorkXFlaskServerProcess {
                            child: Mutex::new(Some(child)),
                        });
                    }
                    Err(e) => eprintln!("Error starting WorkXFlaskServer: {:?}", e),
                }
            }
            
            // Iniciar wav_monitor.py en una terminal visible
            match start_wav_monitor() {
                Ok(child) => {
                    println!("wav_monitor.py started successfully.");
                    app.manage(WavMonitorProcess {
                        child: Mutex::new(Some(child)),
                    });
                }
                Err(e) => eprintln!("Error starting wav_monitor.py: {:?}", e),
            }
            
            // Iniciar wav_monitor_gui.py en una terminal visible
            match start_wav_monitor_gui() {
                Ok(child) => {
                    println!("wav_monitor_gui.py started successfully.");
                    app.manage(WavMonitorGuiProcess {
                        child: Mutex::new(Some(child)),
                    });
                }
                Err(e) => eprintln!("Error starting wav_monitor_gui.py: {:?}", e),
            }
            
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![read_file, get_env, get_audio_devices, record_10_secs, start_continuous_recording, stop_continuous_recording, read_transcription_file, get_transcription_files])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
