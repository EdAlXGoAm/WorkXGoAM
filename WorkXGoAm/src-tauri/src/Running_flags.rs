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
    pub fn new() -> Result<Self, String> {
        let temp_file_path = get_temp_flag_path()?;
        File::create(&temp_file_path).map_err(|e| e.to_string())?;
        println!("Temporary file created at {:?}", temp_file_path);
        Ok(TempFlagHandler)
    }
}