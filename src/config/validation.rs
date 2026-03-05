//! Configuration validation

use super::types::*;
use crate::error::{OasisError, Result};

/// Validate a device configuration
pub fn validate_config(config: &DeviceConfig) -> Result<()> {
    validate_device(&config.device)?;
    validate_connectivity(&config.connectivity, config.device.board.platform)?;
    validate_sensors(&config.sensors)?;
    validate_actuators(&config.actuators)?;
    validate_control_loops(&config.control_loops, &config.sensors, &config.actuators)?;
    Ok(())
}

fn validate_device(device: &Device) -> Result<()> {
    if device.id.is_empty() {
        return Err(OasisError::Validation("device.id is required".into()));
    }
    
    if device.name.is_empty() {
        return Err(OasisError::Validation("device.name is required".into()));
    }
    
    validate_board(&device.board)?;
    Ok(())
}

fn validate_board(board: &Board) -> Result<()> {
    let valid_mcu_boards = [
        "esp32_devkit", "esp32_c3", "esp32_s3",
        "arduino_uno", "arduino_mega", "arduino_nano",
        "teensy_40", "teensy_41",
        "stm32f103", "stm32f411",
    ];
    
    let valid_rpi_boards = [
        "rpi_zero_w", "rpi_zero_2w",
        "rpi_3b", "rpi_4b", "rpi_5",
    ];
    
    match board.platform {
        Platform::Mcu => {
            if !valid_mcu_boards.contains(&board.model.as_str()) {
                return Err(OasisError::UnsupportedBoard(format!(
                    "MCU board '{}' not supported. Valid options: {:?}",
                    board.model, valid_mcu_boards
                )));
            }
        }
        Platform::Rpi => {
            if !valid_rpi_boards.contains(&board.model.as_str()) {
                return Err(OasisError::UnsupportedBoard(format!(
                    "RPi board '{}' not supported. Valid options: {:?}",
                    board.model, valid_rpi_boards
                )));
            }
        }
    }
    
    Ok(())
}

fn validate_connectivity(conn: &Connectivity, platform: Platform) -> Result<()> {
    match conn.mode {
        ConnectivityMode::DirectMqtt | ConnectivityMode::Hybrid => {
            if conn.mqtt.is_none() {
                return Err(OasisError::Validation(
                    "mqtt configuration required for direct_mqtt or hybrid mode".into()
                ));
            }
            // WiFi required for MCU direct modes
            if platform == Platform::Mcu && conn.wifi.is_none() {
                return Err(OasisError::Validation(
                    "wifi configuration required for MCU direct_mqtt mode".into()
                ));
            }
        }
        ConnectivityMode::DirectHttps => {
            if conn.https.is_none() {
                return Err(OasisError::Validation(
                    "https configuration required for direct_https mode".into()
                ));
            }
            if platform == Platform::Mcu && conn.wifi.is_none() {
                return Err(OasisError::Validation(
                    "wifi configuration required for MCU direct_https mode".into()
                ));
            }
        }
        ConnectivityMode::SerialGateway => {
            if platform == Platform::Rpi {
                return Err(OasisError::Validation(
                    "serial_gateway mode is for MCU devices connecting to an RPi gateway".into()
                ));
            }
        }
    }
    
    Ok(())
}

fn validate_sensors(sensors: &[Sensor]) -> Result<()> {
    let mut names = std::collections::HashSet::new();
    
    for sensor in sensors {
        if sensor.name.is_empty() {
            return Err(OasisError::Validation("sensor name is required".into()));
        }
        
        if !names.insert(&sensor.name) {
            return Err(OasisError::Validation(format!(
                "duplicate sensor name: '{}'", sensor.name
            )));
        }
        
        // Validate pin configuration based on sensor type
        validate_sensor_pins(sensor)?;
        
        // Validate measurements
        if sensor.output.measurements.is_empty() {
            return Err(OasisError::Validation(format!(
                "sensor '{}' must have at least one measurement", sensor.name
            )));
        }
    }
    
    Ok(())
}

fn validate_sensor_pins(sensor: &Sensor) -> Result<()> {
    use SensorType::*;
    
    match sensor.sensor_type {
        Dht11 | Dht22 | Ds18b20 => {
            if sensor.pins.data.is_none() {
                return Err(OasisError::Validation(format!(
                    "sensor '{}' ({:?}) requires 'data' pin", 
                    sensor.name, sensor.sensor_type
                )));
            }
        }
        Hcsr04 => {
            if sensor.pins.trigger.is_none() || sensor.pins.echo.is_none() {
                return Err(OasisError::Validation(format!(
                    "sensor '{}' (hcsr04) requires 'trigger' and 'echo' pins",
                    sensor.name
                )));
            }
        }
        AdcRaw | CapacitiveMoisture | ResistiveMoisture | Photoresistor => {
            if sensor.pins.adc.is_none() {
                return Err(OasisError::Validation(format!(
                    "sensor '{}' requires 'adc' pin", sensor.name
                )));
            }
        }
        // I2C sensors use default pins or specified sda/scl
        Bme280 | Bme680 | Sht31 | Bh1750 | Tsl2561 | Veml7700 |
        Vl53l0x | Vl53l1x | Mpu6050 | Mpu9250 | Bno055 |
        Ccs811 | Sgp30 | Ina219 | I2cCustom => {
            // I2C pins are optional (use board defaults)
        }
        _ => {}
    }
    
    Ok(())
}

fn validate_actuators(actuators: &[Actuator]) -> Result<()> {
    let mut names = std::collections::HashSet::new();
    
    for actuator in actuators {
        if actuator.name.is_empty() {
            return Err(OasisError::Validation("actuator name is required".into()));
        }
        
        if !names.insert(&actuator.name) {
            return Err(OasisError::Validation(format!(
                "duplicate actuator name: '{}'", actuator.name
            )));
        }
        
        validate_actuator_pins(actuator)?;
    }
    
    Ok(())
}

fn validate_actuator_pins(actuator: &Actuator) -> Result<()> {
    use ActuatorType::*;
    
    match actuator.actuator_type {
        Relay | RelayNc | Led | Buzzer => {
            if actuator.pins.output.is_none() {
                return Err(OasisError::Validation(format!(
                    "actuator '{}' requires 'output' pin", actuator.name
                )));
            }
        }
        Pwm | Servo | DcMotor => {
            if actuator.pins.pwm.is_none() {
                return Err(OasisError::Validation(format!(
                    "actuator '{}' requires 'pwm' pin", actuator.name
                )));
            }
        }
        StepperA4988 | StepperDrv8825 | StepperTmc2209 => {
            if actuator.pins.step.is_none() || actuator.pins.dir.is_none() {
                return Err(OasisError::Validation(format!(
                    "actuator '{}' requires 'step' and 'dir' pins", actuator.name
                )));
            }
        }
        // I2C actuators use default pins
        Pca9685 | Mcp23017 => {}
        Rs485 | Modbus => {}
    }
    
    Ok(())
}

fn validate_control_loops(
    loops: &[ControlLoop],
    sensors: &[Sensor],
    actuators: &[Actuator],
) -> Result<()> {
    let sensor_names: std::collections::HashSet<_> = 
        sensors.iter().map(|s| &s.name).collect();
    let actuator_names: std::collections::HashSet<_> = 
        actuators.iter().map(|a| &a.name).collect();
    
    for ctrl in loops {
        // Validate input sensor exists
        if !sensor_names.contains(&ctrl.input.sensor) {
            return Err(OasisError::Validation(format!(
                "control loop '{}' references unknown sensor '{}'",
                ctrl.name, ctrl.input.sensor
            )));
        }
        
        // Validate output actuator exists
        if !actuator_names.contains(&ctrl.output.actuator) {
            return Err(OasisError::Validation(format!(
                "control loop '{}' references unknown actuator '{}'",
                ctrl.name, ctrl.output.actuator
            )));
        }
        
        // Validate measurement exists in sensor
        let sensor = sensors.iter().find(|s| s.name == ctrl.input.sensor).unwrap();
        let measurement_names: std::collections::HashSet<_> = 
            sensor.output.measurements.iter().map(|m| &m.name).collect();
        
        if !measurement_names.contains(&ctrl.input.measurement) {
            return Err(OasisError::Validation(format!(
                "control loop '{}' references unknown measurement '{}' in sensor '{}'",
                ctrl.name, ctrl.input.measurement, ctrl.input.sensor
            )));
        }
        
        // Validate loop-type-specific config
        match ctrl.loop_type {
            ControlLoopType::Threshold => {
                if ctrl.threshold.is_none() {
                    return Err(OasisError::Validation(format!(
                        "control loop '{}' is type 'threshold' but missing threshold config",
                        ctrl.name
                    )));
                }
            }
            ControlLoopType::Pid => {
                if ctrl.pid.is_none() {
                    return Err(OasisError::Validation(format!(
                        "control loop '{}' is type 'pid' but missing pid config",
                        ctrl.name
                    )));
                }
            }
            ControlLoopType::Schedule => {
                if ctrl.schedule.is_none() || ctrl.schedule.as_ref().unwrap().is_empty() {
                    return Err(OasisError::Validation(format!(
                        "control loop '{}' is type 'schedule' but missing schedule entries",
                        ctrl.name
                    )));
                }
            }
            ControlLoopType::StateMachine => {
                // TODO: State machine validation
            }
        }
    }
    
    Ok(())
}
