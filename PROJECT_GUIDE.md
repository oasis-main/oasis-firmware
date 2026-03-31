# Oasis Firmware Project Guide

**For Future AI Agents and Developers**

---

## Project Vision

Create a simple, modular firmware ecosystem for IoT devices:
- **Raspberry Pi**: App launcher with visual process manager
- **Arduino**: Compile-time multi-app system with optional menu
- **Management**: Cross-platform desktop app for deployment

---

## Core Principles

1. **Simplicity Over Complexity**: Use existing ecosystems, don't reinvent
2. **Compile-Time Safety**: Arduino apps bundled at compile time
3. **Single-Purpose Optimization**: Skip menu for single-app deployments
4. **Cross-Platform Management**: One tool to rule them all

---

## Repository Structure

### oasis-rpi (Raspberry Pi Launcher)
**Language**: Rust  
**Purpose**: Visual app launcher and process manager

**Key Files**:
- `src/main.rs` - egui application entry point
- `src/app_scanner.rs` - Scans `/opt/oasis-apps/` for apps
- `src/process_manager.rs` - Launches and monitors processes
- `systemd/oasis-launcher.service` - Auto-start on boot

**App Format**:
```
/opt/oasis-apps/app-name/
├── manifest.json  # App metadata
├── run.sh         # Entry point
└── [app files]
```

### oasis-mcu (Arduino Multi-App System)
**Language**: C++ (Arduino) + Python (build system)  
**Purpose**: Compile-time app loading with intelligent menu

**Key Files**:
- `platforms/{board}/{app}/app.ino` - Individual apps
- `core/menu_system.h` - Menu system (multi-app mode)
- `core/app_interface.h` - App interface contract
- `build.py` - Intelligent compiler script

**Build Logic**:
- 1 app selected → Direct boot (no menu overhead)
- 2+ apps selected → Include menu system
- Overflow check → Fail before compile

### oasis-manager (Desktop Management App)
**Language**: Rust  
**Purpose**: Download apps, flash SD cards and Arduinos

**Key Features**:
- App repository browser
- SD card imaging (RPi)
- Arduino compilation and flashing
- Cross-platform (macOS, Windows, Linux)

---

## Development Workflow

### Adding a Raspberry Pi App

1. Create app directory:
```bash
mkdir -p /opt/oasis-apps/my-app
cd /opt/oasis-apps/my-app
```

2. Create manifest.json:
```json
{
  "name": "My App",
  "version": "1.0.0",
  "description": "Does something cool",
  "icon": "icon.png",
  "permissions": ["gpio", "serial"]
}
```

3. Create run.sh:
```bash
#!/bin/bash
cd "$(dirname "$0")"
python3 main.py
```

4. Make executable:
```bash
chmod +x run.sh
```

5. Restart launcher or it will auto-detect

### Adding an Arduino App

1. Create app directory:
```bash
mkdir -p oasis-mcu/platforms/atmega328p_uno/my-sensor
cd oasis-mcu/platforms/atmega328p_uno/my-sensor
```

2. Create manifest.json:
```json
{
  "name": "My Sensor",
  "version": "1.0.0",
  "description": "Reads temperature",
  "flash_size_kb": 8
}
```

3. Create app.ino with required functions:
```cpp
void my_sensor_setup() {
    // Initialize hardware
}

void my_sensor_loop() {
    // Main logic
}

void my_sensor_cleanup() {
    // Cleanup on exit
}
```

4. Build and flash:
```bash
python build.py --platform atmega328p_uno --apps my-sensor,led-controller
```

### Using Oasis Manager

1. Launch desktop app
2. Browse app repository
3. Select apps for RPi or Arduino
4. Click "Flash SD Card" or "Flash Arduino"
5. Done!

---

## Technical Specifications

### Raspberry Pi Launcher

**Dependencies**:
- Rust 1.70+
- egui 0.24+
- systemd

**Build**:
```bash
cd oasis-rpi
cargo build --release
sudo cp target/release/oasis-launcher /usr/local/bin/
sudo cp systemd/oasis-launcher.service /etc/systemd/system/
sudo systemctl enable oasis-launcher
sudo systemctl start oasis-launcher
```

**Configuration**:
- Apps directory: `/opt/oasis-apps/`
- Launcher runs on display :0
- Auto-starts via systemd

### Arduino Build System

**Dependencies**:
- Python 3.8+
- arduino-cli
- Platform-specific cores

**Build Script Usage**:
```bash
# Single app (no menu)
python build.py --platform atmega328p_uno --apps greenhouse-sensors

# Multiple apps (with menu)
python build.py --platform atmega328p_uno --apps greenhouse-sensors,led-controller

# Check size without compiling
python build.py --platform atmega328p_uno --apps app1,app2,app3 --dry-run
```

**Flash Size Limits**:
- ATmega328P (Uno): 32KB
- SAMD21 (Nano 33 IoT): 256KB
- ESP32: 4MB

### Oasis Manager

**Dependencies**:
- Rust 1.70+
- egui 0.24+
- arduino-cli (for Arduino flashing)
- Platform-specific SD card tools

**Build**:
```bash
cd oasis-manager
cargo build --release
```

**Supported Platforms**:
- macOS (Intel + Apple Silicon)
- Windows 10/11
- Linux (Ubuntu, Debian, Fedora)

---

## App Interface Contracts

### Raspberry Pi App (manifest.json)
```json
{
  "name": "string (required)",
  "version": "semver (required)",
  "description": "string (optional)",
  "icon": "path (optional)",
  "permissions": ["gpio", "serial", "camera", "network"],
  "run_command": "./run.sh (default)",
  "stop_command": "./stop.sh (optional)"
}
```

### Arduino App (manifest.json)
```json
{
  "name": "string (required)",
  "version": "semver (required)",
  "description": "string (optional)",
  "flash_size_kb": "number (estimated)",
  "ram_size_kb": "number (estimated)",
  "required_libraries": ["DHT", "FastLED"]
}
```

### Arduino App (app.ino)
```cpp
// Required functions (replace 'appname' with your app name)
void appname_setup();    // Called once on app start
void appname_loop();     // Called repeatedly while running
void appname_cleanup();  // Called on app exit (menu mode only)
```

---

## Menu System (Arduino)

### Serial Control Protocol
```json
// Commands from RPi to Arduino
{"action": "scroll_forward"}
{"action": "scroll_backward"}
{"action": "select"}
{"action": "back"}

// Responses from Arduino to RPi
{"type": "menu_state", "selected": 0, "app_name": "Greenhouse"}
{"type": "app_running", "app_name": "Greenhouse"}
{"type": "app_exited", "app_name": "Greenhouse"}
```

### GPIO Control (Optional)
```cpp
// Pin assignments (configurable)
#define SCROLL_FWD_PIN  2
#define SCROLL_BACK_PIN 3
#define SELECT_PIN      4
#define BACK_PIN        5
```

---

## Common Tasks

### Deploy Greenhouse System
```bash
# 1. Flash RPi SD card with apps
oasis-manager --device /dev/disk2 --apps greenhouse-control,timelapse

# 2. Flash Arduino with sensors
oasis-manager --port /dev/ttyUSB0 --platform uno --apps greenhouse-sensors

# 3. Insert SD card in RPi, connect Arduino via USB
# 4. Power on - system auto-starts
```

### Update an App
```bash
# RPi: Just replace files in /opt/oasis-apps/app-name/
# Arduino: Reflash with updated app

oasis-manager --port /dev/ttyUSB0 --platform uno --apps greenhouse-sensors-v2
```

### Debug an App
```bash
# RPi: Check systemd logs
journalctl -u oasis-launcher -f

# Arduino: Serial monitor
arduino-cli monitor -p /dev/ttyUSB0
```

---

## Future Enhancements

### Phase 2 (Optional)
- [ ] App sandboxing with bubblewrap
- [ ] OTA updates for Arduino (ESP32)
- [ ] Cloud app repository
- [ ] App marketplace with ratings
- [ ] Remote monitoring dashboard

### Phase 3 (Optional)
- [ ] Multi-device orchestration
- [ ] App dependencies and versioning
- [ ] Automated testing framework
- [ ] Performance profiling tools

---

## Troubleshooting

### RPi Launcher Won't Start
```bash
# Check service status
sudo systemctl status oasis-launcher

# Check logs
journalctl -u oasis-launcher -n 50

# Verify display
echo $DISPLAY  # Should be :0

# Test manually
/usr/local/bin/oasis-launcher
```

### Arduino Flash Overflow
```bash
# Check app sizes
python build.py --platform uno --apps app1,app2 --dry-run

# Remove apps or optimize code
# Menu system uses ~2KB flash
```

### SD Card Won't Flash
```bash
# Check permissions (Linux/macOS)
sudo oasis-manager

# Verify device path
diskutil list  # macOS
lsblk          # Linux
```

---

## Contributing

### Code Style
- **Rust**: `cargo fmt` and `cargo clippy`
- **C++**: Arduino style guide
- **Python**: PEP 8

### Testing
- **RPi**: Test on Pi 3B+ and Pi 4
- **Arduino**: Test on Uno, Nano 33 IoT, ESP32
- **Manager**: Test on all three platforms

### Pull Requests
1. Fork repository
2. Create feature branch
3. Add tests
4. Update documentation
5. Submit PR with description

---

## Resources

### Documentation
- [Rust Book](https://doc.rust-lang.org/book/)
- [egui Documentation](https://docs.rs/egui/)
- [Arduino Reference](https://www.arduino.cc/reference/en/)
- [arduino-cli](https://arduino.github.io/arduino-cli/)

### Community
- GitHub Issues: Bug reports and features
- Discussions: Questions and ideas
- Discord: Real-time chat (coming soon)

---

## License

MIT License - See LICENSE file for details

---

**Last Updated**: November 23, 2024  
**Maintainer**: Oasis-X Team
