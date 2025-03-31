// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::fs::{remove_file, File};
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;
use chrono::Local;

// Structure to store the Python server process
struct PythonProcess {
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
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
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![read_file, get_env])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
