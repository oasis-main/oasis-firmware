//! Configuration type definitions matching the device.yaml schema

use serde::{Deserialize, Serialize};

/// Root device configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceConfig {
    pub device: Device,
    pub connectivity: Connectivity,
    pub auth: Auth,
    #[serde(default)]
    pub sensors: Vec<Sensor>,
    #[serde(default)]
    pub actuators: Vec<Actuator>,
    #[serde(default)]
    pub control_loops: Vec<ControlLoop>,
    #[serde(default)]
    pub data_publishing: Option<DataPublishing>,
    #[serde(default)]
    pub system: Option<SystemConfig>,
    #[serde(default)]
    pub hardware: Option<HardwareConfig>,
    #[serde(default)]
    pub deployment: Option<DeploymentConfig>,
}

// =============================================================================
// Hardware/PCB Section (KiCAD Integration)
// =============================================================================

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct HardwareConfig {
    /// Path to KiCAD project file (.kicad_pro)
    #[serde(default)]
    pub kicad_project: Option<String>,
    
    /// Mapping of device.yaml component names to KiCAD schematic symbols
    #[serde(default)]
    pub symbols: Vec<SymbolMapping>,
    
    /// Connector definitions
    #[serde(default)]
    pub connectors: Vec<Connector>,
    
    /// Enclosure/housing configuration
    #[serde(default)]
    pub housing: Option<Housing>,
    
    /// Bill of Materials overrides
    #[serde(default)]
    pub bom_overrides: Vec<BomOverride>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolMapping {
    /// Component name from sensors/actuators
    pub component: String,
    /// KiCAD symbol reference (e.g., "U1", "R5")
    pub symbol_ref: String,
    /// Optional KiCAD footprint override
    #[serde(default)]
    pub footprint: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Connector {
    /// Connector name/reference
    pub name: String,
    /// Connector type (e.g., "screw_terminal_4p", "jst_xh_4", "rj45")
    pub connector_type: String,
    /// Signal names for each pin
    pub signals: Vec<String>,
    /// KiCAD symbol reference
    #[serde(default)]
    pub symbol_ref: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Housing {
    /// Housing model identifier
    pub model: String,
    /// Path to FreeCAD/STEP file
    #[serde(default)]
    pub cad_file: Option<String>,
    /// IP rating
    #[serde(default)]
    pub ip_rating: Option<String>,
    /// Dimensions in mm [length, width, height]
    #[serde(default)]
    pub dimensions_mm: Option<[f32; 3]>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BomOverride {
    /// Component reference
    pub component: String,
    /// Manufacturer part number
    #[serde(default)]
    pub mpn: Option<String>,
    /// Supplier (e.g., "digikey", "mouser", "lcsc")
    #[serde(default)]
    pub supplier: Option<String>,
    /// Supplier part number
    #[serde(default)]
    pub supplier_pn: Option<String>,
}

// =============================================================================
// Deployment Section
// =============================================================================

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DeploymentConfig {
    /// Flashing method for MCU
    #[serde(default)]
    pub flash_method: Option<FlashMethod>,
    
    /// Target device address (IP for RPi, serial port for MCU)
    #[serde(default)]
    pub target_address: Option<String>,
    
    /// SSH configuration for RPi deployment
    #[serde(default)]
    pub ssh: Option<SshConfig>,
    
    /// OTA update configuration
    #[serde(default)]
    pub ota: Option<OtaDeployConfig>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FlashMethod {
    /// USB serial (espflash, arduino-cli)
    UsbSerial,
    /// Debug probe (probe-rs, OpenOCD)
    DebugProbe,
    /// Over-the-air via MQTT
    OtaMqtt,
    /// Over-the-air via HTTPS
    OtaHttps,
    /// SSH + rsync for RPi
    SshRsync,
    /// Docker deployment for RPi
    Docker,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SshConfig {
    /// SSH host
    pub host: String,
    /// SSH port (default 22)
    #[serde(default = "default_ssh_port")]
    pub port: u16,
    /// SSH user
    pub user: String,
    /// Path to SSH key
    #[serde(default)]
    pub key_path: Option<String>,
    /// Remote install directory
    #[serde(default = "default_install_dir")]
    pub install_dir: String,
}

fn default_ssh_port() -> u16 {
    22
}

fn default_install_dir() -> String {
    "/opt/oasis".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OtaDeployConfig {
    /// OTA server URL or MQTT topic
    pub endpoint: String,
    /// Firmware signing key path
    #[serde(default)]
    pub signing_key: Option<String>,
    /// Require signed firmware
    #[serde(default)]
    pub require_signature: bool,
}

// =============================================================================
// Device Section
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Device {
    pub id: String,
    pub name: String,
    pub board: Board,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Board {
    pub platform: Platform,
    pub model: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Platform {
    Rpi,
    Mcu,
}

// =============================================================================
// Connectivity Section
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Connectivity {
    pub mode: ConnectivityMode,
    #[serde(default)]
    pub wifi: Option<WifiConfig>,
    #[serde(default)]
    pub mqtt: Option<MqttConfig>,
    #[serde(default)]
    pub https: Option<HttpsConfig>,
    #[serde(default)]
    pub serial: Option<SerialConfig>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConnectivityMode {
    DirectMqtt,
    DirectHttps,
    SerialGateway,
    Hybrid,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WifiConfig {
    pub ssid: String,
    pub password: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MqttConfig {
    pub broker: String,
    #[serde(default = "default_mqtt_port")]
    pub port: u16,
    #[serde(default = "default_true")]
    pub use_tls: bool,
}

fn default_mqtt_port() -> u16 {
    8883
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HttpsConfig {
    pub endpoint: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SerialConfig {
    #[serde(default = "default_baud_rate")]
    pub baud_rate: u32,
    #[serde(default)]
    pub protocol: SerialProtocol,
}

fn default_baud_rate() -> u32 {
    115200
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SerialProtocol {
    #[default]
    CobsMsgpack,
    CobsJson,
    RawJson,
}

// =============================================================================
// Auth Section
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Auth {
    pub api_key: String,
    #[serde(default)]
    pub source_id: Option<u64>,
    #[serde(default)]
    pub admin_id: Option<String>,
}

// =============================================================================
// Sensors Section
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Sensor {
    pub name: String,
    #[serde(rename = "type")]
    pub sensor_type: SensorType,
    #[serde(default)]
    pub pins: SensorPins,
    #[serde(default)]
    pub i2c_address: Option<u8>,
    pub sampling: SamplingConfig,
    pub output: SensorOutput,
    #[serde(default)]
    pub calibration: Option<Calibration>,
    #[serde(default)]
    pub thresholds: Vec<Threshold>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SensorType {
    // Temperature/Humidity
    Dht11,
    Dht22,
    Bme280,
    Bme680,
    Sht31,
    Ds18b20,
    // Light
    Bh1750,
    Tsl2561,
    Veml7700,
    Photoresistor,
    // Moisture
    CapacitiveMoisture,
    ResistiveMoisture,
    // Distance
    Hcsr04,
    Vl53l0x,
    Vl53l1x,
    // Motion
    Mpu6050,
    Mpu9250,
    Bno055,
    Pir,
    // Gas
    Mq2,
    Mq135,
    Ccs811,
    Sgp30,
    // Current/Voltage
    Ina219,
    Acs712,
    VoltageDivider,
    // Weight
    Hx711,
    // Camera
    EspCam,
    RpiCamera,
    // Generic
    AdcRaw,
    I2cCustom,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SensorPins {
    #[serde(default)]
    pub data: Option<u8>,
    #[serde(default)]
    pub sda: Option<u8>,
    #[serde(default)]
    pub scl: Option<u8>,
    #[serde(default)]
    pub trigger: Option<u8>,
    #[serde(default)]
    pub echo: Option<u8>,
    #[serde(default)]
    pub adc: Option<u8>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SamplingConfig {
    pub interval_ms: u32,
    #[serde(default = "default_averaging")]
    pub averaging: u8,
}

fn default_averaging() -> u8 {
    1
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SensorOutput {
    pub measurements: Vec<MeasurementDef>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MeasurementDef {
    pub name: String,
    pub unit: String,
    #[serde(default = "default_precision")]
    pub precision: u8,
}

fn default_precision() -> u8 {
    2
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Calibration {
    #[serde(default)]
    pub offset: f32,
    #[serde(default = "default_scale")]
    pub scale: f32,
}

fn default_scale() -> f32 {
    1.0
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Threshold {
    pub measurement: String,
    #[serde(default)]
    pub min: Option<f32>,
    #[serde(default)]
    pub max: Option<f32>,
    pub on_breach: ThresholdAction,
    #[serde(default)]
    pub actuator_target: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ThresholdAction {
    Log,
    Alert,
    TriggerActuator,
}

// =============================================================================
// Actuators Section
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Actuator {
    pub name: String,
    #[serde(rename = "type")]
    pub actuator_type: ActuatorType,
    #[serde(default)]
    pub pins: ActuatorPins,
    #[serde(default)]
    pub default: Option<ActuatorDefault>,
    #[serde(default)]
    pub constraints: Option<ActuatorConstraints>,
    #[serde(default)]
    pub safety: Option<ActuatorSafety>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ActuatorType {
    // Digital
    Relay,
    RelayNc,
    Led,
    Buzzer,
    // PWM
    Pwm,
    Servo,
    DcMotor,
    // Stepper
    StepperA4988,
    StepperDrv8825,
    StepperTmc2209,
    // I2C
    Pca9685,
    Mcp23017,
    // Communication
    Rs485,
    Modbus,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ActuatorPins {
    #[serde(default)]
    pub output: Option<u8>,
    #[serde(default)]
    pub pwm: Option<u8>,
    #[serde(default)]
    pub step: Option<u8>,
    #[serde(default)]
    pub dir: Option<u8>,
    #[serde(default)]
    pub enable: Option<u8>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActuatorDefault {
    #[serde(default)]
    pub state: Option<OnOff>,
    #[serde(default)]
    pub value: Option<u16>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum OnOff {
    On,
    Off,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActuatorConstraints {
    #[serde(default)]
    pub min_value: Option<u16>,
    #[serde(default)]
    pub max_value: Option<u16>,
    #[serde(default)]
    pub ramp_rate: Option<u16>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActuatorSafety {
    #[serde(default)]
    pub watchdog_timeout_ms: Option<u32>,
    #[serde(default)]
    pub max_on_duration_ms: Option<u32>,
}

// =============================================================================
// Control Loops Section
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ControlLoop {
    pub name: String,
    #[serde(rename = "type")]
    pub loop_type: ControlLoopType,
    pub input: ControlInput,
    pub output: ControlOutput,
    #[serde(default)]
    pub threshold: Option<ThresholdControl>,
    #[serde(default)]
    pub pid: Option<PidControl>,
    #[serde(default)]
    pub schedule: Option<Vec<ScheduleEntry>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ControlLoopType {
    Threshold,
    Pid,
    Schedule,
    StateMachine,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ControlInput {
    pub sensor: String,
    pub measurement: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ControlOutput {
    pub actuator: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThresholdControl {
    pub setpoint: f32,
    pub hysteresis: f32,
    pub direction: ThresholdDirection,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ThresholdDirection {
    Heat,
    Cool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PidControl {
    pub kp: f32,
    pub ki: f32,
    pub kd: f32,
    pub setpoint: f32,
    pub output_min: f32,
    pub output_max: f32,
    pub sample_time_ms: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScheduleEntry {
    pub start_time: String,
    pub end_time: String,
    pub value: serde_json::Value, // Can be bool or int
    #[serde(default)]
    pub days: Option<Vec<Weekday>>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Weekday {
    Mon,
    Tue,
    Wed,
    Thu,
    Fri,
    Sat,
    Sun,
}

// =============================================================================
// Data Publishing Section
// =============================================================================

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct DataPublishing {
    #[serde(default)]
    pub mqtt: Option<MqttPublishing>,
    #[serde(default)]
    pub https: Option<HttpsPublishing>,
    #[serde(default)]
    pub local_storage: Option<LocalStorage>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MqttPublishing {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default)]
    pub telemetry_topic: Option<String>,
    #[serde(default)]
    pub state_topic: Option<String>,
    #[serde(default)]
    pub cmd_topic: Option<String>,
    #[serde(default = "default_publish_interval")]
    pub publish_interval_ms: u32,
    #[serde(default = "default_qos")]
    pub qos: u8,
}

fn default_publish_interval() -> u32 {
    5000
}

fn default_qos() -> u8 {
    1
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HttpsPublishing {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_batch_interval")]
    pub batch_interval_s: u32,
    #[serde(default = "default_batch_size")]
    pub max_batch_size: u32,
    #[serde(default = "default_retry_count")]
    pub retry_count: u8,
}

fn default_batch_interval() -> u32 {
    60
}

fn default_batch_size() -> u32 {
    100
}

fn default_retry_count() -> u8 {
    3
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LocalStorage {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_max_records")]
    pub max_records: u32,
    #[serde(default)]
    pub persist_on_reboot: bool,
}

fn default_max_records() -> u32 {
    1000
}

// =============================================================================
// System Section
// =============================================================================

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SystemConfig {
    #[serde(default)]
    pub log_level: LogLevel,
    #[serde(default)]
    pub watchdog: Option<WatchdogConfig>,
    #[serde(default)]
    pub power: Option<PowerConfig>,
    #[serde(default)]
    pub ota: Option<OtaConfig>,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum LogLevel {
    Error,
    Warn,
    #[default]
    Info,
    Debug,
    Trace,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WatchdogConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_watchdog_timeout")]
    pub timeout_ms: u32,
}

fn default_watchdog_timeout() -> u32 {
    30000
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PowerConfig {
    #[serde(default)]
    pub sleep_mode: SleepMode,
    #[serde(default)]
    pub wake_interval_ms: Option<u32>,
    #[serde(default)]
    pub wake_on_interrupt: Vec<u8>,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SleepMode {
    #[default]
    None,
    Light,
    Deep,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OtaConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_ota_interval")]
    pub check_interval_s: u32,
    #[serde(default)]
    pub update_topic: Option<String>,
}

fn default_ota_interval() -> u32 {
    3600
}
