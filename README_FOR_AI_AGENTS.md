# README for AI Agents: Oasis Firmware Project

**Last Updated**: March 10, 2026  
**Status**: Simulation Framework Implemented, MCP Server Active

---

## Quick Start for AI Agents

This document provides everything you need to understand and work on the Oasis Firmware project.

### What is This Project?

A configuration-driven firmware ecosystem for IoT devices with simulation and AI tooling:
- **oasis-core**: Rust CLI that generates firmware from YAML device configs
- **Simulation**: Behavioral models + MCU emulation with MCP server for AI control
- **oasis-mcu**: Compile-time multi-app system for Arduino with intelligent build
- **Legacy RPi**: Preserved Python toolkit for Raspberry Pi climate control

### Key Design Decisions

1. **Declarative Configuration**: Define devices in YAML, generate firmware code
2. **Simulation-First Development**: Test without hardware via behavioral models + emulators
3. **MCP Integration**: AI-accessible API for simulation control and component management
4. **Compile-Time Safety**: Arduino apps bundled at compile time (no dynamic loading)
5. **Platform Agnostic**: Support ESP32, Arduino, STM32, Raspberry Pi

---

## Project Structure

```
oasis-firmware/
├── README.md                        # Main project README
├── README_FOR_AI_AGENTS.md          # ← You are here
├── QUICKSTART.md                    # Fast onboarding guide
├── PROJECT_GUIDE.md                 # User-facing documentation
├── SIMPLIFIED_ARCHITECTURE.md       # Architecture overview (historical)
│
├── oasis-core/                      # Rust firmware generator
│   ├── Cargo.toml
│   ├── README.md
│   ├── src/
│   │   ├── bin/build.rs             # oasis-build CLI entry point
│   │   ├── lib.rs                   # Library exports
│   │   ├── codegen/                 # Code generation modules
│   │   └── config/                  # Config parsing & validation
│   └── examples/                    # device.yaml examples
│
├── oasis-rpi/                       # Main repo (GitHub: oasis-main/oasis-firmware)
│   ├── simulation/                  # ⭐ SIMULATION FRAMEWORK
│   │   ├── behavioral/              # Python component runtime
│   │   ├── emulators/               # MCU emulation wrappers
│   │   │   ├── simavr/              # Arduino (ATmega328P/2560)
│   │   │   ├── renode/              # STM32 (F103/F401/F407)
│   │   │   └── esp32/               # ESP32 (Wokwi CLI)
│   │   ├── components/              # YAML component library
│   │   ├── datasheet_ingestion/     # PDF → component YAML
│   │   ├── mcp_server.py            # ⭐ MCP SERVER
│   │   └── README.md
│   ├── desktop/                     # Rust + egui desktop app
│   ├── kicad_bridge/                # Python KiCAD integration
│   ├── docs/
│   │   ├── DEVICE_SCHEMA.md         # YAML configuration reference
│   │   ├── SIMULATION_ARCHITECTURE.md
│   │   └── DEPLOYMENT.md
│   └── legacy/rpi/                  # Original Python RPi toolkit
│
├── oasis-mcu/                       # Arduino multi-app system
│   ├── README.md
│   ├── BUILD_SYSTEM_SPEC.md         # Full build system spec
│   ├── platforms/
│   │   ├── atmega328p_uno/          # Arduino Uno apps
│   │   ├── esp32_devkit/            # ESP32 apps
│   │   └── stm32f103/               # STM32 apps
│   ├── core/                        # Menu system implementation
│   └── build.py                     # Intelligent compiler
│
├── oasis-ino/                       # Arduino code generation templates
│   ├── platforms/
│   └── skeletons/
│
└── oasis-manager/                   # Desktop app (spec only)
    └── MANAGER_SPEC.md
```

---

## Core Components

### 1. Simulation Framework (oasis-rpi/simulation) ⭐ PRIMARY FOCUS

**Purpose**: Test device configurations without hardware  
**Language**: Python  
**Location**: `oasis-rpi/simulation/`

**Components**:
- **Behavioral Runtime**: Python execution of YAML-defined component models
- **MCU Emulators**: simavr (Arduino), Renode (STM32), Wokwi (ESP32)
- **MCP Server**: AI-accessible API for simulation control
- **Datasheet Ingestion**: PDF → component YAML extraction

**Key Files**:
- `mcp_server.py` - MCP server entry point
- `behavioral/runtime.py` - Component simulation runtime
- `components/*.yaml` - Component library
- `emulators/orchestrator.py` - Unified emulator interface

**Quick Start**:
```bash
cd oasis-rpi/simulation
pip install -e .[all]
oasis-sim  # Start MCP server
```

### 2. MCP Tools (AI Interface)

| Tool | Description | Example |
|------|-------------|---------|
| `sim_start` | Start simulation | `sim_start(config="device.yaml")` |
| `sim_stop` | Stop simulation | `sim_stop(sim_id="sim_123")` |
| `sim_step` | Advance time | `sim_step(sim_id, duration_ms=1000)` |
| `sim_get_state` | Get full state | `sim_get_state(sim_id)` |
| `sim_set_sensor_value` | Set input | `sim_set_sensor_value(sim_id, "temp1", 25.0)` |
| `sim_inject_fault` | Inject fault | `sim_inject_fault(sim_id, "temp1", "disconnect")` |
| `component_list` | List components | `component_list()` |
| `component_describe` | Get schema | `component_describe("dht22")` |
| `component_add` | Add component | `component_add(sim_id, "temp1", "dht22")` |
| `datasheet_parse` | Parse PDF | `datasheet_parse("sensor.pdf")` |
| `datasheet_generate` | Generate YAML | `datasheet_generate("sensor.pdf", "out.yaml")` |

### 3. oasis-core (Firmware Generator)

**Purpose**: Generate firmware from YAML device configs  
**Language**: Rust  
**Location**: `oasis-core/`

**CLI Commands**:
```bash
# Validate config
oasis-build validate --config device.yaml

# Generate firmware code
oasis-build generate --config device.yaml --output ./build/

# Show device info
oasis-build info --config device.yaml
```

**Key Files**:
- `src/bin/build.rs` - CLI entry point
- `src/codegen/` - Code generation for each platform
- `src/config/` - YAML parsing and validation

### 4. Arduino Build System (oasis-mcu)

**Purpose**: Compile multiple apps into single firmware  
**Language**: Python (build script) + C++ (apps)  
**Supports**: Arduino Uno, ESP32, STM32, Nano 33 IoT

**How It Works**:
1. User selects platform and apps
2. Build script checks flash size
3. If 1 app: Generate direct boot firmware (no menu)
4. If 2+ apps: Generate firmware with menu system
5. Compile using arduino-cli
6. Flash to board

**App Structure**:
```cpp
// Required functions (prefix with app name)
void myapp_setup() { /* Initialize */ }
void myapp_loop() { /* Main logic */ }
void myapp_cleanup() { /* Cleanup */ }
```

**Key Files**:
- `build.py` - Build orchestration
- `BUILD_SYSTEM_SPEC.md` - Full specification
- `platforms/{board}/{app}/app.ino` - Individual apps

### 5. Legacy RPi Toolkit (oasis-rpi/legacy/rpi)

**Purpose**: Python-based Raspberry Pi climate control  
**Language**: Python  
**Status**: Preserved for backward compatibility

**Features**:
- PID climate control (temperature, humidity)
- GPIO relay control for equipment
- Arduino sensor communication via serial
- Camera integration with NDVI analysis
- Web API for remote control

**Key Files**:
- `main.py` - Main orchestration
- `api.py` - Local API
- `configs/` - JSON configuration files

---

## Common Tasks for AI Agents

### Task 1: Run a Simulation (Most Common)

```python
from behavioral import BehavioralRuntime
from pathlib import Path

# Initialize runtime
runtime = BehavioralRuntime()
runtime.load_component_library(Path('oasis-rpi/simulation/components'))

# Add components
runtime.add_component('temp1', 'dht22')
runtime.add_component('relay1', 'relay')

# Set environment
runtime.set_physical_input('temp1', 'temp_actual', 25.0)
runtime.set_physical_input('temp1', 'humidity_actual', 60.0)

# Run simulation
for _ in range(100):
    runtime.step(0.1)  # 100ms steps
    state = runtime.get_state()
    print(f"Temp: {state['components']['temp1']['temperature']:.1f}°C")
```

### Task 2: Add a New Component to Library

Create `oasis-rpi/simulation/components/sensors/my_sensor.yaml`:

```yaml
component:
  id: my_sensor
  name: My Custom Sensor
  type: sensor
  
  inputs:
    - name: value_actual
      type: analog
      unit: "units"
      range_min: 0
      range_max: 100
      
  outputs:
    - name: value
      type: i2c
      unit: "units"
      
  parameters:
    accuracy:
      value: 1.0
      unit: "units"
      
  behavior:
    model: gaussian
    noise_stddev: 0.5
    read_interval_ms: 1000
```

### Task 3: Create a Device Config

Create `my_device.yaml`:

```yaml
device:
  id: my-device
  name: My IoT Device
  board:
    platform: mcu
    model: esp32_devkit

sensors:
  - name: temp
    type: dht22
    pins:
      data: 4
    sampling:
      interval_ms: 5000

actuators:
  - name: led
    type: relay
    pins:
      output: 16

control_loops:
  - name: temp_warning
    type: threshold
    input:
      sensor: temp
      measurement: temperature
    output:
      actuator: led
    threshold:
      setpoint: 30.0
      hysteresis: 2.0
      direction: heat
```

### Task 4: Add a New Arduino App

1. Create app directory:
```bash
mkdir -p oasis-mcu/platforms/atmega328p_uno/my_sensor
```

2. Create `manifest.json`:
```json
{
  "name": "My Sensor",
  "version": "1.0.0",
  "resources": {
    "flash_size_kb": 6,
    "ram_size_kb": 1
  },
  "dependencies": {
    "libraries": [{"name": "DHT", "version": ">=1.4.0"}]
  },
  "menu": {
    "display_name": "My Sensor"
  }
}
```

3. Create `app.ino`:
```cpp
void my_sensor_setup() {
    Serial.begin(9600);
}

void my_sensor_loop() {
    Serial.println("{\"status\":\"ok\"}");
    delay(1000);
}

void my_sensor_cleanup() {
    // Cleanup
}
```

4. Build and test:
```bash
cd oasis-mcu
python build.py --platform atmega328p_uno --apps my_sensor --dry-run
python build.py --platform atmega328p_uno --apps my_sensor
```

### Task 5: Generate Firmware from Config

```bash
cd oasis-core
cargo build --release

# Validate
./target/release/oasis-build validate --config ../my_device.yaml

# Generate
./target/release/oasis-build generate --config ../my_device.yaml --output ../build/
```

### Task 6: Parse a Datasheet

```bash
cd oasis-rpi/simulation

# Parse to JSON
oasis-datasheet parse sensor.pdf --json

# Generate component YAML
oasis-datasheet generate sensor.pdf -o components/sensors/new_sensor.yaml
```

---

## Important Constraints

### Simulation
- **Python**: 3.8+ required
- **Emulators**: Optional - simavr, Renode, Wokwi CLI for MCU emulation
- **PDF Parsing**: Requires `[pdf]` extras for datasheet ingestion

### Arduino (oasis-mcu)
- **Flash Limits**: 
  - Uno: 32KB (tight!)
  - ESP32: 4MB (plenty)
  - Nano 33 IoT: 256KB (good)
  - STM32F103: 64KB
- **Menu Overhead**: ~2KB
- **No Dynamic Loading**: All apps compiled into firmware
- **Function Naming**: Must follow `{appname}_setup/loop/cleanup` pattern

### Device Config (YAML)
- **Required**: `device.id`, `device.board.platform`, `device.board.model`
- **Environment Variables**: Use `${VAR}` syntax for secrets
- **Pins**: Must not conflict within same device

---

## Testing Guidelines

### Simulation Framework
```bash
cd oasis-rpi/simulation
pip install -e .[all]

# Run tests
pytest tests/ -v

# Start MCP server
oasis-sim
```

### oasis-core (Rust CLI)
```bash
cd oasis-core
cargo test
cargo build --release
./target/release/oasis-build validate --config examples/greenhouse.yaml
```

### Arduino Build System
```bash
cd oasis-mcu

# Test single app
python build.py --platform atmega328p_uno --apps greenhouse_sensors --dry-run

# Test multi-app
python build.py --platform atmega328p_uno --apps app1,app2 --dry-run

# Test overflow detection
python build.py --platform atmega328p_uno --apps app1,app2,app3,app4 --dry-run
```

---

## Common Pitfalls

### 1. Simulation Module Not Found
**Problem**: `No module named 'behavioral'`  
**Solution**: `pip install -e .` in simulation directory

### 2. Arduino Flash Overflow
**Problem**: Too many apps selected for small board  
**Solution**: Use `--dry-run` to check sizes first

### 3. Arduino Function Naming
**Problem**: Menu can't find app functions  
**Solution**: Must follow `{appname}_setup/loop/cleanup` pattern exactly

### 4. arduino-cli Not Found
**Problem**: Build script can't compile  
**Solution**: Install arduino-cli and add to PATH

### 5. MCP Server Connection
**Problem**: AI assistant can't connect  
**Solution**: Ensure MCP config points to correct simulation directory

---

## Architecture Decisions

### Why Simulation-First?
- Test without physical hardware
- Faster iteration cycles
- AI agents can run simulations autonomously
- Catch bugs before flashing to devices

### Why YAML for Device Config?
- Human-readable
- Easy to diff and version control
- Can be generated by AI agents
- Supports environment variable substitution

### Why MCP Server?
- AI assistants can control simulations
- Standard protocol (Model Context Protocol)
- Enables autonomous testing and validation
- Works with Windsurf, Cursor, Claude Desktop

### Why Compile-Time App Loading for Arduino?
- Arduino can't dynamically load code
- Compile-time is safer (no runtime failures)
- Smaller footprint than dynamic loader

### Why Preserve Legacy RPi Toolkit?
- Existing users depend on it
- Proven in production environments
- New system can coexist alongside it

---

## Project Status

| Component | Status | Priority |
|-----------|--------|----------|
| Simulation Framework | ✅ Complete | - |
| MCP Server | ✅ Complete | - |
| Behavioral Runtime | ✅ Complete | - |
| MCU Emulators | ✅ Complete | - |
| Datasheet Ingestion | ✅ Complete | - |
| oasis-core CLI | ✅ Complete | - |
| Component Library | 🟡 In Progress | High |
| oasis-mcu Build Script | 📋 Specified | Medium |
| oasis-manager Desktop | 📋 Specified | Low |

---

## Getting Help

### Documentation
- `README.md` - Main project overview
- `QUICKSTART.md` - Fast onboarding
- `oasis-rpi/docs/DEVICE_SCHEMA.md` - YAML config reference
- `oasis-rpi/docs/SIMULATION_ARCHITECTURE.md` - Simulation design
- `oasis-rpi/simulation/README.md` - Simulation quick start
- `oasis-mcu/BUILD_SYSTEM_SPEC.md` - Arduino build system

### Code Locations
- `oasis-rpi/simulation/` - Simulation framework
- `oasis-rpi/simulation/mcp_server.py` - MCP server
- `oasis-rpi/simulation/components/` - Component library
- `oasis-core/src/` - Rust firmware generator
- `oasis-mcu/platforms/` - Arduino app examples

### External Resources
- [MCP Protocol](https://modelcontextprotocol.io/)
- [Rust Book](https://doc.rust-lang.org/book/)
- [Arduino Reference](https://www.arduino.cc/reference/en/)
- [Wokwi Simulator](https://wokwi.com/)
- [arduino-cli](https://arduino.github.io/arduino-cli/)

---

## Checklist for New AI Agents

Before starting work, verify:

- [ ] Read this document completely
- [ ] Understand the simulation framework and MCP tools
- [ ] Know the device YAML config format
- [ ] Can start the MCP server (`oasis-sim`)
- [ ] Understand component library structure
- [ ] Know which constraints apply (flash limits, function naming)
- [ ] Reviewed relevant documentation in `oasis-rpi/docs/`

---

## Quick Reference

### Start Simulation
```bash
cd oasis-rpi/simulation
pip install -e .[all]
oasis-sim  # MCP server
```

### Generate Firmware
```bash
cd oasis-core
cargo build --release
./target/release/oasis-build generate --config device.yaml --output ./build/
```

### Build Arduino Apps
```bash
cd oasis-mcu
python build.py --platform atmega328p_uno --apps app1,app2
```

### Key File Locations
| Purpose | Location |
|---------|----------|
| MCP Server | `oasis-rpi/simulation/mcp_server.py` |
| Component Library | `oasis-rpi/simulation/components/` |
| Device Schema Docs | `oasis-rpi/docs/DEVICE_SCHEMA.md` |
| Firmware Generator | `oasis-core/src/` |
| Arduino Apps | `oasis-mcu/platforms/{platform}/{app}/` |
| Legacy RPi | `oasis-rpi/legacy/rpi/` |

### Key Patterns
- Device configs: `device.yaml` with `device`, `sensors`, `actuators`, `control_loops`
- Components: YAML with `inputs`, `outputs`, `parameters`, `behavior`
- Arduino functions: `{appname}_setup/loop/cleanup`
- MCP tools: `sim_*` for simulation, `component_*` for library, `datasheet_*` for PDF

---

**Remember**: Simulation-first development. Test before flashing. AI-accessible via MCP.

Good luck! 🚀
