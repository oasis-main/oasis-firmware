//! Application state management

use std::path::PathBuf;
use std::collections::HashMap;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Tab {
    Configure,
    Simulate,
    Hardware,
    Deploy,
    Monitor,
}

impl Default for Tab {
    fn default() -> Self {
        Tab::Configure
    }
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
