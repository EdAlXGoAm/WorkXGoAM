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

mod wav_monitors;
use wav_monitors::{start_wav_monitor, start_wav_monitor_gui, WavMonitorProcess, WavMonitorGuiProcess};
mod workx_flask_server;
use workx_flask_server::{start_workx_flask_server, WorkXFlaskServerProcess};
mod wav_recording;
use wav_recording::{record_10_secs, start_continuous_recording, stop_continuous_recording};
mod files_lib;
use files_lib::{read_file, get_env, get_app_data_dir};
mod audio_lib;
mod transcription_files_lib;
mod Running_flags;

// Structure to store the Python server process
struct PythonProcess {
    child: Mutex<Option<Child>>,
}

// Function that encapsulates all cleanup tasks before closing the application
fn cleanup_before_closing() {
    // 1. Eliminar archivo temporal running_flag.tmp
    if let Ok(temp_file_path) = Running_flags::get_temp_flag_path() {
        let _ = std::fs::remove_file(&temp_file_path);
        println!("Temporary file running_flag.tmp removed");
    }

    // 2. Terminar WorkXFlaskServer.exe, wav_monitor.py y wav_monitor_gui.py si existen
    #[cfg(target_os = "windows")]
    {
        for proc_name in ["WorkXFlaskServer.exe", "wav_monitor.exe", "wav_monitor_gui.exe"] {
            let args = if proc_name == "python.exe" {
                // Cierra todos los procesos python.exe que estén ejecutando wav_monitor.py o wav_monitor_gui.py
                // Esto es una solución general, pero si quieres más precisión, puedes usar herramientas como tasklist + findstr
                // o usar un script externo para filtrar por línea de comando.
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
        for proc_name in ["WorkXFlaskServer.exe", "wav_monitor.exe", "wav_monitor_gui.exe"] {
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
        .invoke_handler(tauri::generate_handler![read_file, get_env, audio_lib::get_audio_devices, record_10_secs, start_continuous_recording, stop_continuous_recording, transcription_files_lib::read_transcription_file, transcription_files_lib::get_transcription_files])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
