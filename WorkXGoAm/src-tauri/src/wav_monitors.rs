use std::path::Path;
use std::process::{Child, Command};
use std::sync::Mutex;
use log::info;

/// Estructuras para almacenar los procesos de los scripts de Python wav_monitor
pub struct WavMonitorProcess {
    pub child: Mutex<Option<Child>>,
}

/// Estructuras para almacenar los procesos de los scripts de Python wav_monitor_gui
pub struct WavMonitorGuiProcess {
    pub child: Mutex<Option<Child>>,
}

/// Función para iniciar el script wav_monitor.py en una terminal visible
pub fn start_wav_monitor() -> Result<Child, String> {
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

/// Función para iniciar el script wav_monitor_gui.py en una terminal visible
pub fn start_wav_monitor_gui() -> Result<Child, String> {
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