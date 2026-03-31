# Oasis Manager: Cross-Platform Desktop Application

**Purpose**: Unified tool for managing Raspberry Pi and Arduino deployments

---

## Overview

Single Rust desktop application that:
- Downloads apps from repository
- Flashes Raspberry Pi SD cards
- Compiles and flashes Arduino firmware
- Manages device configurations
- Monitors deployments

**Platforms**: macOS, Windows, Linux

---

## Technology Stack

- **Language**: Rust 1.70+
- **UI Framework**: egui 0.24+ (same as RPi launcher)
- **HTTP Client**: reqwest (app downloads)
- **SD Card**: Platform-specific APIs
- **Arduino**: arduino-cli wrapper
- **Serialization**: serde_json

---

## Features

### 1. App Repository Browser
- Fetch app catalog from GitHub/S3
- Search and filter apps
- View app details and screenshots
- Download app packages

### 2. Raspberry Pi Manager
- Detect SD cards
- Flash base OS image
- Install selected apps to `/opt/oasis-apps/`
- Configure WiFi and settings
- Eject safely

### 3. Arduino Manager
- Detect connected boards
- Select platform and apps
- Compile firmware (via build.py)
- Flash to board
- Monitor serial output

### 4. Configuration Editor
- Edit app manifests
- Configure hardware pins
- Set network credentials
- Manage device settings

---

## Architecture

```
oasis-manager/
├── Cargo.toml
├── src/
│   ├── main.rs              # Entry point
│   ├── ui/
│   │   ├── mod.rs
│   │   ├── home.rs          # Home screen
│   │   ├── rpi_tab.rs       # RPi management
│   │   ├── arduino_tab.rs   # Arduino management
│   │   └── repository_tab.rs # App browser
│   ├── repository/
│   │   ├── mod.rs
│   │   ├── client.rs        # HTTP client
│   │   └── catalog.rs       # App catalog
│   ├── sd_card/
│   │   ├── mod.rs
│   │   ├── detector.rs      # Detect SD cards
│   │   ├── flasher.rs       # Flash images
│   │   └── mounter.rs       # Mount/unmount
│   ├── arduino/
│   │   ├── mod.rs
│   │   ├── detector.rs      # Detect boards
│   │   ├── compiler.rs      # Build firmware
│   │   └── flasher.rs       # Upload firmware
│   └── config/
│       ├── mod.rs
│       └── settings.rs      # App settings
├── resources/
│   ├── icon.png
│   └── base_images/         # Base OS images
└── README.md
```

---

## UI Design

### Main Window

```
┌──────────────────────────────────────────────────────┐
│ Oasis Manager                          [_][□][X]     │
├──────────────────────────────────────────────────────┤
│ [🏠 Home] [🥧 Raspberry Pi] [🔧 Arduino] [📦 Apps]  │
├──────────────────────────────────────────────────────┤
│                                                      │
│  [Content area based on selected tab]               │
│                                                      │
│                                                      │
│                                                      │
│                                                      │
│                                                      │
│                                                      │
│                                                      │
│                                                      │
│                                                      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Raspberry Pi Tab

```
┌──────────────────────────────────────────────────────┐
│ SD Card Device                                       │
│ ┌──────────────────────────────────────────────────┐ │
│ │ Device: /dev/disk2                               │ │
│ │ Size: 32GB                                       │ │
│ │ Status: ● Ready                                  │ │
│ │ [Refresh Devices]                                │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ Base Image                                           │
│ ┌──────────────────────────────────────────────────┐ │
│ │ ○ Raspberry Pi OS Lite (Recommended)             │ │
│ │ ○ Raspberry Pi OS Desktop                        │ │
│ │ ○ Custom Image: [Browse...]                      │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ Apps to Install                                      │
│ ┌──────────────────────────────────────────────────┐ │
│ │ ☑ Greenhouse Control v1.2                        │ │
│ │ ☑ Timelapse Camera v2.0                          │ │
│ │ ☐ Environmental Monitor v1.5                     │ │
│ │ ☐ Irrigation Controller v1.0                     │ │
│ │                                                   │ │
│ │ [+ Add from Repository]                          │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ Configuration (Optional)                             │
│ ┌──────────────────────────────────────────────────┐ │
│ │ WiFi SSID: [________________]                    │ │
│ │ WiFi Password: [________________]                │ │
│ │ Hostname: [oasis-pi]                             │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ [Flash SD Card]                                      │
│ Progress: ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░ 50%                  │
└──────────────────────────────────────────────────────┘
```

### Arduino Tab

```
┌──────────────────────────────────────────────────────┐
│ Arduino Board                                        │
│ ┌──────────────────────────────────────────────────┐ │
│ │ Port: /dev/ttyUSB0                               │ │
│ │ Board: Arduino Uno (atmega328p)                  │ │
│ │ Status: ● Connected                              │ │
│ │ [Refresh Ports]                                  │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ Platform                                             │
│ ┌──────────────────────────────────────────────────┐ │
│ │ ● atmega328p_uno (32KB flash)                    │ │
│ │ ○ esp32_devkit (4MB flash)                       │ │
│ │ ○ samd21_nano33iot (256KB flash)                 │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ Apps to Compile                                      │
│ ┌──────────────────────────────────────────────────┐ │
│ │ ☑ Greenhouse Sensors                             │ │
│ │ ☑ LED Controller                                 │ │
│ │ ☐ Timelapse Trigger                              │ │
│ │                                                   │ │
│ │ Flash Usage: 18KB / 32KB (56%)                   │ │
│ │ RAM Usage: 1.2KB / 2KB (60%)                     │ │
│ │                                                   │ │
│ │ [+ Add from Repository]                          │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ Build Mode                                           │
│ ┌──────────────────────────────────────────────────┐ │
│ │ ● Multi-app with menu (2KB overhead)             │ │
│ │ ○ Single-app direct boot (no menu)               │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ [Compile & Flash]                                    │
│ Build log: Compiling... ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░ 50%    │
└──────────────────────────────────────────────────────┘
```

### Repository Tab

```
┌──────────────────────────────────────────────────────┐
│ App Repository                                       │
│ ┌──────────────────────────────────────────────────┐ │
│ │ Search: [greenhouse________] [🔍]                │ │
│ │ Filter: [All ▼] [Raspberry Pi ▼] [Arduino ▼]    │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ Available Apps                                       │
│ ┌──────────────────────────────────────────────────┐ │
│ │ ┌────────────────────────────────────────────┐   │ │
│ │ │ 🌱 Greenhouse Control v1.2                 │   │ │
│ │ │ Platform: Raspberry Pi                     │   │ │
│ │ │ Automated climate control for greenhouses  │   │ │
│ │ │ ⭐⭐⭐⭐⭐ (42 reviews)                        │   │ │
│ │ │ [Download] [Details]                       │   │ │
│ │ └────────────────────────────────────────────┘   │ │
│ │                                                   │ │
│ │ ┌────────────────────────────────────────────┐   │ │
│ │ │ 📷 Timelapse Camera v2.0                   │   │ │
│ │ │ Platform: Raspberry Pi                     │   │ │
│ │ │ Create beautiful timelapse videos          │   │ │
│ │ │ ⭐⭐⭐⭐☆ (28 reviews)                        │   │ │
│ │ │ [Download] [Details]                       │   │ │
│ │ └────────────────────────────────────────────┘   │ │
│ │                                                   │ │
│ │ ┌────────────────────────────────────────────┐   │ │
│ │ │ 🌡️ Greenhouse Sensors v1.0                 │   │ │
│ │ │ Platform: Arduino (atmega328p_uno)         │   │ │
│ │ │ DHT22 + soil moisture monitoring           │   │ │
│ │ │ ⭐⭐⭐⭐⭐ (35 reviews)                        │   │ │
│ │ │ [Download] [Details]                       │   │ │
│ │ └────────────────────────────────────────────┘   │ │
│ └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## Implementation

### Cargo.toml

```toml
[package]
name = "oasis-manager"
version = "0.1.0"
edition = "2021"

[dependencies]
eframe = "0.24"
egui = "0.24"
reqwest = { version = "0.11", features = ["blocking", "json"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
anyhow = "1.0"
tokio = { version = "1", features = ["full"] }

[target.'cfg(target_os = "macos")'.dependencies]
core-foundation = "0.9"
io-kit-sys = "0.4"

[target.'cfg(target_os = "windows")'.dependencies]
winapi = { version = "0.3", features = ["winioctl", "fileapi"] }

[target.'cfg(target_os = "linux")'.dependencies]
libc = "0.2"
```

### main.rs

```rust
use eframe::egui;
use std::sync::Arc;
use tokio::sync::Mutex;

mod ui;
mod repository;
mod sd_card;
mod arduino;
mod config;

use ui::{HomeTab, RpiTab, ArduinoTab, RepositoryTab};

#[derive(Default)]
struct OasisManager {
    active_tab: Tab,
    home_tab: HomeTab,
    rpi_tab: RpiTab,
    arduino_tab: ArduinoTab,
    repository_tab: RepositoryTab,
}

#[derive(Default, PartialEq)]
enum Tab {
    #[default]
    Home,
    RaspberryPi,
    Arduino,
    Repository,
}

impl eframe::App for OasisManager {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        egui::TopBottomPanel::top("top_panel").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.heading("Oasis Manager");
                ui.separator();
                
                ui.selectable_value(&mut self.active_tab, Tab::Home, "🏠 Home");
                ui.selectable_value(&mut self.active_tab, Tab::RaspberryPi, "🥧 Raspberry Pi");
                ui.selectable_value(&mut self.active_tab, Tab::Arduino, "🔧 Arduino");
                ui.selectable_value(&mut self.active_tab, Tab::Repository, "📦 Apps");
            });
        });

        egui::CentralPanel::default().show(ctx, |ui| {
            match self.active_tab {
                Tab::Home => self.home_tab.show(ui),
                Tab::RaspberryPi => self.rpi_tab.show(ui),
                Tab::Arduino => self.arduino_tab.show(ui),
                Tab::Repository => self.repository_tab.show(ui),
            }
        });
    }
}

fn main() -> Result<(), eframe::Error> {
    let options = eframe::NativeOptions {
        initial_window_size: Some(egui::vec2(800.0, 600.0)),
        ..Default::default()
    };
    
    eframe::run_native(
        "Oasis Manager",
        options,
        Box::new(|_cc| Box::<OasisManager>::default()),
    )
}
```

### SD Card Detection (macOS)

```rust
// src/sd_card/detector.rs

#[cfg(target_os = "macos")]
pub fn detect_sd_cards() -> Vec<SdCard> {
    use std::process::Command;
    
    let output = Command::new("diskutil")
        .arg("list")
        .output()
        .expect("Failed to run diskutil");
    
    let stdout = String::from_utf8_lossy(&output.stdout);
    
    // Parse diskutil output
    // Look for removable media
    // Return list of SdCard structs
    
    vec![]
}

#[cfg(target_os = "linux")]
pub fn detect_sd_cards() -> Vec<SdCard> {
    use std::process::Command;
    
    let output = Command::new("lsblk")
        .args(&["-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT"])
        .output()
        .expect("Failed to run lsblk");
    
    // Parse JSON output
    // Filter for removable devices
    
    vec![]
}

#[cfg(target_os = "windows")]
pub fn detect_sd_cards() -> Vec<SdCard> {
    // Use WMI or Win32 API
    vec![]
}

pub struct SdCard {
    pub device: String,
    pub size_bytes: u64,
    pub mounted: bool,
    pub mount_point: Option<String>,
}
```

### Arduino Compiler

```rust
// src/arduino/compiler.rs

use std::process::Command;
use std::path::PathBuf;
use anyhow::Result;

pub struct ArduinoCompiler {
    build_script: PathBuf,
}

impl ArduinoCompiler {
    pub fn new() -> Self {
        Self {
            build_script: PathBuf::from("../oasis-mcu/build.py"),
        }
    }
    
    pub fn compile(&self, platform: &str, apps: &[String]) -> Result<PathBuf> {
        let apps_str = apps.join(",");
        
        let output = Command::new("python3")
            .arg(&self.build_script)
            .arg("--platform").arg(platform)
            .arg("--apps").arg(&apps_str)
            .output()?;
        
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            anyhow::bail!("Compilation failed: {}", stderr);
        }
        
        Ok(PathBuf::from(format!("../oasis-mcu/build/{}/main.ino.hex", platform)))
    }
    
    pub fn flash(&self, port: &str, hex_file: &PathBuf) -> Result<()> {
        let output = Command::new("arduino-cli")
            .arg("upload")
            .arg("--port").arg(port)
            .arg("--input-file").arg(hex_file)
            .output()?;
        
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            anyhow::bail!("Flashing failed: {}", stderr);
        }
        
        Ok(())
    }
}
```

---

## Build Instructions

### Development

```bash
cd oasis-manager
cargo run
```

### Release Build

```bash
# macOS
cargo build --release
# Binary: target/release/oasis-manager

# Windows
cargo build --release --target x86_64-pc-windows-gnu
# Binary: target/x86_64-pc-windows-gnu/release/oasis-manager.exe

# Linux
cargo build --release
# Binary: target/release/oasis-manager
```

### Distribution

```bash
# macOS App Bundle
cargo bundle --release

# Windows Installer
cargo wix

# Linux AppImage
cargo appimage
```

---

## Testing

### Unit Tests

```bash
cargo test
```

### Integration Tests

```bash
# Test SD card detection
cargo test --test sd_card_detection

# Test Arduino compilation
cargo test --test arduino_compile

# Test repository client
cargo test --test repository_client
```

---

## Future Enhancements

- [ ] Device monitoring dashboard
- [ ] OTA update support
- [ ] Multi-device management
- [ ] Cloud sync for configurations
- [ ] App development tools
- [ ] Serial monitor integration
- [ ] Log viewer
- [ ] Backup/restore functionality

---

**Last Updated**: November 23, 2024
