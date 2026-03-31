//! Main application struct and UI layout

use eframe::egui;
use crate::state::{AppState, Tab};
use crate::panels;
use crate::simulation_bridge::SimulationBridge;

pub struct OasisStudio {
    pub state: AppState,
    pub simulation_bridge: SimulationBridge,
}

impl OasisStudio {
    pub fn new(_cc: &eframe::CreationContext<'_>) -> Self {
        Self {
            state: AppState::default(),
            simulation_bridge: SimulationBridge::new(),
        }
    }
}

impl eframe::App for OasisStudio {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Top menu bar
        egui::TopBottomPanel::top("menu_bar").show(ctx, |ui| {
            egui::menu::bar(ui, |ui| {
                ui.menu_button("File", |ui| {
                    if ui.button("New Project").clicked() {
                        self.state.config_yaml = default_config_template();
                        self.state.project_path = None;
                        ui.close_menu();
                    }
                    if ui.button("Open Project...").clicked() {
                        // TODO: Integrate file dialog when rfd compatible version available
                        // For now, use command-line or drag-drop
                        ui.close_menu();
                    }
                    if ui.button("Save").clicked() {
                        if let Some(ref path) = self.state.project_path {
                            let _ = std::fs::write(path, &self.state.config_yaml);
                        }
                        ui.close_menu();
                    }
                    ui.separator();
                    if ui.button("Exit").clicked() {
                        ctx.send_viewport_cmd(egui::ViewportCommand::Close);
                    }
                });
                ui.menu_button("Help", |ui| {
                    if ui.button("Documentation").clicked() {
                        let _ = open::that("https://github.com/oasis-main/oasis-firmware");
                        ui.close_menu();
                    }
                    if ui.button("About").clicked() {
                        ui.close_menu();
                    }
                });
            });
        });

        // Tab bar
        egui::TopBottomPanel::top("tab_bar").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.selectable_value(&mut self.state.current_tab, Tab::Configure, "⚙ Configure");
                ui.selectable_value(&mut self.state.current_tab, Tab::Simulate, "▶ Simulate");
                ui.selectable_value(&mut self.state.current_tab, Tab::Orchestrate, "🔗 Orchestrate");
                ui.selectable_value(&mut self.state.current_tab, Tab::Hardware, "🔧 Hardware");
                ui.selectable_value(&mut self.state.current_tab, Tab::Deploy, "📤 Deploy");
                ui.selectable_value(&mut self.state.current_tab, Tab::Monitor, "📊 Monitor");
                ui.selectable_value(&mut self.state.current_tab, Tab::Tests, "🧪 Tests");
                
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if let Some(ref path) = self.state.project_path {
                        ui.label(format!("📁 {}", path.file_name().unwrap_or_default().to_string_lossy()));
                    } else {
                        ui.label("No project open");
                    }
                });
            });
        });

        // Status bar
        egui::TopBottomPanel::bottom("status_bar").show(ctx, |ui| {
            ui.horizontal(|ui| {
                if self.state.config_valid {
                    ui.label(egui::RichText::new("✓ Config valid").color(egui::Color32::GREEN));
                } else if !self.state.validation_errors.is_empty() {
                    ui.label(egui::RichText::new(format!("✗ {} errors", self.state.validation_errors.len()))
                        .color(egui::Color32::RED));
                }
                
                ui.separator();
                
                match &self.state.deployment_status {
                    crate::state::DeploymentStatus::Idle => ui.label("Ready"),
                    crate::state::DeploymentStatus::Building => ui.label("🔨 Building..."),
                    crate::state::DeploymentStatus::Flashing => ui.label("⚡ Flashing..."),
                    crate::state::DeploymentStatus::Verifying => ui.label("🔍 Verifying..."),
                    crate::state::DeploymentStatus::Success => ui.label(egui::RichText::new("✓ Deployed").color(egui::Color32::GREEN)),
                    crate::state::DeploymentStatus::Failed(e) => ui.label(egui::RichText::new(format!("✗ {}", e)).color(egui::Color32::RED)),
                };
            });
        });

        // Main content area
        egui::CentralPanel::default().show(ctx, |ui| {
            match self.state.current_tab {
                Tab::Configure => panels::configure::show(ui, &mut self.state),
                Tab::Simulate => panels::simulate::show(ui, &mut self.state),
                Tab::Orchestrate => panels::orchestrate::show(ui, &mut self.state, &mut self.simulation_bridge),
                Tab::Hardware => panels::hardware::show(ui, &mut self.state),
                Tab::Deploy => panels::deploy::show(ui, &mut self.state),
                Tab::Monitor => panels::monitor::show(ui, &mut self.state),
                Tab::Tests => panels::tests::show(ui, &mut self.state, &mut self.simulation_bridge),
            }
        });
    }
}

fn default_config_template() -> String {
    r#"device:
  id: my-device
  name: My IoT Device
  version: "0.1.0"
  board:
    platform: mcu
    model: esp32_devkit

connectivity:
  mode: direct_mqtt
  wifi:
    ssid: "${WIFI_SSID}"
    password: "${WIFI_PASSWORD}"
  mqtt:
    broker: mqtt.oasis-x.io
    port: 8883
    tls: true

auth:
  method: api_key
  api_key: "${OASIS_DEVICE_API_KEY}"

sensors:
  - name: temperature
    type: dht22
    pins:
      data: 4
    sampling:
      interval_ms: 5000
    output:
      measurements:
        - name: temperature
          unit: "°C"
        - name: humidity
          unit: "%"

actuators:
  - name: relay
    type: relay
    pins:
      output: 5

data_publishing:
  topic_prefix: "oasis/devices/${device.id}"
  measurements:
    - temperature
    - humidity
"#.to_string()
}
