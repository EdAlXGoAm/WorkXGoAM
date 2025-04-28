use wasapi::{DeviceCollection, Direction};
use serde::Serialize;

#[derive(Serialize)]
pub struct AudioDevice {
    pub name: String,
    pub id: String,
}

#[tauri::command]
pub fn get_audio_devices() -> Result<Vec<AudioDevice>, String> {
    let outputs = DeviceCollection::new(&Direction::Render)
        .map_err(|e| e.to_string())?;
    
    let mut devices = Vec::new();
    let count = outputs.get_nbr_devices().map_err(|e| e.to_string())?;
    
    for i in 0..count {
        let device = outputs.get_device_at_index(i).map_err(|e| e.to_string())?;
        let name = device.get_friendlyname().map_err(|e| e.to_string())?;
        let id = device.get_id().map_err(|e| e.to_string())?;
        
        devices.push(AudioDevice {
            name,
            id,
        });
    }
    
    Ok(devices)
} 