//! Code generation for MCU and RPi targets
//!
//! This module generates Rust source code from validated device configurations.

mod mcu;
mod rpi;
mod templates;

use crate::config::{DeviceConfig, Platform};
use crate::error::Result;
use std::path::Path;

/// Generate firmware source code for a device configuration
pub fn generate(config: &DeviceConfig, output_dir: &Path) -> Result<()> {
    match config.device.board.platform {
        Platform::Mcu => mcu::generate(config, output_dir),
        Platform::Rpi => rpi::generate(config, output_dir),
    }
}

/// Supported target information
#[derive(Debug, Clone)]
pub struct TargetInfo {
    pub platform: Platform,
    pub board: String,
    pub rust_target: String,
    pub features: Vec<String>,
}

impl TargetInfo {
    pub fn from_config(config: &DeviceConfig) -> Self {
        let (rust_target, features) = match config.device.board.model.as_str() {
            // ESP32 variants
            "esp32_devkit" => ("xtensa-esp32-none-elf".into(), vec!["esp32".into()]),
            "esp32_c3" => ("riscv32imc-unknown-none-elf".into(), vec!["esp32c3".into()]),
            "esp32_s3" => ("xtensa-esp32s3-none-elf".into(), vec!["esp32s3".into()]),
            
            // STM32 variants
            "stm32f103" => ("thumbv7m-none-eabi".into(), vec!["stm32f103".into()]),
            "stm32f411" => ("thumbv7em-none-eabihf".into(), vec!["stm32f411".into()]),
            
            // Teensy (ARM Cortex-M7)
            "teensy_40" | "teensy_41" => ("thumbv7em-none-eabihf".into(), vec!["teensy4".into()]),
            
            // RPi variants (native compilation or cross-compile)
            "rpi_zero_w" | "rpi_zero_2w" => ("aarch64-unknown-linux-gnu".into(), vec!["rpi_zero".into()]),
            "rpi_3b" => ("aarch64-unknown-linux-gnu".into(), vec!["rpi3".into()]),
            "rpi_4b" | "rpi_5" => ("aarch64-unknown-linux-gnu".into(), vec!["rpi4".into()]),
            
            // Fallback
            _ => ("".into(), vec![]),
        };
        
        Self {
            platform: config.device.board.platform,
            board: config.device.board.model.clone(),
            rust_target,
            features,
        }
    }
}
