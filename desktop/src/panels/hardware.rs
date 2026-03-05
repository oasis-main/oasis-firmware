//! Hardware tab - KiCAD integration and PCB design

use eframe::egui;
use crate::state::AppState;

pub fn show(ui: &mut egui::Ui, state: &mut AppState) {
    ui.heading("Hardware Design");
    ui.separator();
    
    ui.columns(2, |columns| {
        // Left: KiCAD tools
        columns[0].heading("KiCAD Integration");
        
        columns[0].group(|ui| {
            ui.heading("Import");
            ui.label("Import existing KiCAD project to generate device.yaml");
            
            ui.horizontal(|ui| {
                if ui.button("📂 Select KiCAD Project").clicked() {
                    // TODO: Integrate file dialog when rfd compatible version available
                    tracing::info!("KiCAD import requested");
                }
            });
        });
        
        columns[0].add_space(10.0);
        
        columns[0].group(|ui| {
            ui.heading("Export");
            ui.label("Generate KiCAD project scaffold from device.yaml");
            
            ui.horizontal(|ui| {
                ui.label("Template:");
                egui::ComboBox::from_id_source("kicad_template")
                    .selected_text("Modular")
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut "modular", "modular", "Modular (hierarchical sheets)");
                        ui.selectable_value(&mut "flat", "modular", "Flat (single sheet)");
                        ui.selectable_value(&mut "minimal", "modular", "Minimal");
                    });
            });
            
            if ui.button("📤 Generate KiCAD Scaffold").clicked() {
                // Would call oasis-kicad scaffold
            }
        });
        
        columns[0].add_space(10.0);
        
        columns[0].group(|ui| {
            ui.heading("Design Review");
            ui.label("Get connector and junction recommendations");
            
            if ui.button("🔍 Run Design Review").clicked() {
                // Would call oasis-kicad review
            }
        });
        
        // Right: Junction recommendations
        columns[1].heading("Junction Advisor");
        
        columns[1].group(|ui| {
            ui.heading("Connector Recommendations");
            
            egui::Grid::new("connector_grid")
                .striped(true)
                .show(ui, |ui| {
                    ui.strong("Interface");
                    ui.strong("Connector");
                    ui.strong("Notes");
                    ui.end_row();
                    
                    ui.label("I2C Sensors");
                    ui.label("JST-SH 4-pin");
                    ui.label("VCC, GND, SDA, SCL");
                    ui.end_row();
                    
                    ui.label("Power Input");
                    ui.label("XT30");
                    ui.label("< 15A, 5-12V");
                    ui.end_row();
                    
                    ui.label("Serial Debug");
                    ui.label("JST-XH 4-pin");
                    ui.label("VCC, GND, TX, RX");
                    ui.end_row();
                });
        });
        
        columns[1].add_space(10.0);
        
        columns[1].group(|ui| {
            ui.heading("Cable Specifications");
            
            egui::Grid::new("cable_grid")
                .striped(true)
                .show(ui, |ui| {
                    ui.strong("Connection");
                    ui.strong("Type");
                    ui.strong("Max Length");
                    ui.end_row();
                    
                    ui.label("MCU ↔ Sensors");
                    ui.label("4-wire shielded");
                    ui.label("1m @ 400kHz");
                    ui.end_row();
                    
                    ui.label("MCU ↔ Actuators");
                    ui.label("2/3-wire");
                    ui.label("3m");
                    ui.end_row();
                });
        });
        
        columns[1].add_space(10.0);
        
        columns[1].group(|ui| {
            ui.heading("Enclosure");
            ui.label("• IP65 minimum for outdoor");
            ui.label("• Include mounting holes for board");
            ui.label("• Cable glands for wire entry");
        });
    });
}
