//! Configure tab - YAML editor with validation

use eframe::egui;
use crate::state::AppState;

pub fn show(ui: &mut egui::Ui, state: &mut AppState) {
    ui.horizontal(|ui| {
        ui.heading("Device Configuration");
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            if ui.button("🔍 Validate").clicked() {
                validate_config(state);
            }
            if ui.button("⚡ Generate").clicked() {
                generate_firmware(state);
            }
        });
    });
    
    ui.separator();
    
    ui.columns(2, |columns| {
        // Left: YAML editor
        columns[0].heading("device.yaml");
        egui::ScrollArea::vertical()
            .id_source("yaml_editor")
            .show(&mut columns[0], |ui| {
                ui.add(
                    egui::TextEdit::multiline(&mut state.config_yaml)
                        .code_editor()
                        .desired_width(f32::INFINITY)
                        .desired_rows(40)
                        .font(egui::TextStyle::Monospace)
                );
            });
        
        // Right: Validation results & preview
        columns[1].heading("Validation");
        
        if state.validation_errors.is_empty() && state.config_valid {
            columns[1].label(egui::RichText::new("✓ Configuration is valid").color(egui::Color32::GREEN));
            columns[1].separator();
            
            // Show parsed config preview
            if let Ok(config) = serde_yaml::from_str::<serde_yaml::Value>(&state.config_yaml) {
                columns[1].heading("Device Info");
                if let Some(device) = config.get("device") {
                    if let Some(id) = device.get("id") {
                        columns[1].label(format!("ID: {}", id.as_str().unwrap_or("?")));
                    }
                    if let Some(name) = device.get("name") {
                        columns[1].label(format!("Name: {}", name.as_str().unwrap_or("?")));
                    }
                    if let Some(board) = device.get("board") {
                        if let Some(platform) = board.get("platform") {
                            columns[1].label(format!("Platform: {}", platform.as_str().unwrap_or("?")));
                        }
                        if let Some(model) = board.get("model") {
                            columns[1].label(format!("Model: {}", model.as_str().unwrap_or("?")));
                        }
                    }
                }
                
                columns[1].separator();
                columns[1].heading("Components");
                
                if let Some(sensors) = config.get("sensors").and_then(|s| s.as_sequence()) {
                    columns[1].label(format!("Sensors: {}", sensors.len()));
                    for sensor in sensors {
                        if let Some(name) = sensor.get("name").and_then(|n| n.as_str()) {
                            let sensor_type = sensor.get("type").and_then(|t| t.as_str()).unwrap_or("?");
                            columns[1].label(format!("  • {} ({})", name, sensor_type));
                        }
                    }
                }
                
                if let Some(actuators) = config.get("actuators").and_then(|a| a.as_sequence()) {
                    columns[1].label(format!("Actuators: {}", actuators.len()));
                    for actuator in actuators {
                        if let Some(name) = actuator.get("name").and_then(|n| n.as_str()) {
                            let actuator_type = actuator.get("type").and_then(|t| t.as_str()).unwrap_or("?");
                            columns[1].label(format!("  • {} ({})", name, actuator_type));
                        }
                    }
                }
            }
        } else {
            for error in &state.validation_errors {
                columns[1].label(egui::RichText::new(format!("✗ {}", error)).color(egui::Color32::RED));
            }
        }
        
        // Generated files
        if !state.generated_files.is_empty() {
            columns[1].separator();
            columns[1].heading("Generated Files");
            for file in &state.generated_files {
                columns[1].label(format!("📄 {}", file.file_name().unwrap_or_default().to_string_lossy()));
            }
        }
    });
}

fn validate_config(state: &mut AppState) {
    state.validation_errors.clear();
    state.config_valid = false;
    
    // Parse YAML
    match serde_yaml::from_str::<serde_yaml::Value>(&state.config_yaml) {
        Ok(config) => {
            // Check required fields
            if config.get("device").is_none() {
                state.validation_errors.push("Missing 'device' section".to_string());
            } else {
                let device = config.get("device").unwrap();
                if device.get("id").is_none() {
                    state.validation_errors.push("Missing 'device.id'".to_string());
                }
                if device.get("board").is_none() {
                    state.validation_errors.push("Missing 'device.board'".to_string());
                }
            }
            
            if config.get("connectivity").is_none() {
                state.validation_errors.push("Missing 'connectivity' section".to_string());
            }
            
            if state.validation_errors.is_empty() {
                state.config_valid = true;
            }
        }
        Err(e) => {
            state.validation_errors.push(format!("YAML parse error: {}", e));
        }
    }
}

fn generate_firmware(state: &mut AppState) {
    // Validate first
    validate_config(state);
    
    if !state.config_valid {
        return;
    }
    
    // For now, just show that generation would happen
    // In full implementation, this would call oasis-core
    state.generated_files.clear();
    state.generated_files.push(std::path::PathBuf::from("src/main.rs"));
    state.generated_files.push(std::path::PathBuf::from("src/sensors.rs"));
    state.generated_files.push(std::path::PathBuf::from("src/actuators.rs"));
    state.generated_files.push(std::path::PathBuf::from("Cargo.toml"));
}
