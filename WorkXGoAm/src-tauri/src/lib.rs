// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::sync::Mutex;
use tauri::Manager;

mod wav_monitors;
use wav_monitors::{WavMonitorProcess, WavMonitorGuiProcess, start_wav_monitor_cmd, start_wav_monitor_gui_cmd};
mod workx_flask_server;
use workx_flask_server::{start_workx_flask_server, WorkXFlaskServerProcess};
mod wav_recording;
use wav_recording::{record_10_secs, start_continuous_recording, stop_continuous_recording};
mod files_lib;
use files_lib::{read_file, get_env};
mod audio_lib;
mod transcription_files_lib;
mod running_flags;
use running_flags::{get_temp_flag_path, TempFlagHandler};

// Function that encapsulates all cleanup tasks before closing the application
fn cleanup_before_closing() {
    // 1. Eliminar archivo temporal running_flag.tmp
    if let Ok(temp_file_path) = get_temp_flag_path() {
        match std::fs::remove_file(&temp_file_path) {
            Ok(_) => println!("Archivo temporal running_flag.tmp eliminado correctamente"),
            Err(e) => println!("No se pudo eliminar running_flag.tmp: {}", e),
        }
    } else {
        println!("No se pudo obtener la ruta del archivo temporal");
    }
    // 2. Terminar WorkXFlaskServer.exe, wav_monitor.py y wav_monitor_gui.py si existen
    #[cfg(target_os = "windows")]
    {
        for proc_name in ["WorkXFlaskServer.exe", "wav_monitor.exe", "wav_monitor_gui.exe"] {
            let args = if proc_name == "python.exe" {
                vec!["/F", "/IM", proc_name]
            } else {
                vec!["/F", "/IM", proc_name]
            };
            match std::process::Command::new("taskkill")
                .args(&args)
                .status()
            {
                Ok(status) if status.success() => println!("{} terminated successfully.", proc_name),
                Ok(status) => println!(
                    "Taskkill returned status {} while trying to terminate {}",
                    status, proc_name
                ),
                Err(e) => println!("Error running taskkill for {}: {}", proc_name, e),
            }
        }
    }
    #[cfg(any(target_os = "linux", target_os = "macos"))]
    {
        for proc_name in ["WorkXFlaskServer.exe", "wav_monitor.py", "wav_monitor_gui.py"] {
            match std::process::Command::new("pkill").arg(proc_name).status() {
                Ok(status) if status.success() => {
                    println!("{} terminated successfully (using pkill).", proc_name)
                }
                Ok(status) => println!(
                    "Pkill returned status {} while trying to terminate {}",
                    status, proc_name
                ),
                Err(e) => println!("Error running pkill for {}: {}", proc_name, e),
            }
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Inicializar el sistema de logging
    env_logger::init();
    
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {            // Crear y almacenar TempFlagHandler para gestionar el archivo temporal
            match TempFlagHandler::new() {
                Ok(handler) => {
                    app.manage(handler);
                },
                Err(e) => {
                    eprintln!("Error creando TempFlagHandler: {}", e);
                }
            }

            // Registrar estado para los monitores pero sin iniciarlos
            app.manage(WavMonitorProcess { child: Mutex::new(None) });
            app.manage(WavMonitorGuiProcess { child: Mutex::new(None) });

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
            
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            read_file, get_env, audio_lib::get_audio_devices, record_10_secs, start_continuous_recording, stop_continuous_recording, transcription_files_lib::read_transcription_file, transcription_files_lib::get_transcription_files,
            start_wav_monitor_cmd, start_wav_monitor_gui_cmd
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
