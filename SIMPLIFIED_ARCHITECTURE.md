# Oasis Firmware: Simplified Architecture (Final)

**Date:** November 23, 2024  
**Status:** Approved Architecture

---

## Overview

Pragmatic, ecosystem-leveraging approach to firmware management:
- **Raspberry Pi**: Rust launcher + app folder system
- **Arduino**: Compile-time sketch loading with intelligent menu system
- **Management**: Cross-platform Rust desktop app for flashing and deployment

---

## Raspberry Pi Architecture

### Stack
- **Launcher**: Rust + egui (~5MB binary)
- **Sandboxing**: Bubblewrap (optional)
- **Process Management**: systemd
- **App Format**: Folder with manifest.json + run.sh

### App Structure
```
/opt/oasis-apps/
├── greenhouse-control/
│   ├── manifest.json
│   ├── run.sh
│   ├── stop.sh (optional)
│   └── [app files]
└── timelapse-camera/
    └── ...
```

---

## Arduino Architecture (oasis-mcu)

### Key Innovation: **Compile-Time App Loading**

#### Folder Structure
```
oasis-mcu/
├── platforms/
│   ├── atmega328p_uno/
│   │   ├── greenhouse_sensors/
│   │   │   ├── app.ino
│   │   │   └── manifest.json
│   │   ├── led_controller/
│   │   └── timelapse_trigger/
│   ├── esp32_devkit/
│   │   ├── wifi_sensor_hub/
│   │   └── camera_trigger/
│   └── samd21_nano33iot/
├── core/
│   ├── menu_system.h
│   └── app_interface.h
└── build.py  # Compiler script
```

### Build System Logic

```python
# build.py - Intelligent compiler
def build_firmware(platform, selected_apps):
    """
    Compiles selected apps into single firmware.
    - If 1 app: Direct boot (no menu)
    - If 2+ apps: Include menu system
    - Fails if flash overflow
    """
    
    # Calculate sizes
    total_size = sum(get_app_size(app) for app in selected_apps)
    menu_size = get_menu_system_size() if len(selected_apps) > 1 else 0
    available = get_platform_flash_size(platform)
    
    if total_size + menu_size > available:
        raise FlashOverflowError(f"Apps require {total_size}KB, only {available}KB available")
    
    # Generate main.ino
    if len(selected_apps) == 1:
        generate_single_app_main(selected_apps[0])
    else:
        generate_menu_main(selected_apps)
    
    # Compile
    compile_arduino(platform)
```

### Menu System (Multi-App Mode)

```cpp
// Auto-generated main.ino for multi-app
#include "core/menu_system.h"
#include "platforms/atmega328p_uno/greenhouse_sensors/app.h"
#include "platforms/atmega328p_uno/led_controller/app.h"

OasisMenuSystem menu;

void setup() {
    Serial.begin(9600);
    menu.registerApp("Greenhouse", greenhouse_setup, greenhouse_loop, greenhouse_cleanup);
    menu.registerApp("LED Control", led_setup, led_loop, led_cleanup);
    menu.begin();
}

void loop() {
    menu.update();
}
```

### Single-App Mode

```cpp
// Auto-generated main.ino for single app
#include "platforms/atmega328p_uno/greenhouse_sensors/app.h"

void setup() {
    greenhouse_setup();
}

void loop() {
    greenhouse_loop();
}
```

---

## Oasis Manager: Cross-Platform Desktop App

### Purpose
Single desktop application for managing entire Oasis ecosystem:
- Download apps from repository
- Flash Raspberry Pi SD cards
- Flash Arduino microcontrollers
- Configure devices
- Monitor deployments

### Technology Stack
- **Language**: Rust
- **UI Framework**: egui (same as Pi launcher - code reuse!)
- **SD Card Flashing**: `dd` wrapper (Linux/macOS), Win32 API (Windows)
- **Arduino Flashing**: arduino-cli integration
- **Networking**: reqwest for app downloads

### Features

#### 1. App Repository Browser
```rust
struct AppRepository {
    rpi_apps: Vec<RpiApp>,
    arduino_apps: Vec<ArduinoApp>,
}

impl AppRepository {
    fn fetch_from_remote(&self) -> Result<()> {
        // Download app catalog from GitHub/S3
    }
    
    fn download_app(&self, app_id: &str, dest: &Path) -> Result<()> {
        // Download app package
    }
}
```

#### 2. SD Card Manager
```rust
struct SdCardManager {
    fn list_devices(&self) -> Vec<BlockDevice>,
    fn flash_image(&self, device: &str, image: &Path) -> Result<()>,
    fn install_apps(&self, device: &str, apps: Vec<&Path>) -> Result<()>,
}
```

#### 3. Arduino Flasher
```rust
struct ArduinoFlasher {
    fn detect_boards(&self) -> Vec<ArduinoBoard>,
    fn compile_apps(&self, platform: &str, apps: Vec<&str>) -> Result<PathBuf>,
    fn flash_firmware(&self, port: &str, firmware: &Path) -> Result<()>,
}
```

### UI Mockup
```
┌─────────────────────────────────────────────┐
│ Oasis Manager                          [_][□][X] │
├─────────────────────────────────────────────┤
│ [Raspberry Pi] [Arduino] [Repository]       │
├─────────────────────────────────────────────┤
│                                             │
│  Raspberry Pi SD Card                       │
│  ┌─────────────────────────────────────┐   │
│  │ Device: /dev/disk2 (32GB)           │   │
│  │ Status: Ready                       │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  Selected Apps:                             │
│  ☑ Greenhouse Control v1.2                 │
│  ☑ Timelapse Camera v2.0                   │
│  ☐ Environmental Monitor v1.5              │
│                                             │
│  [Download Apps] [Flash SD Card]           │
│                                             │
│  Arduino Uno (atmega328p)                  │
│  ┌─────────────────────────────────────┐   │
│  │ Port: /dev/ttyUSB0                  │   │
│  │ Flash: 32KB (18KB used)             │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  Selected Sketches:                         │
│  ☑ Greenhouse Sensors                      │
│  ☑ LED Controller                          │
│                                             │
│  [Compile] [Flash Arduino]                 │
│                                             │
└─────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### Phase 1: Core Systems (Week 1-2)
- [ ] Raspberry Pi launcher (Rust + egui)
- [ ] Arduino menu system (C++)
- [ ] Build script for Arduino (Python)

### Phase 2: Oasis Manager (Week 3-4)
- [ ] Desktop app skeleton (Rust + egui)
- [ ] SD card detection and flashing
- [ ] Arduino compilation and flashing
- [ ] App repository integration

### Phase 3: Ecosystem (Week 5-6)
- [ ] Create 5+ example apps (RPi)
- [ ] Create 5+ example sketches (Arduino)
- [ ] Documentation
- [ ] Testing across platforms

---

## File Structure

```
oasis-firmware/
├── oasis-rpi/              # Raspberry Pi launcher
│   ├── Cargo.toml
│   ├── src/
│   │   ├── main.rs         # egui launcher
│   │   ├── app_scanner.rs
│   │   └── process_manager.rs
│   └── systemd/
│       └── oasis-launcher.service
│
├── oasis-mcu/              # Arduino apps
│   ├── platforms/
│   │   ├── atmega328p_uno/
│   │   ├── esp32_devkit/
│   │   └── samd21_nano33iot/
│   ├── core/
│   │   ├── menu_system.h
│   │   └── app_interface.h
│   └── build.py            # Compiler script
│
├── oasis-manager/          # Desktop management app
│   ├── Cargo.toml
│   ├── src/
│   │   ├── main.rs
│   │   ├── ui/
│   │   ├── sd_card/
│   │   ├── arduino/
│   │   └── repository/
│   └── README.md
│
└── apps/                   # App repository
    ├── rpi/
    │   ├── greenhouse-control/
    │   └── timelapse-camera/
    └── arduino/
        ├── greenhouse-sensors/
        └── led-controller/
```

---

## Next Steps

1. **Create project structure** (this document)
2. **Implement RPi launcher** (Rust + egui)
3. **Implement Arduino build system** (Python script)
4. **Implement Oasis Manager** (Rust desktop app)
5. **Create example apps**
6. **Documentation for future agents**
