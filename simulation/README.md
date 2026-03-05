# Oasis Simulation

Unified simulation framework for Oasis firmware with MCU emulation and MCP interface.

## Features

- **Component Library**: YAML-defined behavioral models for sensors and actuators
- **Behavioral Runtime**: Python runtime that executes component models
- **MCU Emulators**: Arduino (simavr), STM32 (Renode), ESP32 (QEMU/Wokwi)
- **Datasheet Ingestion**: PDF → component YAML generation
- **MCP Server**: AI-accessible API for simulation control
- **Fault Injection**: Test edge cases with disconnect, stuck, offset, and noise faults

## Getting Started: Build Your First Device

### 1. Install the Simulation Framework

```bash
cd oasis-firmware/oasis-rpi/simulation
pip install -e .[all]
```

### 2. Create a Device Configuration

Create `my_device.yaml` in your project directory:

```yaml
device:
  id: my-first-device
  name: Simple Temperature Monitor
  board:
    platform: mcu
    model: esp32_devkit

sensors:
  - name: temp_sensor
    type: dht22
    pins:
      data: 4
    sampling:
      interval_ms: 5000

actuators:
  - name: warning_led
    type: relay
    pins:
      output: 16
    default:
      state: off

control_loops:
  - name: temp_warning
    type: threshold
    input:
      sensor: temp_sensor
      measurement: temperature
    output:
      actuator: warning_led
    threshold:
      setpoint: 30.0
      hysteresis: 2.0
      direction: heat
```

### 3. Run a Simulation

```python
from behavioral import BehavioralRuntime
from pathlib import Path

# Initialize runtime
runtime = BehavioralRuntime()
runtime.load_component_library(Path('components'))

# Add components
runtime.add_component('temp1', 'dht22')
runtime.add_component('led1', 'relay')

# Set physical input (simulated environment)
runtime.set_physical_input('temp1', 'temp_actual', 25.0)
runtime.set_physical_input('temp1', 'humidity_actual', 60.0)

# Run simulation loop
for _ in range(100):
    runtime.step(0.1)  # 100ms steps
    state = runtime.get_state()
    print(f"Time: {state['sim_time_ms']}ms")
```

### 4. Using the MCP Server (AI-Assisted Development)

Start the MCP server for AI assistant integration:

```bash
oasis-sim  # Runs stdio MCP server
```

Then use your AI assistant to:
- Add components: "Add a DHT22 sensor called sensor1"
- Run simulation: "Step the simulation forward 1 second"
- Inject faults: "Disconnect sensor1 to test fault handling"
- Generate components: "Parse this datasheet and create a component YAML"

## Desktop UI (Rust + egui)

The desktop application provides a visual interface for simulation:

```bash
cd oasis-firmware/oasis-rpi/desktop
cargo run --release
```

### UI Features
- **Device Editor**: Visual drag-and-drop component placement
- **Wiring View**: See signal connections between components
- **Simulation Panel**: Real-time waveform visualization
- **Fault Injection**: Click to inject faults and test resilience

## Quick Start (CLI)

```bash
# Install (basic)
cd simulation
pip install -e .

# Install with PDF parsing
pip install -e .[pdf]

# Install all features
pip install -e .[all]

# Run MCP server (stdio mode)
oasis-sim

# Parse a datasheet
oasis-datasheet parse sensor.pdf --json
oasis-datasheet generate sensor.pdf -o components/sensors/new.yaml
```

## Emulator Prerequisites

### ESP32 (Wokwi CLI) - Recommended
```bash
# macOS ARM64
curl -L -o /usr/local/bin/wokwi-cli \
  https://github.com/wokwi/wokwi-cli/releases/download/v0.26.1/wokwi-cli-macos-arm64
chmod +x /usr/local/bin/wokwi-cli

# macOS x64
curl -L -o /usr/local/bin/wokwi-cli \
  https://github.com/wokwi/wokwi-cli/releases/download/v0.26.1/wokwi-cli-macos-x64
chmod +x /usr/local/bin/wokwi-cli

# Linux
curl -L -o /usr/local/bin/wokwi-cli \
  https://github.com/wokwi/wokwi-cli/releases/download/v0.26.1/wokwi-cli-linux-x64
chmod +x /usr/local/bin/wokwi-cli

# Verify
wokwi-cli --version
```

### Arduino (simavr)
```bash
# macOS - build from source
brew tap osx-cross/avr
brew install avr-gcc libelf
git clone https://github.com/buserror/simavr.git
cd simavr && make && sudo make install PREFIX=/usr/local

# Ubuntu/Debian
sudo apt install simavr avr-libc

# Verify
simavr --help
```

### STM32 (Renode)
```bash
# macOS ARM64
curl -LO https://github.com/renode/renode/releases/download/v1.16.1/renode-1.16.1-dotnet.osx-arm64-portable.dmg
hdiutil attach renode-1.16.1-dotnet.osx-arm64-portable.dmg
cp -R "/Volumes/Renode_1.16.1/Renode.app" /Applications/
ln -sf /Applications/Renode.app/Contents/MacOS/Renode /usr/local/bin/renode
hdiutil detach "/Volumes/Renode_1.16.1"

# macOS x64
curl -LO https://github.com/renode/renode/releases/download/v1.16.1/renode_1.16.1.dmg
# Mount and copy to /Applications

# Ubuntu/Debian
sudo apt install renode

# Verify
renode --version
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `sim_start` | Start a new simulation session |
| `sim_stop` | Stop a simulation session |
| `sim_step` | Advance simulation time |
| `sim_get_state` | Get current simulation state |
| `sim_set_sensor_value` | Set physical input for a sensor |
| `sim_inject_fault` | Inject a fault into a component |
| `component_list` | List available component types |
| `component_describe` | Get component schema details |
| `component_add` | Add a component instance |

## Component Library

### Sensors
- `dht22` - Temperature & humidity (single-wire)
- `bme280` - Temperature, humidity, pressure (I2C)
- `scd40` - CO2, temperature, humidity (I2C)
- `soil_moisture` - Capacitive soil moisture (analog)
- `light_sensor` - BH1750 ambient light (I2C)

### Actuators
- `relay` - Electromechanical relay
- `servo` - PWM servo motor
- `dc_motor` - DC motor with H-bridge
- `led_strip` - WS2812B addressable LEDs
- `pump` - Water pump

## Adding Custom Components

Create a YAML file in `components/sensors/` or `components/actuators/`:

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

## MCP Configuration

Add to your AI assistant's MCP config:

```json
{
  "mcpServers": {
    "oasis-simulation": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/oasis-firmware/simulation"
    }
  }
}
```

## Architecture

See [SIMULATION_ARCHITECTURE.md](../docs/SIMULATION_ARCHITECTURE.md) for the full co-simulation design including:
- MCU emulator integration (Phase 2)
- FMI/Modelica co-simulation (Phase 3)
- Datasheet ingestion (Phase 4)
