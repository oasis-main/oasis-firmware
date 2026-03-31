//! Communication Protocol Templates
//!
//! MQTT, serial bridge, and other protocol implementations.

/// Get MQTT client implementation
pub fn get_mqtt_driver() -> &'static str {
    MQTT_DRIVER
}

/// Get serial bridge implementation
pub fn get_serial_bridge() -> &'static str {
    SERIAL_BRIDGE
}

// =============================================================================
// MQTT Client
// =============================================================================
const MQTT_DRIVER: &str = r#"
use embedded_mqtt::{MqttClient, MqttOptions, QoS};
use embassy_sync::channel::Channel;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;

/// MQTT message types
#[derive(Clone)]
pub enum MqttMessage {
    Telemetry { topic: &'static str, payload: Vec<u8> },
    State { topic: &'static str, payload: Vec<u8> },
    Command { topic: &'static str, payload: Vec<u8> },
}

/// MQTT publish channel
pub static MQTT_TX: Channel<CriticalSectionRawMutex, MqttMessage, 16> = Channel::new();
/// MQTT receive channel
pub static MQTT_RX: Channel<CriticalSectionRawMutex, MqttMessage, 8> = Channel::new();

pub struct OasisMqtt {
    device_id: &'static str,
    broker: &'static str,
    port: u16,
    use_tls: bool,
}

impl OasisMqtt {
    pub fn new(device_id: &'static str, broker: &'static str, port: u16, use_tls: bool) -> Self {
        Self { device_id, broker, port, use_tls }
    }
    
    pub fn telemetry_topic(&self) -> String {
        format!("oasis/devices/{}/telemetry", self.device_id)
    }
    
    pub fn state_topic(&self) -> String {
        format!("oasis/devices/{}/state", self.device_id)
    }
    
    pub fn cmd_topic(&self) -> String {
        format!("oasis/devices/{}/cmd", self.device_id)
    }
    
    /// Publish telemetry data
    pub async fn publish_telemetry(&self, payload: &[u8]) {
        MQTT_TX.send(MqttMessage::Telemetry {
            topic: "telemetry",
            payload: payload.to_vec(),
        }).await;
    }
    
    /// Publish state change
    pub async fn publish_state(&self, payload: &[u8]) {
        MQTT_TX.send(MqttMessage::State {
            topic: "state",
            payload: payload.to_vec(),
        }).await;
    }
}

/// MQTT connection task
#[embassy_executor::task]
pub async fn mqtt_task(config: OasisMqtt) {
    // Connect to broker
    info!("Connecting to MQTT broker {}:{}", config.broker, config.port);
    
    // Main MQTT loop
    loop {
        // Handle outgoing messages
        let msg = MQTT_TX.receive().await;
        match msg {
            MqttMessage::Telemetry { payload, .. } => {
                // Publish to telemetry topic
                info!("MQTT publish: {} bytes", payload.len());
            }
            MqttMessage::State { payload, .. } => {
                // Publish to state topic
                info!("MQTT state: {} bytes", payload.len());
            }
            MqttMessage::Command { topic, payload } => {
                // Forward to command handler
                info!("MQTT command on {}: {} bytes", topic, payload.len());
            }
        }
    }
}
"#;

// =============================================================================
// Serial Bridge (for RPi <-> MCU communication)
// =============================================================================
const SERIAL_BRIDGE: &str = r#"
use embassy_sync::channel::Channel;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use postcard::{from_bytes, to_vec};
use serde::{Deserialize, Serialize};

/// Serial frame types
#[derive(Clone, Serialize, Deserialize)]
pub enum SerialFrame {
    /// Sensor reading from MCU to RPi
    SensorData {
        sensor_id: u8,
        timestamp_ms: u32,
        values: [f32; 4],
    },
    /// Actuator command from RPi to MCU
    ActuatorCmd {
        actuator_id: u8,
        command: ActuatorCommand,
    },
    /// Heartbeat
    Heartbeat { uptime_ms: u32 },
    /// Acknowledgment
    Ack { seq: u16 },
    /// Error
    Error { code: u8, message: [u8; 32] },
}

#[derive(Clone, Serialize, Deserialize)]
pub enum ActuatorCommand {
    SetState(bool),
    SetValue(u16),
    SetPwm { duty: u16, frequency: u16 },
    Stop,
}

/// Serial TX channel
pub static SERIAL_TX: Channel<CriticalSectionRawMutex, SerialFrame, 16> = Channel::new();
/// Serial RX channel  
pub static SERIAL_RX: Channel<CriticalSectionRawMutex, SerialFrame, 16> = Channel::new();

/// COBS-encode and transmit a frame
pub fn encode_frame(frame: &SerialFrame) -> Result<Vec<u8>, postcard::Error> {
    let serialized = to_vec::<_, 64>(frame)?;
    // Add COBS encoding
    let mut encoded = vec![0u8; serialized.len() + 2];
    let len = cobs_encode(&serialized, &mut encoded[..]);
    encoded.truncate(len);
    encoded.push(0x00);  // Frame delimiter
    Ok(encoded)
}

/// Decode a COBS-encoded frame
pub fn decode_frame(data: &[u8]) -> Result<SerialFrame, postcard::Error> {
    let mut decoded = vec![0u8; data.len()];
    let len = cobs_decode(data, &mut decoded);
    from_bytes(&decoded[..len])
}

fn cobs_encode(src: &[u8], dst: &mut [u8]) -> usize {
    let mut dst_idx = 1;
    let mut code_idx = 0;
    let mut code = 1u8;
    
    for &byte in src {
        if byte == 0 {
            dst[code_idx] = code;
            code_idx = dst_idx;
            dst_idx += 1;
            code = 1;
        } else {
            dst[dst_idx] = byte;
            dst_idx += 1;
            code += 1;
            if code == 0xFF {
                dst[code_idx] = code;
                code_idx = dst_idx;
                dst_idx += 1;
                code = 1;
            }
        }
    }
    dst[code_idx] = code;
    dst_idx
}

fn cobs_decode(src: &[u8], dst: &mut [u8]) -> usize {
    let mut src_idx = 0;
    let mut dst_idx = 0;
    
    while src_idx < src.len() {
        let code = src[src_idx];
        src_idx += 1;
        
        if code == 0 { break; }
        
        for _ in 1..code {
            if src_idx >= src.len() { break; }
            dst[dst_idx] = src[src_idx];
            src_idx += 1;
            dst_idx += 1;
        }
        
        if code < 0xFF && src_idx < src.len() {
            dst[dst_idx] = 0;
            dst_idx += 1;
        }
    }
    dst_idx
}
"#;
