//! Oasis Core - Types and utilities for firmware generation
//!
//! This crate provides:
//! - Device configuration types (parsed from YAML)
//! - Code generation for MCU (embedded Rust) and RPi targets
//! - Hardware driver templates for sensors and actuators
//! - Simulation config generation (Wokwi, mock GPIO)
//! - Build pipeline orchestration

pub mod config;
pub mod codegen;
pub mod drivers;
pub mod error;
pub mod simulation;

pub use config::DeviceConfig;
pub use error::OasisError;
