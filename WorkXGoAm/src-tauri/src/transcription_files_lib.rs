use std::fs::read_to_string;
use std::fs::read_dir;
use std::path::PathBuf;
use crate::running_flags::read_temp_flag;
use serde::Serialize;

#[derive(Serialize)]
pub struct TranscriptionFiles {
    pub original: Vec<String>,
    pub english: Vec<String>,
}

#[tauri::command]
pub fn read_transcription_file(path: &str) -> Result<String, String> {
    read_to_string(path).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_transcription_files() -> Result<TranscriptionFiles, String> {
    let monitor_dir = read_temp_flag()?;
    let entries = read_dir(monitor_dir).map_err(|e| e.to_string())?;

    let mut original_files: Vec<(PathBuf, std::time::SystemTime)> = Vec::new();
    let mut english_files: Vec<(PathBuf, std::time::SystemTime)> = Vec::new();

    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        if path.is_file() && path.extension().map_or(false, |ext| ext == "txt") {
            if let Ok(metadata) = entry.metadata() {
                if let Ok(modified) = metadata.modified() {
                    // Clasificar según el sufijo "_EN" antes de la extensión
                    let file_stem = path.file_stem().and_then(|s| s.to_str()).unwrap_or("");
                    if file_stem.ends_with("_EN") {
                        english_files.push((path, modified));
                    } else {
                        original_files.push((path, modified));
                    }
                }
            }
        }
    }

    // Ordenar descendente por fecha de modificación
    original_files.sort_by(|a, b| b.1.cmp(&a.1));
    english_files.sort_by(|a, b| b.1.cmp(&a.1));

    // Convertir a String
    let original: Vec<String> = original_files
        .into_iter()
        .map(|(path, _)| path.to_string_lossy().to_string())
        .collect();

    let english: Vec<String> = english_files
        .into_iter()
        .map(|(path, _)| path.to_string_lossy().to_string())
        .collect();

    Ok(TranscriptionFiles { original, english })
} 