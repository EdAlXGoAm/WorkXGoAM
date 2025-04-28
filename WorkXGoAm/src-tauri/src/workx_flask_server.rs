use std::process::{Child, Command};
use std::path::PathBuf;
use std::sync::Mutex;
use log::info;

/// Estructura para almacenar el proceso de WorkXFlaskServer
pub struct WorkXFlaskServerProcess {
    pub child: Mutex<Option<Child>>,
}

impl Drop for WorkXFlaskServerProcess {
    fn drop(&mut self) {
        if let Some(mut child) = self.child.lock().unwrap().take() {
            println!("Terminating WorkXFlaskServer...");
            let _ = child.kill(); // Intentar matar el proceso
            let _ = child.wait(); // Esperar a que cierre
        }
    }
}

/// Starts the WorkXFlaskServer and returns the Child for later management
pub fn start_workx_flask_server() -> Result<Child, String> {
    // Get Tauri executable path
    let exe_path = std::env::current_exe().map_err(|e| e.to_string())?;
    let exe_dir = exe_path.parent().ok_or("Failed to get executable directory")?;

    // Look for Python file in flask_server folder
    let python_script = exe_dir.join("WorkXFlaskServer.exe");

    if !python_script.exists() {
        return Err(format!("Python executable not found at: {:?}", python_script));
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