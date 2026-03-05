//! Error types for oasis-core

use thiserror::Error;

#[derive(Error, Debug)]
pub enum OasisError {
    #[error("Configuration error: {0}")]
    Config(String),

    #[error("YAML parsing error: {0}")]
    YamlParse(#[from] serde_yaml::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Code generation error: {0}")]
    CodeGen(String),

    #[error("Unsupported board: {0}")]
    UnsupportedBoard(String),

    #[error("Unsupported sensor type: {0}")]
    UnsupportedSensor(String),

    #[error("Unsupported actuator type: {0}")]
    UnsupportedActuator(String),

    #[error("Validation error: {0}")]
    Validation(String),

    #[error("Environment variable not found: {0}")]
    EnvVar(String),

    #[error("Template error: {0}")]
    Template(String),
}

pub type Result<T> = std::result::Result<T, OasisError>;
