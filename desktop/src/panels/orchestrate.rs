//! Orchestrate tab - Multi-board topology editor and inter-board communication
//!
//! Visual editor for creating topologies like:
//!   RPi 4 (Linux) ←UART→ Arduino Mega (MCU)
//!   RPi 4 ←I2C→ [BME280, MPU6050]
//!   RPi 4 ←MQTT→ ESP32 ←Serial→ Arduino

use eframe::egui;
use crate::state::{AppState, OrchestrationView};
use crate::simulation_bridge::{SimulationBridge, LinkType};

pub fn show(ui: &mut egui::Ui, state: &mut AppState, bridge: &mut SimulationBridge) {
    ui.horizontal(|ui| {
        ui.heading("Multi-Board Orchestration");
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            // View selector
            ui.selectable_value(&mut state.orch_view, OrchestrationView::Topology, "🔲 Topology");
            ui.selectable_value(&mut state.orch_view, OrchestrationView::Signals, "📊 Signals");
            ui.selectable_value(&mut state.orch_view, OrchestrationView::Comms, "🔗 Comms");
            
            ui.separator();
            
            // Time display
            ui.label(format!("⏱ {}ms", state.sim_time_ms));
            
            // Step controls
            if ui.button("⏭ +1s").clicked() {
                state.sim_step_requested = Some(1000);
            }
            if ui.button("⏭ +100ms").clicked() {
                state.sim_step_requested = Some(100);
            }
        });
    });
    
    ui.separator();
    
    match state.orch_view {
        OrchestrationView::Topology => show_topology_view(ui, state, bridge),
        OrchestrationView::Signals => show_signals_view(ui, state, bridge),
        OrchestrationView::Comms => show_comms_view(ui, state, bridge),
    }
}

fn show_topology_view(ui: &mut egui::Ui, state: &mut AppState, bridge: &mut SimulationBridge) {
    // Three-column layout: Board Palette | Canvas | Properties
    ui.columns(3, |columns| {
        show_board_palette(&mut columns[0], state, bridge);
        show_topology_canvas(&mut columns[1], state, bridge);
        show_properties_panel(&mut columns[2], state, bridge);
    });
}

fn show_board_palette(ui: &mut egui::Ui, state: &mut AppState, bridge: &mut SimulationBridge) {
    ui.heading("Boards");
    
    // Filter
    ui.horizontal(|ui| {
        ui.label("🔍");
        ui.text_edit_singleline(&mut state.orch_board_filter);
    });
    
    // Collect platform data first to avoid borrow issues
    let mcu_platforms: Vec<_> = bridge.mcu_platforms()
        .iter()
        .map(|p| (p.id.clone(), p.name.clone()))
        .collect();
    let linux_platforms: Vec<_> = bridge.linux_platforms()
        .iter()
        .map(|p| (p.id.clone(), p.name.clone(), p.arch.clone()))
        .collect();
    let node_count = bridge.topology.nodes.len();
    
    let mut add_node: Option<(String, String)> = None;
    
    egui::ScrollArea::vertical()
        .id_source("board_palette")
        .show(ui, |ui| {
            // MCU Boards
            ui.group(|ui| {
                ui.label(egui::RichText::new("🔌 MCU Boards").strong());
                
                for (id, name) in &mcu_platforms {
                    if !state.orch_board_filter.is_empty() 
                        && !name.to_lowercase().contains(&state.orch_board_filter.to_lowercase()) {
                        continue;
                    }
                    
                    if ui.button(format!("+ {}", name)).clicked() {
                        add_node = Some((id.clone(), id.clone()));
                    }
                }
            });
            
            ui.add_space(10.0);
            
            // Linux SBC Boards
            ui.group(|ui| {
                ui.label(egui::RichText::new("🐧 Linux Boards").strong());
                
                for (id, name, arch) in &linux_platforms {
                    if !state.orch_board_filter.is_empty() 
                        && !name.to_lowercase().contains(&state.orch_board_filter.to_lowercase()) {
                        continue;
                    }
                    
                    ui.horizontal(|ui| {
                        if ui.button(format!("+ {}", name)).clicked() {
                            add_node = Some((id.clone(), id.clone()));
                        }
                        if let Some(arch) = arch {
                            ui.label(egui::RichText::new(arch).small().weak());
                        }
                    });
                }
            });
            
            ui.add_space(10.0);
            
            // Link Tools
            ui.group(|ui| {
                ui.label(egui::RichText::new("🔗 Connect").strong());
                
                ui.horizontal(|ui| {
                    ui.radio_value(&mut state.orch_add_link_type, LinkType::Uart, "UART");
                    ui.radio_value(&mut state.orch_add_link_type, LinkType::I2c, "I2C");
                });
                ui.horizontal(|ui| {
                    ui.radio_value(&mut state.orch_add_link_type, LinkType::Spi, "SPI");
                    ui.radio_value(&mut state.orch_add_link_type, LinkType::Network, "Net");
                });
                
                if state.orch_link_mode {
                    ui.label(egui::RichText::new("Click second board...").color(egui::Color32::YELLOW));
                    if ui.button("Cancel").clicked() {
                        state.orch_link_mode = false;
                        state.orch_link_start = None;
                    }
                } else {
                    ui.label("Click a board to start link");
                }
            });
            
            ui.add_space(10.0);
            
            // Components
            ui.group(|ui| {
                ui.label(egui::RichText::new("📦 Components").strong());
                
                if let Some(ref node_id) = state.orch_selected_node {
                    ui.label(format!("Add to: {}", node_id));
                    
                    for comp in &["dht22", "bme280", "soil_moisture", "relay", "pump"] {
                        if ui.small_button(format!("+ {}", comp)).clicked() {
                            let _ = bridge.add_component_to_node(node_id, comp);
                        }
                    }
                } else {
                    ui.label("Select a board first");
                }
            });
        });
}

fn show_topology_canvas(ui: &mut egui::Ui, state: &mut AppState, bridge: &mut SimulationBridge) {
    ui.heading("Topology");
    
    let canvas_size = egui::vec2(450.0, 450.0);
    let (response, painter) = ui.allocate_painter(canvas_size, egui::Sense::click_and_drag());
    let rect = response.rect;
    
    // Background
    painter.rect_filled(rect, 0.0, egui::Color32::from_rgb(25, 30, 40));
    
    // Grid
    let grid_spacing = 25.0;
    for x in (rect.left() as i32..rect.right() as i32).step_by(grid_spacing as usize) {
        painter.line_segment(
            [egui::pos2(x as f32, rect.top()), egui::pos2(x as f32, rect.bottom())],
            egui::Stroke::new(0.3, egui::Color32::from_rgb(40, 45, 55)),
        );
    }
    for y in (rect.top() as i32..rect.bottom() as i32).step_by(grid_spacing as usize) {
        painter.line_segment(
            [egui::pos2(rect.left(), y as f32), egui::pos2(rect.right(), y as f32)],
            egui::Stroke::new(0.3, egui::Color32::from_rgb(40, 45, 55)),
        );
    }
    
    // Draw links first (behind nodes)
    for link in &bridge.topology.links {
        let node_a = bridge.topology.nodes.iter().find(|n| n.node_id == link.node_a);
        let node_b = bridge.topology.nodes.iter().find(|n| n.node_id == link.node_b);
        
        if let (Some(a), Some(b)) = (node_a, node_b) {
            let pos_a = egui::pos2(rect.left() + a.x + 50.0, rect.top() + a.y + 25.0);
            let pos_b = egui::pos2(rect.left() + b.x + 50.0, rect.top() + b.y + 25.0);
            
            let color = match link.link_type {
                LinkType::Uart => egui::Color32::from_rgb(100, 200, 100),
                LinkType::I2c => egui::Color32::from_rgb(100, 150, 255),
                LinkType::Spi => egui::Color32::from_rgb(255, 150, 100),
                LinkType::Network => egui::Color32::from_rgb(200, 100, 255),
                LinkType::Gpio => egui::Color32::from_rgb(255, 255, 100),
            };
            
            let is_selected = state.orch_selected_link.as_ref() == Some(&link.link_id);
            let stroke = if is_selected {
                egui::Stroke::new(3.0, color)
            } else {
                egui::Stroke::new(2.0, color)
            };
            
            painter.line_segment([pos_a, pos_b], stroke);
            
            // Link type label at midpoint
            let mid = egui::pos2((pos_a.x + pos_b.x) / 2.0, (pos_a.y + pos_b.y) / 2.0);
            painter.text(
                mid,
                egui::Align2::CENTER_CENTER,
                format!("{}", link.link_type),
                egui::FontId::proportional(9.0),
                color,
            );
        }
    }
    
    // Draw nodes
    for node in &bridge.topology.nodes {
        let pos = egui::pos2(rect.left() + node.x, rect.top() + node.y);
        let size = egui::vec2(100.0, 50.0);
        let node_rect = egui::Rect::from_min_size(pos, size);
        
        let is_selected = state.orch_selected_node.as_ref() == Some(&node.node_id);
        let is_linux = node.board_type.contains("rpi") || node.board_type.contains("beagle") 
                      || node.board_type.contains("jetson") || node.board_type.contains("generic_arm");
        
        let fill_color = if is_selected {
            if is_linux {
                egui::Color32::from_rgb(60, 100, 60)
            } else {
                egui::Color32::from_rgb(80, 100, 180)
            }
        } else {
            if is_linux {
                egui::Color32::from_rgb(40, 70, 40)
            } else {
                egui::Color32::from_rgb(50, 60, 100)
            }
        };
        
        painter.rect_filled(node_rect, 6.0, fill_color);
        painter.rect_stroke(
            node_rect, 
            6.0, 
            egui::Stroke::new(if is_selected { 2.0 } else { 1.0 }, egui::Color32::WHITE)
        );
        
        // Icon
        let icon = if is_linux { "🐧" } else { "🔌" };
        painter.text(
            egui::pos2(node_rect.left() + 10.0, node_rect.center().y),
            egui::Align2::LEFT_CENTER,
            icon,
            egui::FontId::proportional(14.0),
            egui::Color32::WHITE,
        );
        
        // Board type
        painter.text(
            egui::pos2(node_rect.left() + 28.0, node_rect.top() + 12.0),
            egui::Align2::LEFT_TOP,
            &node.board_type,
            egui::FontId::proportional(10.0),
            egui::Color32::WHITE,
        );
        
        // Node ID
        painter.text(
            egui::pos2(node_rect.left() + 28.0, node_rect.bottom() - 12.0),
            egui::Align2::LEFT_BOTTOM,
            &node.node_id,
            egui::FontId::proportional(8.0),
            egui::Color32::GRAY,
        );
        
        // Component count badge
        if !node.components.is_empty() {
            let badge_pos = egui::pos2(node_rect.right() - 8.0, node_rect.top() + 8.0);
            painter.circle_filled(badge_pos, 8.0, egui::Color32::from_rgb(200, 80, 80));
            painter.text(
                badge_pos,
                egui::Align2::CENTER_CENTER,
                format!("{}", node.components.len()),
                egui::FontId::proportional(8.0),
                egui::Color32::WHITE,
            );
        }
    }
    
    // Handle clicks
    if response.clicked() {
        if let Some(pos) = response.interact_pointer_pos() {
            let local_pos = pos - rect.min.to_vec2();
            let mut clicked_node = None;
            
            for node in &bridge.topology.nodes {
                let node_rect = egui::Rect::from_min_size(
                    egui::pos2(node.x, node.y),
                    egui::vec2(100.0, 50.0),
                );
                if node_rect.contains(local_pos) {
                    clicked_node = Some(node.node_id.clone());
                    break;
                }
            }
            
            if let Some(node_id) = clicked_node {
                if state.orch_link_mode {
                    // Complete link
                    if let Some(ref start) = state.orch_link_start {
                        if start != &node_id {
                            bridge.add_link(start, &node_id, state.orch_add_link_type.clone());
                        }
                    }
                    state.orch_link_mode = false;
                    state.orch_link_start = None;
                } else {
                    state.orch_selected_node = Some(node_id);
                    state.orch_selected_link = None;
                }
            } else {
                state.orch_selected_node = None;
            }
        }
    }
    
    // Right-click to start link mode
    if response.secondary_clicked() {
        if let Some(ref selected) = state.orch_selected_node {
            state.orch_link_mode = true;
            state.orch_link_start = Some(selected.clone());
        }
    }
    
    // Status bar
    ui.add_space(5.0);
    ui.horizontal(|ui| {
        ui.label(format!("{} boards", bridge.topology.nodes.len()));
        ui.separator();
        ui.label(format!("{} links", bridge.topology.links.len()));
        ui.separator();
        if state.simulation_running && !state.sim_paused {
            ui.label(egui::RichText::new("● Running").color(egui::Color32::GREEN));
        } else {
            ui.label("● Stopped");
        }
    });
}

fn show_properties_panel(ui: &mut egui::Ui, state: &mut AppState, bridge: &mut SimulationBridge) {
    ui.heading("Properties");
    
    // Collect data first to avoid borrow issues
    let selected_node_id = state.orch_selected_node.clone();
    let selected_link_id = state.orch_selected_link.clone();
    
    // Track actions to perform after rendering
    let mut remove_node: Option<String> = None;
    let mut remove_link: Option<String> = None;
    
    if let Some(ref node_id) = selected_node_id {
        // Collect node data
        let node_data = bridge.topology.nodes.iter()
            .find(|n| &n.node_id == node_id)
            .map(|n| (n.node_id.clone(), n.board_type.clone(), n.is_behavioral, n.components.clone()));
        
        let connected: Vec<_> = bridge.topology.links.iter()
            .filter(|l| &l.node_a == node_id || &l.node_b == node_id)
            .map(|l| {
                let other = if &l.node_a == node_id { l.node_b.clone() } else { l.node_a.clone() };
                (l.link_id.clone(), format!("{}", l.link_type), other)
            })
            .collect();
        
        if let Some((nid, board_type, is_behavioral, components)) = node_data {
            ui.group(|ui| {
                ui.label(egui::RichText::new("Board").strong());
                ui.label(format!("ID: {}", nid));
                ui.label(format!("Type: {}", board_type));
                ui.label(format!("Mode: {}", if is_behavioral { "Behavioral" } else { "Emulated" }));
                
                ui.separator();
                
                if ui.button("🗑 Remove Board").clicked() {
                    remove_node = Some(nid.clone());
                }
            });
            
            ui.add_space(10.0);
            
            ui.group(|ui| {
                ui.label(egui::RichText::new("Components").strong());
                
                if components.is_empty() {
                    ui.label("No components attached");
                } else {
                    for comp in &components {
                        ui.label(format!("• {}", comp));
                    }
                }
            });
            
            ui.add_space(10.0);
            
            ui.group(|ui| {
                ui.label(egui::RichText::new("Connections").strong());
                
                if connected.is_empty() {
                    ui.label("No connections");
                } else {
                    for (lid, link_type, other) in &connected {
                        ui.horizontal(|ui| {
                            ui.label(format!("{} → {}", link_type, other));
                            if ui.small_button("✕").clicked() {
                                remove_link = Some(lid.clone());
                            }
                        });
                    }
                }
            });
        }
    } else if let Some(ref link_id) = selected_link_id {
        let link_data = bridge.topology.links.iter()
            .find(|l| &l.link_id == link_id)
            .map(|l| (l.link_id.clone(), format!("{}", l.link_type), l.node_a.clone(), l.node_b.clone()));
        
        if let Some((lid, link_type, node_a, node_b)) = link_data {
            ui.group(|ui| {
                ui.label(egui::RichText::new("Link").strong());
                ui.label(format!("Type: {}", link_type));
                ui.label(format!("{} ↔ {}", node_a, node_b));
                
                ui.separator();
                
                if ui.button("🗑 Remove Link").clicked() {
                    remove_link = Some(lid);
                }
            });
        }
    } else {
        ui.label("Select a board or link to view properties");
        
        ui.add_space(20.0);
        
        let board_count = bridge.topology.nodes.len();
        let link_count = bridge.topology.links.len();
        let linux_count = bridge.topology.nodes.iter()
            .filter(|n| n.board_type.contains("rpi") || n.board_type.contains("beagle"))
            .count();
        let mcu_count = board_count - linux_count;
        
        ui.group(|ui| {
            ui.label(egui::RichText::new("Topology Summary").strong());
            ui.label(format!("Boards: {}", board_count));
            ui.label(format!("Links: {}", link_count));
            ui.label(format!("  Linux SBCs: {}", linux_count));
            ui.label(format!("  MCUs: {}", mcu_count));
        });
    }
    
    // Apply deferred actions
    if let Some(nid) = remove_node {
        bridge.remove_board_node(&nid);
        state.orch_selected_node = None;
    }
    if let Some(lid) = remove_link {
        bridge.remove_link(&lid);
        state.orch_selected_link = None;
    }
}

fn show_signals_view(ui: &mut egui::Ui, _state: &mut AppState, bridge: &mut SimulationBridge) {
    ui.columns(2, |columns| {
        // Signal list
        columns[0].heading("Signals");
        
        if let Some(ref sim_state) = bridge.state {
            egui::ScrollArea::vertical()
                .id_source("signal_list_orch")
                .show(&mut columns[0], |ui| {
                    for (name, signal) in &sim_state.signals {
                        ui.group(|ui| {
                            ui.horizontal(|ui| {
                                ui.label(egui::RichText::new(name).strong());
                                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                    ui.label(format!("{:.2}", signal.value));
                                });
                            });
                        });
                    }
                });
        } else {
            columns[0].label("No simulation state. Start simulation to see signals.");
        }
        
        // Signal graph placeholder
        columns[1].heading("Waveform");
        
        let graph_size = egui::vec2(200.0, 150.0);
        let (_, painter) = columns[1].allocate_painter(graph_size, egui::Sense::hover());
        let rect = painter.clip_rect();
        
        painter.rect_filled(rect, 0.0, egui::Color32::from_rgb(20, 25, 35));
        painter.text(
            rect.center(),
            egui::Align2::CENTER_CENTER,
            "Signal waveform",
            egui::FontId::proportional(10.0),
            egui::Color32::GRAY,
        );
    });
}

fn show_comms_view(ui: &mut egui::Ui, _state: &mut AppState, bridge: &mut SimulationBridge) {
    ui.heading("Communication Buses");
    
    egui::ScrollArea::vertical()
        .id_source("comms_view")
        .show(ui, |ui| {
            for link in &bridge.topology.links {
                ui.group(|ui| {
                    ui.horizontal(|ui| {
                        let icon = match link.link_type {
                            LinkType::Uart => "📡",
                            LinkType::I2c => "🔌",
                            LinkType::Spi => "⚡",
                            LinkType::Network => "🌐",
                            LinkType::Gpio => "📍",
                        };
                        ui.label(egui::RichText::new(format!("{} {}", icon, link.link_type)).strong());
                    });
                    
                    ui.label(format!("{} ↔ {}", link.node_a, link.node_b));
                    
                    // Show config details
                    match link.link_type {
                        LinkType::Uart => {
                            ui.label("Baud: 115200");
                        }
                        LinkType::I2c => {
                            ui.label("Address: 0x76");
                        }
                        LinkType::Network => {
                            ui.label("Protocol: MQTT");
                        }
                        _ => {}
                    }
                });
            }
            
            if bridge.topology.links.is_empty() {
                ui.label("No communication links configured.");
                ui.label("Right-click a board to create a link.");
            }
        });
}
