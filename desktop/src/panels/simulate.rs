//! Simulate tab - Wokwi integration and mock GPIO

use eframe::egui;
use crate::state::AppState;

pub fn show(ui: &mut egui::Ui, state: &mut AppState) {
    ui.horizontal(|ui| {
        ui.heading("Simulation");
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            if state.simulation_running {
                if ui.button("⏹ Stop").clicked() {
                    state.simulation_running = false;
                }
            } else {
                if ui.button("▶ Start Simulation").clicked() {
                    state.simulation_running = true;
                }
            }
        });
    });
    
    ui.separator();
    
    ui.columns(2, |columns| {
        // Left: Simulation controls
        columns[0].heading("Simulation Mode");
        
        columns[0].group(|ui| {
            ui.label("Platform");
            ui.horizontal(|ui| {
                ui.radio_value(&mut true, true, "Wokwi (ESP32)");
            });
            ui.horizontal(|ui| {
                ui.radio_value(&mut false, true, "Mock GPIO (RPi)");
            });
        });
        
        columns[0].add_space(10.0);
        
        columns[0].group(|ui| {
            ui.heading("Virtual Sensors");
            
            ui.horizontal(|ui| {
                ui.label("Temperature:");
                ui.add(egui::Slider::new(&mut 25.0_f32, 0.0..=50.0).suffix("°C"));
            });
            
            ui.horizontal(|ui| {
                ui.label("Humidity:");
                ui.add(egui::Slider::new(&mut 60.0_f32, 0.0..=100.0).suffix("%"));
            });
            
            ui.horizontal(|ui| {
                ui.label("Light:");
                ui.add(egui::Slider::new(&mut 500.0_f32, 0.0..=10000.0).suffix(" lux"));
            });
        });
        
        columns[0].add_space(10.0);
        
        columns[0].group(|ui| {
            ui.heading("Virtual Actuators");
            
            ui.horizontal(|ui| {
                ui.label("Relay 1:");
                ui.checkbox(&mut false, "ON");
            });
            
            ui.horizontal(|ui| {
                ui.label("PWM Output:");
                ui.add(egui::Slider::new(&mut 0_u8, 0..=255));
            });
        });
        
        // Right: Simulation output / Wokwi preview
        columns[1].heading("Simulation Output");
        
        if state.simulation_running {
            columns[1].label(egui::RichText::new("● Running").color(egui::Color32::GREEN));
            
            egui::ScrollArea::vertical()
                .id_source("sim_output")
                .max_height(400.0)
                .show(&mut columns[1], |ui| {
                    ui.code(r#"[00:00:01] Initializing sensors...
[00:00:01] DHT22 initialized on GPIO4
[00:00:01] Connecting to MQTT...
[00:00:02] MQTT connected to mqtt.oasis-x.io
[00:00:05] Sensor reading: temp=25.3°C, humidity=58%
[00:00:05] Published to oasis/devices/my-device/measurements
[00:00:10] Sensor reading: temp=25.4°C, humidity=57%
[00:00:10] Published to oasis/devices/my-device/measurements"#);
                });
        } else {
            columns[1].label("Simulation not running");
            columns[1].add_space(20.0);
            
            columns[1].group(|ui| {
                ui.heading("Wokwi Integration");
                ui.label("Generate Wokwi config to test ESP32 firmware in browser.");
                
                if ui.button("📤 Export to Wokwi").clicked() {
                    // Would generate wokwi.toml and diagram.json
                }
                
                ui.add_space(10.0);
                ui.label("Or use mock GPIO for RPi simulation on desktop.");
            });
        }
    });
}
