//! Tests tab - Integrated test runner for simulation tests
//!
//! Runs pytest tests from the simulation directory and displays results.

use eframe::egui;
use crate::state::AppState;
use crate::simulation_bridge::SimulationBridge;

pub fn show(ui: &mut egui::Ui, state: &mut AppState, bridge: &mut SimulationBridge) {
    ui.horizontal(|ui| {
        ui.heading("Test Runner");
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            if bridge.test_runner.running {
                ui.spinner();
                if let Some(ref test) = bridge.test_runner.current_test {
                    ui.label(format!("Running: {}", test));
                }
            } else {
                if ui.button("▶ Run All").clicked() {
                    let _ = bridge.run_all_tests();
                }
                if ui.button("🔄 Discover").clicked() {
                    let _ = bridge.discover_tests();
                }
                if ui.button("🗑 Clear").clicked() {
                    bridge.clear_test_results();
                    state.test_output.clear();
                }
            }
        });
    });
    
    ui.separator();
    
    // Two-column layout: Test list | Output
    ui.columns(2, |columns| {
        show_test_list(&mut columns[0], state, bridge);
        show_test_output(&mut columns[1], state, bridge);
    });
}

fn show_test_list(ui: &mut egui::Ui, state: &mut AppState, bridge: &mut SimulationBridge) {
    ui.heading("Tests");
    
    // Filter
    ui.horizontal(|ui| {
        ui.label("🔍");
        ui.text_edit_singleline(&mut state.test_filter);
    });
    
    ui.add_space(5.0);
    
    // Summary
    let passed = bridge.test_runner.results.iter().filter(|r| r.passed).count();
    let failed = bridge.test_runner.results.iter().filter(|r| !r.passed).count();
    let total = bridge.test_runner.results.len();
    
    if total > 0 {
        ui.horizontal(|ui| {
            ui.label(egui::RichText::new(format!("✓ {}", passed)).color(egui::Color32::GREEN));
            ui.label(egui::RichText::new(format!("✗ {}", failed)).color(egui::Color32::RED));
            ui.label(format!("/ {}", total));
        });
        ui.add_space(5.0);
    }
    
    // Collect test data first to avoid borrow issues
    let available_tests: Vec<_> = bridge.test_runner.available_tests.clone();
    let results: Vec<_> = bridge.test_runner.results.iter()
        .map(|r| (r.name.clone(), r.passed))
        .collect();
    
    let mut test_to_run: Option<String> = None;
    
    egui::ScrollArea::vertical()
        .id_source("test_list")
        .show(ui, |ui| {
            // Available tests (discovered)
            if !available_tests.is_empty() {
                ui.group(|ui| {
                    ui.label(egui::RichText::new("Available Tests").strong());
                    
                    for test in &available_tests {
                        if !state.test_filter.is_empty() 
                            && !test.to_lowercase().contains(&state.test_filter.to_lowercase()) {
                            continue;
                        }
                        
                        // Check if this test has a result
                        let result = results.iter()
                            .find(|(name, _)| name.contains(test) || test.contains(name));
                        
                        ui.horizontal(|ui| {
                            // Status icon
                            if let Some((_, passed)) = result {
                                if *passed {
                                    ui.label(egui::RichText::new("✓").color(egui::Color32::GREEN));
                                } else {
                                    ui.label(egui::RichText::new("✗").color(egui::Color32::RED));
                                }
                            } else {
                                ui.label("○");
                            }
                            
                            // Test name (clickable)
                            let test_short = test.split("::").last().unwrap_or(test);
                            if ui.selectable_label(false, test_short).clicked() {
                                test_to_run = Some(test.clone());
                            }
                        });
                    }
                });
            }
            
            ui.add_space(10.0);
            
            // Results - use collected data
            let full_results: Vec<_> = bridge.test_runner.results.iter()
                .map(|r| (r.name.clone(), r.passed, r.duration_ms, r.output.clone()))
                .collect();
            
            if !full_results.is_empty() {
                ui.group(|ui| {
                    ui.label(egui::RichText::new("Results").strong());
                    
                    for (name, passed, duration_ms, output) in &full_results {
                        if !state.test_filter.is_empty() 
                            && !name.to_lowercase().contains(&state.test_filter.to_lowercase()) {
                            continue;
                        }
                        
                        ui.horizontal(|ui| {
                            if *passed {
                                ui.label(egui::RichText::new("✓").color(egui::Color32::GREEN));
                            } else {
                                ui.label(egui::RichText::new("✗").color(egui::Color32::RED));
                            }
                            
                            let name_short = name.split("::").last().unwrap_or(name);
                            if ui.selectable_label(false, name_short).clicked() {
                                state.test_output = output.clone();
                            }
                            
                            if *duration_ms > 0 {
                                ui.label(
                                    egui::RichText::new(format!("{}ms", duration_ms))
                                        .small()
                                        .weak()
                                );
                            }
                        });
                    }
                });
            }
            
            // Test categories - track which to run
            ui.add_space(10.0);
            ui.group(|ui| {
                ui.label(egui::RichText::new("Quick Run").strong());
                
                if ui.button("🌿 Behavioral Tests").clicked() {
                    test_to_run = Some("tests/test_greenhouse_demo.py".to_string());
                }
                
                if ui.button("🔌 Emulator Tests").clicked() {
                    test_to_run = Some("tests/test_emulator_integration.py".to_string());
                }
                
                if ui.button("🐧 Linux Board Tests").clicked() {
                    test_to_run = Some("tests/test_linux_emulator.py".to_string());
                }
            });
        });
    
    // Execute deferred test run
    if let Some(test_name) = test_to_run {
        if let Ok(result) = bridge.run_test(&test_name) {
            state.test_output = result.output;
        }
    }
}

fn show_test_output(ui: &mut egui::Ui, state: &mut AppState, _bridge: &SimulationBridge) {
    ui.heading("Output");
    
    // Toolbar
    ui.horizontal(|ui| {
        if ui.button("📋 Copy").clicked() {
            ui.output_mut(|o| o.copied_text = state.test_output.clone());
        }
        if ui.button("🗑 Clear").clicked() {
            state.test_output.clear();
        }
        
        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            ui.checkbox(&mut state.test_auto_run, "Auto-run on save");
        });
    });
    
    ui.separator();
    
    // Output text area
    egui::ScrollArea::both()
        .id_source("test_output")
        .auto_shrink([false, false])
        .show(ui, |ui| {
            if state.test_output.is_empty() {
                ui.label("Run a test to see output here.");
                ui.add_space(10.0);
                
                // Show tips
                ui.group(|ui| {
                    ui.label(egui::RichText::new("Tips").strong());
                    ui.label("• Click 'Discover' to find available tests");
                    ui.label("• Click a test name to run it individually");
                    ui.label("• Click 'Run All' to run the full test suite");
                });
            } else {
                // Parse and colorize output
                for line in state.test_output.lines() {
                    let color = if line.contains("PASSED") {
                        egui::Color32::GREEN
                    } else if line.contains("FAILED") || line.contains("ERROR") {
                        egui::Color32::RED
                    } else if line.contains("SKIPPED") {
                        egui::Color32::YELLOW
                    } else if line.starts_with("=") || line.starts_with("-") {
                        egui::Color32::GRAY
                    } else {
                        egui::Color32::WHITE
                    };
                    
                    ui.label(egui::RichText::new(line).color(color).monospace());
                }
            }
        });
}
