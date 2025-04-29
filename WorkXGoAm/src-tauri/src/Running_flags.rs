use std::fs::{File};
use std::path::{Path, PathBuf};

// Devuelve la ruta del archivo temporal en AppData/Local/WorkXGoAm
pub fn get_temp_flag_path() -> Result<PathBuf, String> {
    let local_app_data = std::env::var("LOCALAPPDATA").map_err(|e| e.to_string())?;
    let app_data_dir = Path::new(&local_app_data).join("WorkXGoAm");
    println!("AppData directory: {:?}", app_data_dir);
    // Asegura que el directorio exista
    std::fs::create_dir_all(&app_data_dir).map_err(|e| e.to_string())?;
    Ok(app_data_dir.join("running_flag.tmp"))
}

pub struct TempFlagHandler;

impl TempFlagHandler {
    #[allow(dead_code)]
    pub fn new(monitor_dir: &str) -> Result<Self, String> {
        let temp_file_path = get_temp_flag_path()?;
        std::fs::write(&temp_file_path, monitor_dir).map_err(|e| e.to_string())?;
        println!("Temporary file created at {:?} with path {}", temp_file_path, monitor_dir);
        Ok(TempFlagHandler)
    }
}

// Obtiene la ruta almacenada en running_flag.tmp
pub fn read_temp_flag() -> Result<String, String> {
    let temp_file_path = get_temp_flag_path()?;
    std::fs::read_to_string(&temp_file_path).map_err(|e| e.to_string())
}