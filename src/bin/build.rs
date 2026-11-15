//! oasis-build CLI
//!
//! Generate firmware from device.yaml configurations

use anyhow::Result;
use clap::{Parser, Subcommand};
use oasis_core::config;
use oasis_core::codegen;
use oasis_core::simulation;
use std::path::PathBuf;
use tracing::{info, Level};
use tracing_subscriber::EnvFilter;

#[derive(Parser)]
#[command(name = "oasis-build")]
#[command(about = "Generate Oasis firmware from device configurations")]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
    
    /// Enable verbose logging
    #[arg(short, long, global = true)]
    verbose: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Generate firmware from a device.yaml file
    Generate {
        /// Path to device.yaml configuration
        #[arg(short, long)]
        config: PathBuf,
        
        /// Output directory for generated firmware
        #[arg(short, long)]
        output: PathBuf,
        
        /// Substitute environment variables in config
        #[arg(short, long, default_value = "false")]
        env_subst: bool,
        
        /// Generate simulation configs (Wokwi for ESP32, mock GPIO for RPi)
        #[arg(long, default_value = "false")]
        with_simulation: bool,
    },
    
    /// Validate a device.yaml configuration without generating
    Validate {
        /// Path to device.yaml configuration
        #[arg(short, long)]
        config: PathBuf,
    },
    
    /// Show information about a device configuration
    Info {
        /// Path to device.yaml configuration
        #[arg(short, long)]
        config: PathBuf,
    },
    
    /// List supported boards
    Boards,
    
    /// List supported sensor types
    Sensors,
    
    /// List supported actuator types
    Actuators,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    
    // Initialize logging
    let filter = if cli.verbose {
        EnvFilter::from_default_env().add_directive(Level::DEBUG.into())
    } else {
        EnvFilter::from_default_env().add_directive(Level::INFO.into())
    };
    
    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .init();
    
    match cli.command {
        Commands::Generate { config: config_path, output, env_subst, with_simulation } => {
            info!("Loading configuration from {:?}", config_path);
            
            let device_config = if env_subst {
                config::load_config_with_env(&config_path)?
            } else {
                config::load_config(&config_path)?
            };
            
            info!("Generating firmware for device: {}", device_config.device.id);
            info!("Platform: {:?}, Board: {}", 
                device_config.device.board.platform,
                device_config.device.board.model);
            
            // Create output directory
            std::fs::create_dir_all(&output)?;
            
            // Generate firmware
            codegen::generate(&device_config, &output)?;
            
            // Generate simulation configs if requested
            if with_simulation {
                info!("Generating simulation configuration...");
                simulation::generate_simulation(&device_config, &output)?;
                info!("✓ Simulation config generated (wokwi.toml, diagram.json)");
            }
            
            info!("✓ Firmware generated at {:?}", output);
            
            // Print next steps
            println!("\nNext steps:");
            println!("  cd {:?}", output);
            println!("  cargo build --release");
            if with_simulation {
                println!("\nSimulation:");
                println!("  # Open in VS Code with Wokwi extension, or:");
                println!("  wokwi-cli --config wokwi.toml");
            }
        }
        
        Commands::Validate { config: config_path } => {
            info!("Validating configuration: {:?}", config_path);
            
            match config::load_config(&config_path) {
                Ok(device_config) => {
                    println!("✓ Configuration is valid");
                    println!("  Device ID: {}", device_config.device.id);
                    println!("  Platform: {:?}", device_config.device.board.platform);
                    println!("  Board: {}", device_config.device.board.model);
                    println!("  Sensors: {}", device_config.sensors.len());
                    println!("  Actuators: {}", device_config.actuators.len());
                    println!("  Control loops: {}", device_config.control_loops.len());
                }
                Err(e) => {
                    eprintln!("✗ Configuration invalid: {}", e);
                    std::process::exit(1);
                }
            }
        }
        
        Commands::Info { config: config_path } => {
            let device_config = config::load_config(&config_path)?;
            
            println!("Device Configuration");
            println!("====================");
            println!();
            println!("Device:");
            println!("  ID: {}", device_config.device.id);
            println!("  Name: {}", device_config.device.name);
            println!("  Platform: {:?}", device_config.device.board.platform);
            println!("  Board: {}", device_config.device.board.model);
            println!();
            println!("Connectivity:");
            println!("  Mode: {:?}", device_config.connectivity.mode);
            if let Some(mqtt) = &device_config.connectivity.mqtt {
                println!("  MQTT: {}:{}", mqtt.broker, mqtt.port);
            }
            if let Some(https) = &device_config.connectivity.https {
                println!("  HTTPS: {}", https.endpoint);
            }
            println!();
            println!("Sensors ({}):", device_config.sensors.len());
            for sensor in &device_config.sensors {
                println!("  - {} ({:?})", sensor.name, sensor.sensor_type);
                for m in &sensor.output.measurements {
                    println!("      → {} ({})", m.name, m.unit);
                }
            }
            println!();
            println!("Actuators ({}):", device_config.actuators.len());
            for actuator in &device_config.actuators {
                println!("  - {} ({:?})", actuator.name, actuator.actuator_type);
            }
            println!();
            println!("Control Loops ({}):", device_config.control_loops.len());
            for ctrl in &device_config.control_loops {
                println!("  - {} ({:?}): {} → {}", 
                    ctrl.name, ctrl.loop_type,
                    ctrl.input.sensor, ctrl.output.actuator);
            }
        }
        
        Commands::Boards => {
            println!("Supported Boards");
            println!("================");
            println!();
            println!("MCU Platform:");
            println!("  esp32_devkit   - ESP32 DevKit V1");
            println!("  esp32_c3       - ESP32-C3 (RISC-V)");
            println!("  esp32_s3       - ESP32-S3");
            println!("  arduino_uno    - Arduino Uno (ATmega328P)");
            println!("  arduino_mega   - Arduino Mega 2560");
            println!("  arduino_nano   - Arduino Nano");
            println!("  teensy_40      - Teensy 4.0");
            println!("  teensy_41      - Teensy 4.1");
            println!("  stm32f103      - STM32F103 (Blue Pill)");
            println!("  stm32f411      - STM32F411 (Black Pill)");
            println!();
            println!("RPi Platform:");
            println!("  rpi_zero_w     - Raspberry Pi Zero W");
            println!("  rpi_zero_2w    - Raspberry Pi Zero 2 W");
            println!("  rpi_3b         - Raspberry Pi 3B/3B+");
            println!("  rpi_4b         - Raspberry Pi 4B");
            println!("  rpi_5          - Raspberry Pi 5");
        }
        
        Commands::Sensors => {
            println!("Supported Sensor Types");
            println!("======================");
            println!();
            println!("Temperature/Humidity:");
            println!("  dht11, dht22, bme280, bme680, sht31, ds18b20");
            println!();
            println!("Light:");
            println!("  bh1750, tsl2561, veml7700, photoresistor");
            println!();
            println!("Moisture:");
            println!("  capacitive_moisture, resistive_moisture");
            println!();
            println!("Distance:");
            println!("  hcsr04, vl53l0x, vl53l1x");
            println!();
            println!("Motion/Orientation:");
            println!("  mpu6050, mpu9250, bno055, pir");
            println!();
            println!("Gas/Air Quality:");
            println!("  mq2, mq135, ccs811, sgp30");
            println!();
            println!("Current/Voltage:");
            println!("  ina219, acs712, voltage_divider");
            println!();
            println!("Weight:");
            println!("  hx711");
            println!();
            println!("Camera:");
            println!("  esp_cam, rpi_camera");
            println!();
            println!("Generic:");
            println!("  adc_raw, i2c_custom");
        }
        
        Commands::Actuators => {
            println!("Supported Actuator Types");
            println!("========================");
            println!();
            println!("Digital Output:");
            println!("  relay, relay_nc, led, buzzer");
            println!();
            println!("PWM Output:");
            println!("  pwm, servo, dc_motor");
            println!();
            println!("Stepper Motors:");
            println!("  stepper_a4988, stepper_drv8825, stepper_tmc2209");
            println!();
            println!("I2C Expanders:");
            println!("  pca9685, mcp23017");
            println!();
            println!("Communication:");
            println!("  rs485, modbus");
        }
    }
    
    Ok(())
}
