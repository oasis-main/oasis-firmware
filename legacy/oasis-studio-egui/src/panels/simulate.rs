//! Simulate tab - Visual simulation construction and runtime

use eframe::egui;
use crate::state::{AppState, SimulationMode, SimInstance};

pub fn show(ui: &mut egui::Ui, state: &mut AppState) {
    ui.horizontal(|ui| {
        ui.heading("Simulation");
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            // Time display
            ui.label(format!("⏱ {}ms", state.sim_time_ms));
            ui.separator();
            
            // Step controls
            if ui.button("⏭ +1s").clicked() {
                state.sim_step_requested = Some(1000);
            }
            if ui.button("⏭ +100ms").clicked() {
                state.sim_step_requested = Some(100);
            }
            
            ui.separator();
            
            if state.simulation_running {
                if ui.button("⏹ Stop").clicked() {
                    state.simulation_running = false;
                }
                if ui.button("⏸ Pause").clicked() {
                    state.sim_paused = true;
                }
            } else {
                if ui.button("▶ Start").clicked() {
                    state.simulation_running = true;
                    state.sim_paused = false;
                }
            }
        });
    });
    
    ui.separator();
    
    // Three-column layout: Components | Canvas | Signals
    ui.columns(3, |columns| {
        // Left: Component palette
        show_component_palette(&mut columns[0], state);
        
        // Center: Visual canvas
        show_simulation_canvas(&mut columns[1], state);
        
        // Right: Signal inspector
        show_signal_inspector(&mut columns[2], state);
    });
}

fn show_component_palette(ui: &mut egui::Ui, state: &mut AppState) {
    ui.heading("Components");
    
    ui.group(|ui| {
        ui.label(egui::RichText::new("Sensors").strong());
        
        for component in &["dht22", "bme280", "scd40", "soil_moisture", "light_sensor"] {
            if ui.button(format!("+ {}", component)).clicked() {
                let instance_id = format!("{}_{}", component, state.sim_instances.len());
                state.sim_instances.push(SimInstance {
                    id: instance_id,
                    component_type: component.to_string(),
                    x: 100.0,
                    y: 100.0 + (state.sim_instances.len() as f32 * 60.0),
                });
            }
        }
    });
    
    ui.add_space(10.0);
    
    ui.group(|ui| {
        ui.label(egui::RichText::new("Actuators").strong());
        
        for component in &["relay", "servo", "dc_motor", "led_strip", "pump"] {
            if ui.button(format!("+ {}", component)).clicked() {
                let instance_id = format!("{}_{}", component, state.sim_instances.len());
                state.sim_instances.push(SimInstance {
                    id: instance_id,
                    component_type: component.to_string(),
                    x: 300.0,
                    y: 100.0 + (state.sim_instances.len() as f32 * 60.0),
                });
            }
        }
    });
    
    ui.add_space(10.0);
    
    ui.group(|ui| {
        ui.label(egui::RichText::new("Simulation Mode").strong());
        
        ui.radio_value(&mut state.sim_mode, SimulationMode::Behavioral, "Behavioral (fast)");
        ui.radio_value(&mut state.sim_mode, SimulationMode::McuEmulator, "MCU Emulator");
        ui.radio_value(&mut state.sim_mode, SimulationMode::LinuxBoard, "Linux Board");
        ui.radio_value(&mut state.sim_mode, SimulationMode::MultiBoard, "Multi-Board");
    });
    
    ui.add_space(10.0);
    
    ui.group(|ui| {
        ui.label(egui::RichText::new("Fault Injection").strong());
        
        if let Some(ref selected) = state.sim_selected_instance {
            ui.label(format!("Target: {}", selected));
            
            ui.horizontal(|ui| {
                if ui.button("Disconnect").clicked() {
                    state.sim_fault_requested = Some((selected.clone(), "disconnect".to_string()));
                }
                if ui.button("Stuck").clicked() {
                    state.sim_fault_requested = Some((selected.clone(), "stuck".to_string()));
                }
            });
            ui.horizontal(|ui| {
                if ui.button("Offset").clicked() {
                    state.sim_fault_requested = Some((selected.clone(), "offset".to_string()));
                }
                if ui.button("Noise").clicked() {
                    state.sim_fault_requested = Some((selected.clone(), "noise_increase".to_string()));
                }
            });
        } else {
            ui.label("Select a component to inject faults");
        }
    });
}

fn show_simulation_canvas(ui: &mut egui::Ui, state: &mut AppState) {
    ui.heading("Circuit View");
    
    let canvas_size = egui::vec2(400.0, 500.0);
    let (response, painter) = ui.allocate_painter(canvas_size, egui::Sense::click_and_drag());
    let rect = response.rect;
    
    // Background
    painter.rect_filled(rect, 0.0, egui::Color32::from_rgb(30, 30, 40));
    
    // Grid
    let grid_spacing = 20.0;
    for x in (rect.left() as i32..rect.right() as i32).step_by(grid_spacing as usize) {
        painter.line_segment(
            [egui::pos2(x as f32, rect.top()), egui::pos2(x as f32, rect.bottom())],
            egui::Stroke::new(0.5, egui::Color32::from_rgb(50, 50, 60)),
        );
    }
    for y in (rect.top() as i32..rect.bottom() as i32).step_by(grid_spacing as usize) {
        painter.line_segment(
            [egui::pos2(rect.left(), y as f32), egui::pos2(rect.right(), y as f32)],
            egui::Stroke::new(0.5, egui::Color32::from_rgb(50, 50, 60)),
        );
    }
    
    // Draw components
    for instance in &state.sim_instances {
        let pos = egui::pos2(rect.left() + instance.x, rect.top() + instance.y);
        let size = egui::vec2(80.0, 40.0);
        let comp_rect = egui::Rect::from_min_size(pos, size);
        
        let is_selected = state.sim_selected_instance.as_ref() == Some(&instance.id);
        let fill_color = if is_selected {
            egui::Color32::from_rgb(80, 120, 200)
        } else {
            egui::Color32::from_rgb(60, 80, 120)
        };
        
        painter.rect_filled(comp_rect, 4.0, fill_color);
        painter.rect_stroke(comp_rect, 4.0, egui::Stroke::new(1.0, egui::Color32::WHITE));
        
        // Label
        painter.text(
            comp_rect.center(),
            egui::Align2::CENTER_CENTER,
            &instance.component_type,
            egui::FontId::proportional(10.0),
            egui::Color32::WHITE,
        );
        
        // Instance ID below
        painter.text(
            egui::pos2(comp_rect.center().x, comp_rect.bottom() + 8.0),
            egui::Align2::CENTER_TOP,
            &instance.id,
            egui::FontId::proportional(8.0),
            egui::Color32::GRAY,
        );
    }
    
    // Handle clicks for selection
    if response.clicked() {
        if let Some(pos) = response.interact_pointer_pos() {
            let local_pos = pos - rect.min.to_vec2();
            state.sim_selected_instance = None;
            
            for instance in &state.sim_instances {
                let comp_rect = egui::Rect::from_min_size(
                    egui::pos2(instance.x, instance.y),
                    egui::vec2(80.0, 40.0),
                );
                if comp_rect.contains(local_pos) {
                    state.sim_selected_instance = Some(instance.id.clone());
                    break;
                }
            }
        }
    }
    
    // Status bar
    ui.add_space(5.0);
    ui.horizontal(|ui| {
        ui.label(format!("{} components", state.sim_instances.len()));
        ui.separator();
        if state.simulation_running && !state.sim_paused {
            ui.label(egui::RichText::new("● Running").color(egui::Color32::GREEN));
        } else if state.sim_paused {
            ui.label(egui::RichText::new("⏸ Paused").color(egui::Color32::YELLOW));
        } else {
            ui.label("● Stopped");
        }
    });
}

fn show_signal_inspector(ui: &mut egui::Ui, state: &mut AppState) {
    ui.heading("Signals");
    
    if state.sim_signals.is_empty() {
        ui.label("No signals yet. Start simulation to see values.");
    } else {
        egui::ScrollArea::vertical()
            .id_source("signal_list")
            .show(ui, |ui| {
                for (name, value) in &state.sim_signals {
                    ui.group(|ui| {
                        ui.horizontal(|ui| {
                            ui.label(egui::RichText::new(name).strong());
                            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                ui.label(format!("{:.2}", value));
                            });
                        });
                    });
                }
            });
    }
    
    ui.add_space(10.0);
    ui.heading("Input Override");
    
    if let Some(ref selected) = state.sim_selected_instance {
        ui.label(format!("Override inputs for: {}", selected));
        
        ui.horizontal(|ui| {
            ui.label("temp_actual:");
            ui.add(egui::DragValue::new(&mut state.sim_input_override_temp).speed(0.1).suffix("°C"));
        });
        
        ui.horizontal(|ui| {
            ui.label("humidity_actual:");
            ui.add(egui::DragValue::new(&mut state.sim_input_override_humidity).speed(0.1).suffix("%"));
        });
        
        if ui.button("Apply").clicked() {
            state.sim_input_override_requested = true;
        }
    } else {
        ui.label("Select a component to override inputs");
    }
    
    ui.add_space(10.0);
    ui.heading("Waveform");
    
    // Simple waveform display
    let waveform_size = egui::vec2(180.0, 80.0);
    let (_, painter) = ui.allocate_painter(waveform_size, egui::Sense::hover());
    let rect = painter.clip_rect();
    
    painter.rect_filled(rect, 0.0, egui::Color32::from_rgb(20, 20, 30));
    
    // Draw a sample waveform
    if !state.sim_waveform.is_empty() {
        let points: Vec<egui::Pos2> = state.sim_waveform
            .iter()
            .enumerate()
            .map(|(i, &v)| {
                let x = rect.left() + (i as f32 / state.sim_waveform.len() as f32) * rect.width();
                let y = rect.center().y - (v as f32 - 25.0) * 2.0;
                egui::pos2(x, y.clamp(rect.top(), rect.bottom()))
            })
            .collect();
        
        if points.len() > 1 {
            for window in points.windows(2) {
                painter.line_segment(
                    [window[0], window[1]],
                    egui::Stroke::new(1.5, egui::Color32::GREEN),
                );
            }
        }
    }
}
