# Oasis Studio

Desktop application for Oasis firmware development, simulation, and deployment.

## Features

- **Configure**: Visual YAML editor with live validation
- **Simulate**: Wokwi integration (ESP32) and mock GPIO (RPi)
- **Hardware**: KiCAD integration for PCB design
- **Deploy**: Build and flash to USB, SSH, or OTA
- **Monitor**: Live MQTT telemetry viewer

## Requirements

- **Rust 1.85+** (required for egui and transitive dependencies)
- macOS, Linux, or Windows

## Building

```bash
# Update Rust to latest
rustup update stable

# Build release
cargo build --release

# Run
cargo run --release
```

## Architecture

```
desktop/
├── src/
│   ├── main.rs          # Entry point
│   ├── app.rs           # Main application struct
│   ├── state.rs         # Application state
│   ├── mqtt_client.rs   # MQTT for live monitoring
│   └── panels/
│       ├── configure.rs # YAML editor tab
│       ├── simulate.rs  # Simulation tab
│       ├── hardware.rs  # KiCAD integration tab
│       ├── deploy.rs    # Build/flash tab
│       └── monitor.rs   # MQTT viewer tab
```

## Screenshots

(Coming soon)
