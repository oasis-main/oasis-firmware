//! Device configuration types
//!
//! These types are deserialized from device.yaml files and validated
//! before code generation.

mod types;
mod validation;

pub use types::*;
pub use validation::validate_config;

use crate::error::Result;
use std::path::Path;

/// Load and parse a device configuration from a YAML file
pub fn load_config(path: &Path) -> Result<DeviceConfig> {
    let content = std::fs::read_to_string(path)?;
    let config: DeviceConfig = serde_yaml::from_str(&content)?;
    validate_config(&config)?;
    Ok(config)
}

/// Load config with environment variable substitution
pub fn load_config_with_env(path: &Path) -> Result<DeviceConfig> {
    let content = std::fs::read_to_string(path)?;
    
    // Substitute ${ENV_VAR} patterns
    let expanded = substitute_env_vars(&content)?;
    
    let config: DeviceConfig = serde_yaml::from_str(&expanded)?;
    validate_config(&config)?;
    Ok(config)
}

fn substitute_env_vars(content: &str) -> Result<String> {
    let mut result = content.to_string();
    
    // Find all ${VAR} patterns
    let re = regex::Regex::new(r"\$\{([^}]+)\}").unwrap();
    
    for cap in re.captures_iter(content) {
        let full_match = &cap[0];
        let var_name = &cap[1];
        
        match std::env::var(var_name) {
            Ok(value) => {
                result = result.replace(full_match, &value);
            }
            Err(_) => {
                // Leave as-is for runtime substitution (RPi)
                // or error for compile-time (MCU)
                tracing::warn!("Environment variable {} not found", var_name);
            }
        }
    }
    
    Ok(result)
}
