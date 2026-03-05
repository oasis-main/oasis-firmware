# Oasis Build Desktop App Design

A Rust + egui desktop application for visual firmware development, simulation, and deployment.

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Framework** | egui + eframe | Pure Rust, fast, cross-platform, already in your stack |
| **Async Runtime** | tokio | For MQTT monitoring, SSH deployment |
| **Serial** | serialport-rs | USB device detection, flashing |
| **Styling** | egui-extras, egui-notify | Tables, toasts, enhanced widgets |

## UI Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🌿 Oasis Build                                           [_][□][×]         │
├──────────────────┬──────────────────────────────────────────────────────────┤
│                  │  ┌─────────────────────────────────────────────────────┐ │
│  📁 DEVICES      │  │  greenhouse-node-01                    [▶ Build]    │ │
│  ─────────────   │  │  ESP32 DevKit • 3 sensors • 3 actuators             │ │
│  ▼ greenhouse/   │  └─────────────────────────────────────────────────────┘ │
│    └ node-01 ●   │                                                          │
│    └ node-02 ○   │  ┌─ Config ─┬─ Simulate ─┬─ Hardware ─┬─ Deploy ─┐      │
│  ▶ hydroponics/  │  │          │            │            │          │      │
│  ▶ apiary/       │  │ ╔════════════════════════════════════════════╗ │      │
│                  │  │ ║  device:                                   ║ │      │
│  ─────────────   │  │ ║    id: greenhouse-node-01                  ║ │      │
│  + New Device    │  │ ║    board:                                  ║ │      │
│                  │  │ ║      platform: mcu                         ║ │      │
│  📊 MONITORING   │  │ ║      model: esp32_devkit                   ║ │      │
│  ─────────────   │  │ ║                                            ║ │      │
│  greenhouse-01   │  │ ║  sensors:                                  ║ │      │
│    🌡 24.5°C     │  │ ║    - name: air_temp_humidity               ║ │      │
│    💧 62%        │  │ ║      type: dht22                           ║ │      │
│    🌱 45%        │  │ ║      pins:                                 ║ │      │
│                  │  │ ║        data: 4                             ║ │      │
│                  │  │ ╚════════════════════════════════════════════╝ │      │
│                  │  │                                                │      │
│                  │  │  [Validate] [Generate Code] [Open in VS Code]  │      │
│                  │  └────────────────────────────────────────────────┘      │
├──────────────────┴──────────────────────────────────────────────────────────┤
│  ✓ Config valid │ Generated: 2 min ago │ Device: Not connected │ MQTT: ●   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Tabs

### 1. Config Tab (YAML Editor)
- Syntax-highlighted YAML editor (egui_code_editor)
- Real-time validation with inline error markers
- Auto-complete for sensor types, board models
- Schema-aware suggestions

### 2. Simulate Tab
```
┌─────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────┐  ┌──────────────────────────────────┐ │
│  │                     │  │  SENSOR VALUES                   │ │
│  │   [Wokwi Circuit]   │  │  ─────────────────────────────── │ │
│  │                     │  │  🌡 Temperature    [====⚪====] 25°C │
│  │   ESP32 ──── DHT22  │  │  💧 Humidity       [====⚪====] 60% │
│  │     │                │  │  🌱 Soil Moisture  [==⚪======] 40% │
│  │     ├──── Relay 1   │  │  💡 Light Level    [======⚪==] 800lx│
│  │     └──── Relay 2   │  │                                  │ │
│  │                     │  │  ACTUATOR STATES                 │ │
│  └─────────────────────┘  │  ─────────────────────────────── │ │
│                           │  🔌 Grow Light     [OFF] [ON]    │ │
│  [▶ Start] [⏸ Pause]     │  🌀 Exhaust Fan    [====⚪====]   │ │
│  [📁 Load Scenario]       │  💦 Irrigation     [OFF] [ON]    │ │
│                           └──────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Serial Monitor                                    [Clear]  ││
│  │ ───────────────────────────────────────────────────────────││
│  │ [INFO] Starting greenhouse-node-01 firmware                ││
│  │ [INFO] Initialized 3 sensors                               ││
│  │ [INFO] Temperature: 25.0°C, Humidity: 60%                  ││
│  │ [WARN] Threshold breach: temp > 28°C, activating fan       ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

- Interactive sliders to adjust virtual sensor values
- Toggle buttons for actuators
- Real-time serial monitor output
- Load test scenarios from JSON

### 3. Hardware Tab
```
┌─────────────────────────────────────────────────────────────────┐
│  PCB DESIGN                           BILL OF MATERIALS        │
│  ─────────────────────────────────    ───────────────────────  │
│  KiCAD Project: ./pcb/greenhouse.kicad_pro  [Open KiCAD]       │
│                                                                 │
│  ┌─────────────────────────┐          │ Ref │ Part    │ Qty │  │
│  │                         │          ├─────┼─────────┼─────┤  │
│  │   [Schematic Preview]   │          │ U1  │ DHT22   │ 1   │  │
│  │                         │          │ U2  │ BH1750  │ 1   │  │
│  │         U1              │          │ K1  │ Relay   │ 2   │  │
│  │     ┌───┴───┐           │          │ J1  │ JST-XH  │ 3   │  │
│  │  ───┤ DHT22 ├───        │          └─────┴─────────┴─────┘  │
│  │     └───────┘           │                                   │
│  │                         │          ENCLOSURE                │
│  └─────────────────────────┘          ───────────────────────  │
│                                       Model: IP65 ABS 100x68   │
│  [Validate Netlist] [Export BOM]      [Open in FreeCAD]        │
└─────────────────────────────────────────────────────────────────┘
```

- KiCAD project link with netlist validation
- BOM generation with supplier links
- Enclosure preview (if FreeCAD file linked)

### 4. Deploy Tab
```
┌─────────────────────────────────────────────────────────────────┐
│  TARGET DEVICE                                                  │
│  ─────────────────────────────────────────────────────────────  │
│  ○ USB Serial   Port: [/dev/ttyUSB0 ▼]  [🔄 Refresh]           │
│  ● SSH          Host: [greenhouse-rpi.local]  User: [oasis]    │
│  ○ OTA MQTT     Topic: [oasis/devices/greenhouse-01/ota]       │
│                                                                 │
│  BUILD & FLASH                                                  │
│  ─────────────────────────────────────────────────────────────  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ $ cargo build --release                                 │   │
│  │ Compiling greenhouse_node_01 v0.1.0                     │   │
│  │ Finished release [optimized] target(s) in 45.2s        │   │
│  │                                                         │   │
│  │ $ espflash flash target/.../firmware                    │   │
│  │ [========================================] 100%         │   │
│  │ ✓ Flashed successfully!                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [🔨 Build] [⚡ Flash] [🔨⚡ Build & Flash] [📊 Monitor]        │
└─────────────────────────────────────────────────────────────────┘
```

- Device discovery (USB, mDNS for network devices)
- One-click build and flash
- Progress bar with build/flash status
- Serial monitor integration

## Real-Time Monitoring (Left Sidebar)

When devices are online and connected via MQTT:

```
📊 MONITORING
─────────────
greenhouse-01 ●
  🌡 24.5°C  ↑0.2
  💧 62%     ↓1
  🌱 45%     →
  ⏱ 2s ago

greenhouse-02 ○
  Last seen: 5 min ago
```

- Live sensor data via MQTT subscription
- Sparkline graphs for trends
- Alert indicators for threshold breaches
- Click to view detailed device dashboard

## Project Structure

```
oasis-build-desktop/
├── Cargo.toml
├── src/
│   ├── main.rs              # App entry, eframe setup
│   ├── app.rs               # Main App struct, update loop
│   ├── ui/
│   │   ├── mod.rs
│   │   ├── sidebar.rs       # Device tree, monitoring
│   │   ├── config_tab.rs    # YAML editor
│   │   ├── simulate_tab.rs  # Wokwi integration
│   │   ├── hardware_tab.rs  # KiCAD/BOM
│   │   └── deploy_tab.rs    # Build/flash
│   ├── services/
│   │   ├── mod.rs
│   │   ├── mqtt.rs          # MQTT client for monitoring
│   │   ├── serial.rs        # USB device detection
│   │   ├── build.rs         # Cargo build orchestration
│   │   └── flash.rs         # espflash/probe-rs integration
│   └── state/
│       ├── mod.rs
│       ├── devices.rs       # Device config state
│       └── telemetry.rs     # Live sensor data
└── assets/
    └── icons/               # Sensor/actuator icons
```

## Key Dependencies

```toml
[dependencies]
eframe = "0.27"
egui = "0.27"
egui_extras = "0.27"
egui-notify = "0.14"
egui_code_editor = "0.2"

# Async
tokio = { version = "1", features = ["full"] }

# MQTT
rumqttc = "0.24"

# Serial
serialport = "4.3"

# Build tooling
which = "6.0"           # Find espflash, cargo, etc.

# Config
serde = { version = "1", features = ["derive"] }
serde_yaml = "0.9"

# Use oasis-core as a library
oasis-core = { path = "../oasis-core" }
```

## Implementation Priority

1. **Phase 1**: Config editor with validation + code generation
2. **Phase 2**: Deploy tab with USB flashing
3. **Phase 3**: Simulate tab with Wokwi integration
4. **Phase 4**: Hardware tab with KiCAD integration
5. **Phase 5**: Live MQTT monitoring

## Mockup Rendering

The UI should feel like a blend of:
- **Arduino IDE** (simplicity, one-click build/upload)
- **PlatformIO** (project management, multiple devices)
- **Home Assistant** (live monitoring dashboard)

All implemented in pure Rust for your robustness requirements.
