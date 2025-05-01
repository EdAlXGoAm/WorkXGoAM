use std::process::{Child};
use std::sync::Mutex;
use std::path::PathBuf;
use crate::files_lib::read_file;
use crate::running_flags::get_temp_flag_path;

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

/// Función para iniciar el script realtime_transcribe.py con los argumentos requeridos
pub fn start_wav_monitor() -> Result<Child, String> {
    // Leo el path del directorio desde running_flag.tmp
    let flag_path = get_temp_flag_path()?;
    let monitor_dir = read_file(flag_path.to_string_lossy().as_ref())?.trim().to_string();
    #[cfg(debug_assertions)]
    {
        // En modo debug, ejecuta el .py desde la ruta fuente
        let script_path = {
            let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
            manifest_dir.parent().expect("Error al obtener el directorio del proyecto").join("src-python").join("realtime_transcribe.py")
        };
        log::info!("Intentando ejecutar el script de Python: {:?}", script_path);
        #[cfg(target_os = "windows")]
        {
            let mut cmd = std::process::Command::new("cmd");
            cmd.args(&["/c", "start", "cmd", "/k", "python"]);
            cmd.arg(script_path);
            cmd.arg("--source");
            cmd.arg("output");
            cmd.arg("--outdir");
            cmd.arg(&monitor_dir);
            cmd.arg("--azure");
            let child = cmd.spawn().map_err(|e| format!("Error al iniciar realtime_transcribe.py: {}", e))?;
            log::info!("Script realtime_transcribe.py iniciado correctamente");
            return Ok(child);
        }
        #[cfg(not(target_os = "windows"))]
        {
            return Err("Solo implementado para Windows en este cambio".to_string());
        }
    }
    #[cfg(not(debug_assertions))]
    {
        // En release, ejecuta el .py desde la ruta fuente (no .exe)
        #[cfg(target_os = "windows")]
        {
            let script_path = {
                let exe_path = std::env::current_exe().map_err(|e| e.to_string())?;
                exe_path.parent().expect("Error al obtener el directorio del proyecto").join("realtime_transcribe.exe")
            };
            log::info!("Intentando ejecutar el script de Python: {:?}", script_path);
            let mut cmd = std::process::Command::new("cmd");
            cmd.args(&["/c", "start", "cmd", "/k", "python"]);
            cmd.arg(script_path);
            cmd.arg("--source");
            cmd.arg("output");
            cmd.arg("--outdir");
            cmd.arg(&monitor_dir);
            cmd.arg("--azure");
            let child = cmd.spawn().map_err(|e| format!("Error al iniciar realtime_transcribe.exe: {}", e))?;
            log::info!("Script realtime_transcribe.exe iniciado correctamente");
            return Ok(child);
        }
        #[cfg(not(target_os = "windows"))]
        {
            return Err("Solo implementado para Windows en este cambio".to_string());
        }
    }
}

/// Función para iniciar el script wav_monitor_gui.py o wav_monitor_gui.exe según el modo
pub fn start_wav_monitor_gui() -> Result<Child, String> {
    // Leo el path del directorio desde running_flag.tmp
    let flag_path = get_temp_flag_path()?;
    let monitor_dir = read_file(flag_path.to_string_lossy().as_ref())?.trim().to_string();
    #[cfg(debug_assertions)]
    {
        // En modo debug, ejecuta el .py desde la ruta fuente
        let script_path = {
            let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
            manifest_dir.parent().expect("Error al obtener el directorio del proyecto").join("src-python").join("wav_monitor_gui.py")
        };
        log::info!("Intentando ejecutar el script de Python: {:?}", script_path);
        #[cfg(target_os = "windows")]
        {
            let mut cmd = std::process::Command::new("cmd");
            cmd.args(&["/c", "start", "cmd", "/k", "python"]);
            cmd.arg(script_path);
            cmd.arg("--monitor-dir");
            cmd.arg(&monitor_dir);
            let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor_gui.py: {}", e))?;
            log::info!("Script wav_monitor_gui.py iniciado correctamente");
            return Ok(child);
        }
        #[cfg(target_os = "linux")]
        {
            let mut cmd = std::process::Command::new("gnome-terminal");
            cmd.args(&["--", "python"]);
            cmd.arg(script_path);
            cmd.arg("--monitor-dir");
            cmd.arg(&monitor_dir);
            let child = cmd.spawn().map_err(|e| format!("Error al iniciar wav_monitor_gui.py: {}", e))?;
            log::info!("Script wav_monitor_gui.py iniciado correctamente");
            return Ok(child);
        }
        #[cfg(target_os = "macos")]
        {
            let mut cmd = std::process::Command::new("open");
            cmd.args(&["-a", "Terminal"]);
            cmd.arg(script_path);
            cmd.arg("--monitor-dir");
            cmd.arg(&monitor_dir);
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
        cmd.arg("--monitor-dir");
        cmd.arg(&monitor_dir);
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

/// Comando Tauri para iniciar wav_monitor bajo demanda
#[tauri::command]
pub fn start_wav_monitor_cmd() -> Result<String, String> {
    start_wav_monitor().map(|_| "wav_monitor iniciado".into()).map_err(|e| e)
}

/// Comando Tauri para iniciar wav_monitor_gui bajo demanda
#[tauri::command]
pub fn start_wav_monitor_gui_cmd() -> Result<String, String> {
    start_wav_monitor_gui().map(|_| "wav_monitor_gui iniciado".into()).map_err(|e| e)
} 