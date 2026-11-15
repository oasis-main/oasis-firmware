//! Application state management

use std::path::PathBuf;
use std::collections::HashMap;
use serde::{Deserialize, Serialize};

use crate::simulation_bridge::{SimulationBridge, LinkType};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Tab {
    Configure,
    Simulate,
    Orchestrate,  // New: Multi-board topology
    Hardware,
    Deploy,
    Monitor,
    Tests,        // New: Test runner
}

impl Default for Tab {
    fn default() -> Self {
        Tab::Configure
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub enum SimulationMode {
    #[default]
    Behavioral,
    McuEmulator,
    LinuxBoard,   // New: Linux SBC emulation
    MultiBoard,   // New: Multi-board orchestration
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub enum OrchestrationView {
    #[default]
    Topology,
    Signals,
    Comms,
}

#[derive(Debug, Clone)]
pub struct SimInstance {
    pub id: String,
    pub component_type: String,
    pub x: f32,
    pub y: f32,
}

#[derive(Debug, Clone, Default)]
pub struct AppState {
    pub current_tab: Tab,
    pub project_path: Option<PathBuf>,
    pub config_yaml: String,
    pub config_valid: bool,
    pub validation_errors: Vec<String>,
    pub generated_files: Vec<PathBuf>,
    pub devices: Vec<DeviceInfo>,
    pub mqtt_messages: Vec<MqttMessage>,
    pub simulation_running: bool,
    pub deployment_status: DeploymentStatus,
    
    // Simulation state
    pub sim_mode: SimulationMode,
    pub sim_time_ms: i64,
    pub sim_paused: bool,
    pub sim_instances: Vec<SimInstance>,
    pub sim_selected_instance: Option<String>,
    pub sim_signals: HashMap<String, f64>,
    pub sim_waveform: Vec<f64>,
    pub sim_step_requested: Option<i64>,
    pub sim_fault_requested: Option<(String, String)>,
    pub sim_input_override_temp: f64,
    pub sim_input_override_humidity: f64,
    pub sim_input_override_requested: bool,
    
    // Orchestration state (multi-board)
    pub orch_view: OrchestrationView,
    pub orch_selected_node: Option<String>,
    pub orch_selected_link: Option<String>,
    pub orch_link_mode: bool,  // true = drawing a link
    pub orch_link_start: Option<String>,
    pub orch_add_link_type: LinkType,
    pub orch_board_filter: String,  // Filter for board palette
    
    // Test runner state
    pub test_filter: String,
    pub test_output: String,
    pub test_auto_run: bool,
}

#[derive(Debug, Clone, Default)]
pub struct DeviceInfo {
    pub id: String,
    pub name: String,
    pub platform: String,
    pub model: String,
    pub connected: bool,
    pub last_seen: Option<String>,
}

#[derive(Debug, Clone)]
pub struct MqttMessage {
    pub topic: String,
    pub payload: String,
    pub timestamp: String,
    pub qos: u8,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub enum DeploymentStatus {
    #[default]
    Idle,
    Building,
    Flashing,
    Verifying,
    Success,
    Failed(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectConfig {
    pub name: String,
    pub device_yaml_path: PathBuf,
    pub output_dir: PathBuf,
    pub mqtt_broker: Option<String>,
    pub deploy_target: Option<DeployTarget>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeployTarget {
    pub method: String,  // "ssh", "usb", "ota"
    pub host: Option<String>,
    pub port: Option<String>,
    pub user: Option<String>,
}
