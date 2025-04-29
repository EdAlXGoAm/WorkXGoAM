use std::env;
use std::fs;
use std::path::{Path, PathBuf};

/// Lee un archivo de texto completo y devuelve su contenido
#[tauri::command]
pub fn read_file(path: &str) -> Result<String, String> {
    fs::read_to_string(path).map_err(|e| e.to_string())
}

/// Obtiene el valor de una variable de entorno
#[tauri::command]
pub fn get_env(variable: &str) -> Result<String, String> {
    env::var(variable).map_err(|e| e.to_string())
}

/// Devuelve el directorio de datos de la aplicación en AppData Local/[Project]
#[allow(dead_code)]
pub fn get_app_data_dir() -> Result<PathBuf, String> {
    let local_app_data = env::var("LOCALAPPDATA").map_err(|e| e.to_string())?;
    let app_data_dir = Path::new(&local_app_data).join("WorkXGoAm");
    fs::create_dir_all(&app_data_dir).map_err(|e| e.to_string())?;
    Ok(app_data_dir)
} 