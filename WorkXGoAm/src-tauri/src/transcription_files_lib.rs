use std::fs::read_to_string;
use std::fs::read_dir;
use std::path::PathBuf;
use crate::running_flags::read_temp_flag;

#[tauri::command]
pub fn read_transcription_file(path: &str) -> Result<String, String> {
    read_to_string(path).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_transcription_files() -> Result<Vec<String>, String> {
    let monitor_dir = read_temp_flag()?;
    let entries = read_dir(monitor_dir).map_err(|e| e.to_string())?;
    let mut txt_files: Vec<(PathBuf, std::time::SystemTime)> = Vec::new();
    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        if path.is_file() && path.extension().map_or(false, |ext| ext == "txt") {
            if let Ok(metadata) = entry.metadata() {
                if let Ok(modified) = metadata.modified() {
                    txt_files.push((path, modified));
                }
            }
        }
    }
    txt_files.sort_by(|a, b| b.1.cmp(&a.1));
    let paths: Vec<String> = txt_files
        .into_iter()
        .map(|(path, _)| path.to_string_lossy().to_string())
        .collect();
    Ok(paths)
} 