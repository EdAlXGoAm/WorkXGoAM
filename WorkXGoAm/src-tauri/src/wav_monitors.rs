use std::process::{Child};
use std::sync::Mutex;

/// Estructuras para almacenar los procesos de los scripts de Python wav_monitor
#[allow(dead_code)]
pub struct WavMonitorProcess {
    pub child: Mutex<Option<Child>>,
}

/// Estructuras para almacenar los procesos de los scripts de Python wav_monitor_gui
#[allow(dead_code)]
pub struct WavMonitorGuiProcess {
    pub child: Mutex<Option<Child>>,
}

/// Función para iniciar el script wav_monitor.py o wav_monitor.exe según el modo
pub fn start_wav_monitor() -> Result<Child, String> {
    #[cfg(debug_assertions)]
    {
        // En modo debug, ejecuta el .py desde la ruta fuente
        let script_path = std::path::Path::new("D:/git-edalx/WorkXGoAm/WorkXGoAm/src-python/wav_monitor.py");
        log::info!("Intentando ejecutar el script de Python: {:?}", script_path);
        #[cfg(target_os = "windows")]
        {
            let mut cmd = std::process::Command::new("cmd");
            cmd.args(&["/c", "start", "cmd", "/k", "python"]);
            cmd.arg(script_path);
            let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor.py: {}", e))?;
            log::info!("Script wav_monitor.py iniciado correctamente");
            return Ok(child);
        }
        #[cfg(target_os = "linux")]
        {
            let mut cmd = std::process::Command::new("gnome-terminal");
            cmd.args(&["--", "python"]);
            cmd.arg(script_path);
            let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor.py: {}", e))?;
            log::info!("Script wav_monitor.py iniciado correctamente");
            return Ok(child);
        }
        #[cfg(target_os = "macos")]
        {
            let mut cmd = std::process::Command::new("open");
            cmd.args(&["-a", "Terminal"]);
            cmd.arg(script_path);
            let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor.py: {}", e))?;
            log::info!("Script wav_monitor.py iniciado correctamente");
            return Ok(child);
        }
        #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
        {
            return Err("Sistema operativo no soportado para iniciar el script wav_monitor.py".to_string());
        }
    }
    #[cfg(not(debug_assertions))]
    {
        // En release, ejecuta el .exe desde la ruta del ejecutable
        let exe_path = std::env::current_exe().map_err(|e| e.to_string())?;
        let exe_dir = exe_path.parent().ok_or("Failed to get executable directory")?;
        let exe_file = exe_dir.join("wav_monitor.exe");
        if !exe_file.exists() {
            return Err(format!("wav_monitor.exe no encontrado en: {:?}", exe_file));
        }
        let mut cmd = std::process::Command::new(exe_file);
        let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor.exe: {}", e))?;
        log::info!("wav_monitor.exe iniciado correctamente");
        Ok(child)
    }
}

/// Función para iniciar el script wav_monitor_gui.py o wav_monitor_gui.exe según el modo
pub fn start_wav_monitor_gui() -> Result<Child, String> {
    #[cfg(debug_assertions)]
    {
        // En modo debug, ejecuta el .py desde la ruta fuente
        let script_path = std::path::Path::new("D:/git-edalx/WorkXGoAm/WorkXGoAm/src-python/wav_monitor_gui.py");
        log::info!("Intentando ejecutar el script de Python: {:?}", script_path);
        #[cfg(target_os = "windows")]
        {
            let mut cmd = std::process::Command::new("cmd");
            cmd.args(&["/c", "start", "cmd", "/k", "python"]);
            cmd.arg(script_path);
            let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor_gui.py: {}", e))?;
            log::info!("Script wav_monitor_gui.py iniciado correctamente");
            return Ok(child);
        }
        #[cfg(target_os = "linux")]
        {
            let mut cmd = std::process::Command::new("gnome-terminal");
            cmd.args(&["--", "python"]);
            cmd.arg(script_path);
            let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor_gui.py: {}", e))?;
            log::info!("Script wav_monitor_gui.py iniciado correctamente");
            return Ok(child);
        }
        #[cfg(target_os = "macos")]
        {
            let mut cmd = std::process::Command::new("open");
            cmd.args(&["-a", "Terminal"]);
            cmd.arg(script_path);
            let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor_gui.py: {}", e))?;
            log::info!("Script wav_monitor_gui.py iniciado correctamente");
            return Ok(child);
        }
        #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
        {
            return Err("Sistema operativo no soportado para iniciar el script wav_monitor_gui.py".to_string());
        }
    }
    #[cfg(not(debug_assertions))]
    {
        // En release, ejecuta el .exe desde la ruta del ejecutable
        let exe_path = std::env::current_exe().map_err(|e| e.to_string())?;
        let exe_dir = exe_path.parent().ok_or("Failed to get executable directory")?;
        let exe_file = exe_dir.join("wav_monitor_gui.exe");
        if !exe_file.exists() {
            return Err(format!("wav_monitor_gui.exe no encontrado en: {:?}", exe_file));
        }
        let mut cmd = std::process::Command::new(exe_file);

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }
        let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor_gui.exe: {}", e))?;
        log::info!("wav_monitor_gui.exe iniciado correctamente");
        Ok(child)
    }
} 