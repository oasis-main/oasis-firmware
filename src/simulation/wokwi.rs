//! Wokwi simulation configuration generator
//!
//! Generates:
//! - wokwi.toml - Project configuration
//! - diagram.json - Circuit diagram with components and wiring

use crate::config::*;
use crate::error::Result;
use serde::{Deserialize, Serialize};
use std::path::Path;

/// Wokwi project configuration
#[derive(Debug, Serialize, Deserialize)]
pub struct WokwiConfig {
    pub version: u8,
    pub firmware: String,
    pub elf: String,
}

/// Wokwi diagram (circuit layout)
#[derive(Debug, Serialize, Deserialize)]
pub struct WokwiDiagram {
    pub version: u8,
    pub author: String,
    pub editor: String,
    pub parts: Vec<WokwiPart>,
    pub connections: Vec<WokwiConnection>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct WokwiPart {
    #[serde(rename = "type")]
    pub part_type: String,
    pub id: String,
    pub top: i32,
    pub left: i32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attrs: Option<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(untagged)]
pub enum WokwiConnection {
    Wire(Vec<String>),
}

/// Generate Wokwi simulation files
pub fn generate(config: &DeviceConfig, output_dir: &Path) -> Result<()> {
    // Generate wokwi.toml
    let wokwi_config = WokwiConfig {
        version: 1,
        firmware: format!("target/{}/release/{}-firmware", 
            get_target(&config.device.board.model),
            config.device.id.replace('-', "_")),
        elf: format!("target/{}/release/{}-firmware",
            get_target(&config.device.board.model),
            config.device.id.replace('-', "_")),
    };
    
    let toml_content = format!(r#"[wokwi]
version = 1
firmware = "{}"
elf = "{}"

# Simulation settings
[simulation]
# Return sensor readings from these mock values
# Edit to test different scenarios

[env]
# Environment variables for simulation
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""
"#, wokwi_config.firmware, wokwi_config.elf);
    
    std::fs::write(output_dir.join("wokwi.toml"), toml_content)?;
    
    // Generate diagram.json
    let diagram = generate_diagram(config)?;
    let diagram_json = serde_json::to_string_pretty(&diagram)?;
    std::fs::write(output_dir.join("diagram.json"), diagram_json)?;
    
    // Generate test scenarios
    generate_test_scenarios(config, output_dir)?;
    
    tracing::info!("Generated Wokwi simulation config at {:?}", output_dir);
    Ok(())
}

fn get_target(board: &str) -> &'static str {
    match board {
        "esp32_devkit" => "xtensa-esp32-none-elf",
        "esp32_c3" => "riscv32imc-unknown-none-elf",
        "esp32_s3" => "xtensa-esp32s3-none-elf",
        _ => "xtensa-esp32-none-elf",
    }
}

fn generate_diagram(config: &DeviceConfig) -> Result<WokwiDiagram> {
    let mut parts = Vec::new();
    let mut connections = Vec::new();
    
    // Add main board
    let board_type = match config.device.board.model.as_str() {
        "esp32_devkit" => "board-esp32-devkit-c-v4",
        "esp32_c3" => "board-esp32-c3-devkitm-1",
        "esp32_s3" => "board-esp32-s3-devkitc-1",
        "arduino_uno" => "wokwi-arduino-uno",
        "arduino_mega" => "wokwi-arduino-mega",
        "arduino_nano" => "wokwi-arduino-nano",
        _ => "board-esp32-devkit-c-v4",
    };
    
    parts.push(WokwiPart {
        part_type: board_type.to_string(),
        id: "board".to_string(),
        top: 0,
        left: 0,
        attrs: None,
    });
    
    let mut y_offset = 150;
    
    // Add sensors
    for sensor in &config.sensors {
        let (part_type, sensor_pins) = sensor_to_wokwi(&sensor.sensor_type);
        
        parts.push(WokwiPart {
            part_type: part_type.to_string(),
            id: sensor.name.clone(),
            top: y_offset,
            left: -150,
            attrs: sensor_attrs(&sensor.sensor_type),
        });
        
        // Add connections based on sensor type and pins
        let board_connections = generate_sensor_connections(sensor, &sensor_pins);
        connections.extend(board_connections);
        
        y_offset += 80;
    }
    
    // Add actuators
    for actuator in &config.actuators {
        let part_type = actuator_to_wokwi(&actuator.actuator_type);
        
        parts.push(WokwiPart {
            part_type: part_type.to_string(),
            id: actuator.name.clone(),
            top: y_offset,
            left: 200,
            attrs: None,
        });
        
        // Add connections
        let board_connections = generate_actuator_connections(actuator);
        connections.extend(board_connections);
        
        y_offset += 80;
    }
    
    Ok(WokwiDiagram {
        version: 1,
        author: "oasis-build".to_string(),
        editor: "wokwi".to_string(),
        parts,
        connections,
    })
}

fn sensor_to_wokwi(sensor_type: &SensorType) -> (&'static str, Vec<&'static str>) {
    match sensor_type {
        SensorType::Dht11 => ("wokwi-dht22", vec!["VCC", "SDA", "NC", "GND"]),
        SensorType::Dht22 => ("wokwi-dht22", vec!["VCC", "SDA", "NC", "GND"]),
        SensorType::Ds18b20 => ("wokwi-ds18b20", vec!["VCC", "DQ", "GND"]),
        SensorType::Bme280 | SensorType::Bme680 => ("wokwi-bme280", vec!["VCC", "GND", "SCL", "SDA"]),
        SensorType::Hcsr04 => ("wokwi-hc-sr04", vec!["VCC", "TRIG", "ECHO", "GND"]),
        SensorType::Photoresistor => ("wokwi-photoresistor-sensor", vec!["VCC", "OUT", "GND"]),
        SensorType::Pir => ("wokwi-pir-motion-sensor", vec!["VCC", "OUT", "GND"]),
        SensorType::CapacitiveMoisture | SensorType::ResistiveMoisture => {
            ("wokwi-potentiometer", vec!["VCC", "SIG", "GND"]) // Mock with pot
        }
        _ => ("wokwi-potentiometer", vec!["VCC", "SIG", "GND"]), // Generic analog
    }
}

fn sensor_attrs(sensor_type: &SensorType) -> Option<serde_json::Value> {
    match sensor_type {
        SensorType::Dht22 | SensorType::Dht11 => Some(serde_json::json!({
            "temperature": "25",
            "humidity": "60"
        })),
        SensorType::Ds18b20 => Some(serde_json::json!({
            "temperature": "25"
        })),
        SensorType::Bme280 | SensorType::Bme680 => Some(serde_json::json!({
            "temperature": "25",
            "humidity": "60",
            "pressure": "101325"
        })),
        _ => None,
    }
}

fn actuator_to_wokwi(actuator_type: &ActuatorType) -> &'static str {
    match actuator_type {
        ActuatorType::Relay | ActuatorType::RelayNc => "wokwi-relay",
        ActuatorType::Led => "wokwi-led",
        ActuatorType::Buzzer => "wokwi-buzzer",
        ActuatorType::Servo => "wokwi-servo",
        ActuatorType::DcMotor => "wokwi-dc-motor",
        _ => "wokwi-led", // Fallback
    }
}

fn generate_sensor_connections(sensor: &Sensor, _wokwi_pins: &[&str]) -> Vec<WokwiConnection> {
    let mut connections = Vec::new();
    let sensor_id = &sensor.name;
    
    // Power connections
    connections.push(WokwiConnection::Wire(vec![
        format!("{}:VCC", sensor_id),
        "board:3V3".to_string(),
        "red".to_string(),
    ]));
    connections.push(WokwiConnection::Wire(vec![
        format!("{}:GND", sensor_id),
        "board:GND.1".to_string(),
        "black".to_string(),
    ]));
    
    // Data connections based on sensor pins config
    if let Some(data_pin) = sensor.pins.data {
        connections.push(WokwiConnection::Wire(vec![
            format!("{}:SDA", sensor_id),
            format!("board:{}", data_pin),
            "green".to_string(),
        ]));
    }
    
    if let Some(sda) = sensor.pins.sda {
        connections.push(WokwiConnection::Wire(vec![
            format!("{}:SDA", sensor_id),
            format!("board:{}", sda),
            "blue".to_string(),
        ]));
    }
    
    if let Some(scl) = sensor.pins.scl {
        connections.push(WokwiConnection::Wire(vec![
            format!("{}:SCL", sensor_id),
            format!("board:{}", scl),
            "yellow".to_string(),
        ]));
    }
    
    if let Some(trigger) = sensor.pins.trigger {
        connections.push(WokwiConnection::Wire(vec![
            format!("{}:TRIG", sensor_id),
            format!("board:{}", trigger),
            "orange".to_string(),
        ]));
    }
    
    if let Some(echo) = sensor.pins.echo {
        connections.push(WokwiConnection::Wire(vec![
            format!("{}:ECHO", sensor_id),
            format!("board:{}", echo),
            "purple".to_string(),
        ]));
    }
    
    connections
}

fn generate_actuator_connections(actuator: &Actuator) -> Vec<WokwiConnection> {
    let mut connections = Vec::new();
    let actuator_id = &actuator.name;
    
    // Power
    connections.push(WokwiConnection::Wire(vec![
        format!("{}:VCC", actuator_id),
        "board:5V".to_string(),
        "red".to_string(),
    ]));
    connections.push(WokwiConnection::Wire(vec![
        format!("{}:GND", actuator_id),
        "board:GND.2".to_string(),
        "black".to_string(),
    ]));
    
    // Control pin
    if let Some(output_pin) = actuator.pins.output {
        connections.push(WokwiConnection::Wire(vec![
            format!("{}:IN", actuator_id),
            format!("board:{}", output_pin),
            "green".to_string(),
        ]));
    }
    
    if let Some(pwm_pin) = actuator.pins.pwm {
        connections.push(WokwiConnection::Wire(vec![
            format!("{}:PWM", actuator_id),
            format!("board:{}", pwm_pin),
            "blue".to_string(),
        ]));
    }
    
    connections
}

/// Generate test scenario files for CI/automation
fn generate_test_scenarios(config: &DeviceConfig, output_dir: &Path) -> Result<()> {
    let scenarios_dir = output_dir.join("test_scenarios");
    std::fs::create_dir_all(&scenarios_dir)?;
    
    // Normal operation scenario
    let normal = serde_json::json!({
        "name": "normal_operation",
        "description": "Standard operating conditions",
        "duration_ms": 30000,
        "sensors": config.sensors.iter().map(|s| {
            serde_json::json!({
                "id": s.name,
                "values": match s.sensor_type {
                    SensorType::Dht22 | SensorType::Dht11 => serde_json::json!({
                        "temperature": [22.0, 23.0, 24.0, 25.0],
                        "humidity": [55.0, 58.0, 60.0, 62.0]
                    }),
                    SensorType::CapacitiveMoisture | SensorType::ResistiveMoisture => serde_json::json!({
                        "moisture": [40.0, 42.0, 45.0, 48.0]
                    }),
                    _ => serde_json::json!({"value": [50.0, 52.0, 55.0]})
                }
            })
        }).collect::<Vec<_>>()
    });
    std::fs::write(
        scenarios_dir.join("normal.json"),
        serde_json::to_string_pretty(&normal)?
    )?;
    
    // Threshold breach scenario
    let threshold_breach = serde_json::json!({
        "name": "threshold_breach",
        "description": "Trigger threshold alerts",
        "duration_ms": 30000,
        "sensors": config.sensors.iter().map(|s| {
            serde_json::json!({
                "id": s.name,
                "values": match s.sensor_type {
                    SensorType::Dht22 | SensorType::Dht11 => serde_json::json!({
                        "temperature": [25.0, 28.0, 32.0, 38.0, 42.0],
                        "humidity": [60.0, 70.0, 80.0, 90.0]
                    }),
                    _ => serde_json::json!({"value": [80.0, 90.0, 95.0, 100.0]})
                }
            })
        }).collect::<Vec<_>>()
    });
    std::fs::write(
        scenarios_dir.join("threshold_breach.json"),
        serde_json::to_string_pretty(&threshold_breach)?
    )?;
    
    tracing::info!("Generated test scenarios at {:?}", scenarios_dir);
    Ok(())
}
