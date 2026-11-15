//! Deploy tab - Build and flash firmware

use eframe::egui;
use crate::state::{AppState, DeploymentStatus};

pub fn show(ui: &mut egui::Ui, state: &mut AppState) {
    ui.heading("Deployment");
    ui.separator();
    
    ui.columns(2, |columns| {
        // Left: Deployment settings
        columns[0].heading("Target Configuration");
        
        columns[0].group(|ui| {
            ui.heading("Deployment Method");
            
            ui.horizontal(|ui| {
                ui.radio_value(&mut "usb", "usb", "USB Serial (espflash)");
            });
            ui.horizontal(|ui| {
                ui.radio_value(&mut "ssh", "usb", "SSH + rsync (RPi)");
            });
            ui.horizontal(|ui| {
                ui.radio_value(&mut "ota", "usb", "Over-The-Air (OTA)");
            });
        });
        
        columns[0].add_space(10.0);
        
        columns[0].group(|ui| {
            ui.heading("USB Serial");
            
            ui.horizontal(|ui| {
                ui.label("Port:");
                egui::ComboBox::from_id_source("serial_port")
                    .selected_text("/dev/ttyUSB0")
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut "/dev/ttyUSB0", "/dev/ttyUSB0", "/dev/ttyUSB0");
                        ui.selectable_value(&mut "/dev/ttyACM0", "/dev/ttyUSB0", "/dev/ttyACM0");
                    });
            });
            
            ui.horizontal(|ui| {
                ui.label("Baud:");
                egui::ComboBox::from_id_source("baud_rate")
                    .selected_text("921600")
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut 921600_u32, 921600, "921600");
                        ui.selectable_value(&mut 460800_u32, 921600, "460800");
                        ui.selectable_value(&mut 115200_u32, 921600, "115200");
                    });
            });
            
            if ui.button("🔄 Refresh Ports").clicked() {
                // Would scan for serial ports
            }
        });
        
        columns[0].add_space(10.0);
        
        columns[0].group(|ui| {
            ui.heading("SSH Target (RPi)");
            
            let mut host = String::from("raspberrypi.local");
            let mut user = String::from("pi");
            
            ui.horizontal(|ui| {
                ui.label("Host:");
                ui.text_edit_singleline(&mut host);
            });
            
            ui.horizontal(|ui| {
                ui.label("User:");
                ui.text_edit_singleline(&mut user);
            });
            
            if ui.button("🔗 Test Connection").clicked() {
                // Would test SSH connection
            }
        });
        
        // Right: Build and deploy actions
        columns[1].heading("Actions");
        
        columns[1].group(|ui| {
            ui.heading("Build");
            
            let build_enabled = state.config_valid && state.deployment_status == DeploymentStatus::Idle;
            
            ui.horizontal(|ui| {
                if ui.add_enabled(build_enabled, egui::Button::new("🔨 Build Firmware")).clicked() {
                    state.deployment_status = DeploymentStatus::Building;
                    // Would trigger cargo build
                }
                
                ui.checkbox(&mut false, "Release mode");
            });
        });
        
        columns[1].add_space(10.0);
        
        columns[1].group(|ui| {
            ui.heading("Deploy");
            
            let deploy_enabled = state.deployment_status == DeploymentStatus::Idle;
            
            if ui.add_enabled(deploy_enabled, egui::Button::new("⚡ Flash to Device")).clicked() {
                state.deployment_status = DeploymentStatus::Flashing;
                // Would trigger flash
            }
            
            if ui.add_enabled(deploy_enabled, egui::Button::new("📤 Deploy via SSH")).clicked() {
                state.deployment_status = DeploymentStatus::Flashing;
                // Would trigger rsync + systemctl restart
            }
        });
        
        columns[1].add_space(10.0);
        
        columns[1].group(|ui| {
            ui.heading("Build Output");
            
            egui::ScrollArea::vertical()
                .id_source("build_output")
                .max_height(200.0)
                .show(ui, |ui| {
                    match &state.deployment_status {
                        DeploymentStatus::Idle => {
                            ui.label("Ready to build");
                        }
                        DeploymentStatus::Building => {
                            ui.code("$ cargo build --release\n   Compiling oasis-device v0.1.0\n   ...");
                        }
                        DeploymentStatus::Flashing => {
                            ui.code("$ espflash flash target/release/oasis-device\n   Connecting...\n   Flashing...");
                        }
                        DeploymentStatus::Success => {
                            ui.code("✓ Deployment successful!\n   Device is running.");
                        }
                        DeploymentStatus::Failed(e) => {
                            ui.code(format!("✗ Deployment failed:\n   {}", e));
                        }
                        _ => {}
                    }
                });
        });
    });
}
