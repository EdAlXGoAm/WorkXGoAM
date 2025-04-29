use std::fs::File;
use std::io::Write;
use std::sync::{Arc, Mutex};
use std::collections::VecDeque;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager, Emitter};
use log::{info, error};
use chrono::Local;
use wasapi::{DeviceCollection, Direction, Device, WasapiError, WaveFormat, SampleType, ShareMode};

/// Estado para grabación continua
struct ContinuousRecordingState {
    stop_signal: Mutex<bool>,
}

/// Inicia grabación continua de fragmentos de 10 segundos
#[tauri::command]
pub fn start_continuous_recording(deviceid: String, app_handle: AppHandle) -> Result<(), String> {
    info!("Iniciando grabación continua con dispositivo ID: {}", deviceid);
    let state = Arc::new(ContinuousRecordingState { stop_signal: Mutex::new(false) });
    let state_clone = state.clone();
    let app_clone = app_handle.clone();
    std::thread::spawn(move || {
        info!("Hilo de grabación continua iniciado");
        app_clone.emit("continuous_recording_started", ()).unwrap_or_default();
        let mut count = 0;
        while !*state_clone.stop_signal.lock().unwrap() {
            info!("Grabación continua: iteración {}", count + 1);
            if let Err(e) = record_10_secs_internal(deviceid.clone(), app_clone.clone()) {
                error!("Error en grabación continua: {}", e);
                app_clone.emit("continuous_recording_error", e).unwrap_or_default();
                break;
            }
            count += 1;
            app_clone.emit("continuous_recording_progress", count).unwrap_or_default();
        }
        info!("Grabación continua detenida después de {} iteraciones", count);
        app_clone.emit("continuous_recording_stopped", count).unwrap_or_default();
    });
    app_handle.manage(state);
    Ok(())
}

/// Detiene la grabación continua
#[tauri::command]
pub fn stop_continuous_recording(app_handle: AppHandle) -> Result<(), String> {
    info!("Deteniendo grabación continua");
    if let Some(state) = app_handle.try_state::<Arc<ContinuousRecordingState>>() {
        *state.stop_signal.lock().unwrap() = true;
        info!("Señal de parada enviada");
        Ok(())
    } else {
        let err = "No hay grabación continua en curso".to_string();
        error!("{}", err);
        Err(err)
    }
}

/// Graba 10 segundos de audio en segundo plano y escribe un archivo WAV
#[tauri::command]
pub fn record_10_secs(deviceid: String, app_handle: AppHandle) -> Result<(), String> {
    info!("Iniciando record_10_secs con dispositivo ID: {}", deviceid);
    let app_clone = app_handle.clone();
    std::thread::spawn(move || {
        if let Err(e) = record_10_secs_internal(deviceid, app_clone.clone()) {
            error!("Error en record_10_secs: {}", e);
        }
    });
    Ok(())
}

/// Lógica interna para grabar 10 segundos y guardar WAV
fn record_10_secs_internal(deviceid: String, app_handle: AppHandle) -> Result<(), String> {
    info!("Iniciando record_10_secs_internal con dispositivo ID: {}", deviceid);
    info!("Asumiendo que COM está inicializado por Tauri");
    let device = get_device_by_id(&deviceid).map_err(|e| {
        let msg = format!("Error al obtener el dispositivo: {:?}", e);
        app_handle.emit("recording_error", msg.clone()).unwrap_or_default();
        msg
    })?;
    let mut audio_client = device.get_iaudioclient().map_err(|e| {
        let msg = format!("Error al obtener IAudioClient: {:?}", e);
        app_handle.emit("recording_error", msg.clone()).unwrap_or_default();
        msg
    })?;
    let desired_format = WaveFormat::new(32, 32, &SampleType::Float, 44100, 2, None);
    let (def_time, _min_time) = audio_client.get_periods().map_err(|e| {
        let msg = format!("Error al obtener períodos: {:?}", e);
        app_handle.emit("recording_error", msg.clone()).unwrap_or_default();
        msg
    })?;
    audio_client.initialize_client(&desired_format, def_time, &Direction::Capture, &ShareMode::Shared, true)
        .map_err(|e| {
            let msg = format!("Error al inicializar cliente: {:?}", e);
            app_handle.emit("recording_error", msg.clone()).unwrap_or_default();
            msg
        })?;
    let h_event = audio_client.set_get_eventhandle().map_err(|e| {
        let msg = format!("Error al configurar event handle: {:?}", e);
        app_handle.emit("recording_error", msg.clone()).unwrap_or_default();
        msg
    })?;
    let capture_client = audio_client.get_audiocaptureclient().map_err(|e| {
        let msg = format!("Error al obtener cliente de captura: {:?}", e);
        app_handle.emit("recording_error", msg.clone()).unwrap_or_default();
        msg
    })?;
    audio_client.start_stream().map_err(|e| {
        let msg = format!("Error al iniciar stream de audio: {:?}", e);
        app_handle.emit("recording_error", msg.clone()).unwrap_or_default();
        msg
    })?;
    app_handle.emit("recording_started", ()).unwrap_or_default();
    let start = Instant::now();
    let mut captured_data = Vec::new();
    let mut sample_queue: VecDeque<u8> = VecDeque::new();
    while start.elapsed() < Duration::from_secs(10) {
        if h_event.wait_for_event(100_000).is_ok() {
            capture_client.read_from_device_to_deque(&mut sample_queue).map_err(|e| {
                let msg = format!("Error al leer datos: {:?}", e);
                app_handle.emit("recording_error", msg.clone()).unwrap_or_default();
                let _ = audio_client.stop_stream();
                msg
            })?;
            while let Some(byte) = sample_queue.pop_front() {
                captured_data.push(byte);
            }
            let progress = start.elapsed().as_secs_f32() / 10.0 * 100.0;
            app_handle.emit("recording_progress", progress).unwrap_or_default();
        }
    }
    audio_client.stop_stream().unwrap_or_default();
    let filename = format!("record_{}.wav", Local::now().format("%Y%m%d_%H%M%S"));
    let mut file = File::create(&filename).map_err(|e| e.to_string())?;
    let data_len = captured_data.len() as u32;
    write_wav_header(&mut file, data_len, 2, 44100, 32).map_err(|e| e.to_string())?;
    file.write_all(&captured_data).map_err(|e| e.to_string())?;
    app_handle.emit("recording_finished", filename.clone()).unwrap_or_default();
    Ok(())
}

/// Escribe un encabezado WAV para audio IEEE float de 32 bits
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
    header.extend_from_slice(&16u32.to_le_bytes());
    header.extend_from_slice(&3u16.to_le_bytes());
    header.extend_from_slice(&channels.to_le_bytes());
    header.extend_from_slice(&sample_rate.to_le_bytes());
    header.extend_from_slice(&byte_rate.to_le_bytes());
    header.extend_from_slice(&block_align.to_le_bytes());
    header.extend_from_slice(&bits_per_sample.to_le_bytes());
    header.extend_from_slice(b"data");
    header.extend_from_slice(&subchunk2_size.to_le_bytes());
    file.write_all(&header)
}

/// Obtiene un dispositivo por ID
fn get_device_by_id(deviceid: &str) -> Result<Device, WasapiError> {
    let collection = DeviceCollection::new(&Direction::Render)?;
    let count = collection.get_nbr_devices()?;
    for i in 0..count {
        let dev = collection.get_device_at_index(i)?;
        if dev.get_id()? == deviceid {
            return Ok(dev);
        }
    }
    Err(WasapiError::DeviceNotFound(deviceid.to_string()))
} 