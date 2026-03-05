//! Simulation configuration generation
//!
//! Generates configs for hardware simulators:
//! - Wokwi (ESP32, Arduino) - Primary
//! - Renode (STM32, multi-device)
//! - QEMU (ARM Linux for RPi)

mod wokwi;

use crate::config::{DeviceConfig, Platform};
use crate::error::Result;
use std::path::Path;

pub use wokwi::WokwiConfig;

/// Generate simulation configuration files alongside firmware
pub fn generate_simulation(config: &DeviceConfig, output_dir: &Path) -> Result<()> {
    match config.device.board.platform {
        Platform::Mcu => {
            // ESP32 and Arduino use Wokwi
            if is_wokwi_supported(&config.device.board.model) {
                wokwi::generate(config, output_dir)?;
            }
            // STM32 could use Renode (future)
        }
        Platform::Rpi => {
            // RPi simulation is more complex - typically use QEMU
            // or just run natively on dev machine with mocked GPIO
            generate_mock_gpio_config(config, output_dir)?;
        }
    }
    Ok(())
}

fn is_wokwi_supported(board: &str) -> bool {
    matches!(board, 
        "esp32_devkit" | "esp32_c3" | "esp32_s3" |
        "arduino_uno" | "arduino_mega" | "arduino_nano"
    )
}

fn generate_mock_gpio_config(config: &DeviceConfig, output_dir: &Path) -> Result<()> {
    // Generate a mock GPIO configuration for RPi testing on desktop
    let content = format!(r#"# Mock GPIO Configuration for {}
# Use with rppal's mock feature or gpiozero's mock pins

[mock]
enabled = true

[pins]
{}

[sensors]
{}

[actuators]
{}
"#,
        config.device.id,
        config.sensors.iter()
            .filter_map(|s| s.pins.data.map(|p| format!("{} = {{ mode = \"input\", initial = 0 }}", p)))
            .collect::<Vec<_>>()
            .join("\n"),
        config.sensors.iter()
            .map(|s| format!("{} = {{ type = \"{:?}\", mock_value = 25.0 }}", s.name, s.sensor_type))
            .collect::<Vec<_>>()
            .join("\n"),
        config.actuators.iter()
            .map(|a| format!("{} = {{ type = \"{:?}\", initial = \"off\" }}", a.name, a.actuator_type))
            .collect::<Vec<_>>()
            .join("\n"),
    );
    
    std::fs::write(output_dir.join("mock_gpio.toml"), content)?;
    Ok(())
}
