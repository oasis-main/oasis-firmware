//! Monitor tab - Live MQTT data and device status

use eframe::egui;
use crate::state::AppState;

pub fn show(ui: &mut egui::Ui, state: &mut AppState) {
    ui.horizontal(|ui| {
        ui.heading("Live Monitor");
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            if ui.button("🔗 Connect MQTT").clicked() {
                // Would connect to MQTT broker
            }
            if ui.button("🗑 Clear").clicked() {
                state.mqtt_messages.clear();
            }
        });
    });
    
    ui.separator();
    
    ui.columns(2, |columns| {
        // Left: Device list and status
        columns[0].heading("Connected Devices");
        
        if state.devices.is_empty() {
            columns[0].label("No devices connected");
            columns[0].add_space(10.0);
            
            // Demo device
            columns[0].group(|ui| {
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new("●").color(egui::Color32::GRAY));
                    ui.strong("greenhouse-01");
                });
                ui.label("Platform: ESP32");
                ui.label("Last seen: Never");
            });
        } else {
            for device in &state.devices {
                columns[0].group(|ui| {
                    ui.horizontal(|ui| {
                        let color = if device.connected {
                            egui::Color32::GREEN
                        } else {
                            egui::Color32::GRAY
                        };
                        ui.label(egui::RichText::new("●").color(color));
                        ui.strong(&device.name);
                    });
                    ui.label(format!("Platform: {}", device.platform));
                    if let Some(ref last) = device.last_seen {
                        ui.label(format!("Last seen: {}", last));
                    }
                });
            }
        }
        
        columns[0].add_space(20.0);
        columns[0].heading("MQTT Connection");
        
        columns[0].group(|ui| {
            let mut broker = String::from("mqtt.oasis-x.io");
            let mut port = 8883_u16;
            
            ui.horizontal(|ui| {
                ui.label("Broker:");
                ui.text_edit_singleline(&mut broker);
            });
            
            ui.horizontal(|ui| {
                ui.label("Port:");
                ui.add(egui::DragValue::new(&mut port));
            });
            
            ui.horizontal(|ui| {
                ui.label("Topic filter:");
                let mut topic = String::from("oasis/devices/#");
                ui.text_edit_singleline(&mut topic);
            });
        });
        
        // Right: Message stream
        columns[1].heading("Message Stream");
        
        egui::ScrollArea::vertical()
            .id_source("mqtt_messages")
            .stick_to_bottom(true)
            .show(&mut columns[1], |ui| {
                if state.mqtt_messages.is_empty() {
                    // Demo messages
                    show_demo_message(ui, "oasis/devices/greenhouse-01/measurements", 
                        r#"{"temperature": 25.3, "humidity": 58}"#, "14:32:01");
                    show_demo_message(ui, "oasis/devices/greenhouse-01/status",
                        r#"{"state": "running", "uptime": 3600}"#, "14:32:05");
                    show_demo_message(ui, "oasis/devices/greenhouse-01/measurements",
                        r#"{"temperature": 25.4, "humidity": 57}"#, "14:32:11");
                } else {
                    for msg in &state.mqtt_messages {
                        ui.group(|ui| {
                            ui.horizontal(|ui| {
                                ui.label(egui::RichText::new(&msg.timestamp).small());
                                ui.label(egui::RichText::new(&msg.topic).strong());
                            });
                            ui.code(&msg.payload);
                        });
                    }
                }
            });
        
        columns[1].add_space(10.0);
        
        columns[1].heading("Quick Actions");
        columns[1].horizontal(|ui| {
            if ui.button("📊 Export Data").clicked() {
                // Would export to CSV
            }
            if ui.button("📈 Open Dashboard").clicked() {
                let _ = open::that("https://dashboard.oasis-x.io");
            }
        });
    });
}

fn show_demo_message(ui: &mut egui::Ui, topic: &str, payload: &str, time: &str) {
    ui.group(|ui| {
        ui.horizontal(|ui| {
            ui.label(egui::RichText::new(time).small().color(egui::Color32::GRAY));
            ui.label(egui::RichText::new(topic).strong());
        });
        ui.code(payload);
    });
}
