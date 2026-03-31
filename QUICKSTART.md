# Oasis Firmware Quick Start

Get up and running with Oasis Firmware in 10 minutes.

---

## Prerequisites

| Tool | Required For | Install |
|------|--------------|---------|
| Rust 1.70+ | oasis-build CLI | [rustup.rs](https://rustup.rs) |
| Python 3.8+ | Simulation, Arduino build | System package manager |
| arduino-cli | Arduino flashing | `brew install arduino-cli` |

---

## Path 1: Simulation Only (No Hardware)

Test device configurations without physical hardware.

### Step 1: Install Simulation Framework

```bash
cd oasis-firmware/oasis-rpi/simulation
pip install -e .[all]
```

### Step 2: Start MCP Server

```bash
oasis-sim
```

The server is now listening for MCP tool calls from your AI assistant.

### Step 3: Run a Simulation (Python)

```python
from behavioral import BehavioralRuntime
from pathlib import Path

# Initialize
runtime = BehavioralRuntime()
runtime.load_component_library(Path('components'))

# Add a DHT22 sensor
runtime.add_component('temp1', 'dht22')

# Set environment (25°C, 60% humidity)
runtime.set_physical_input('temp1', 'temp_actual', 25.0)
runtime.set_physical_input('temp1', 'humidity_actual', 60.0)

# Run 10 seconds of simulation
for _ in range(100):
    runtime.step(0.1)
    state = runtime.get_state()
    print(f"Temp: {state['components']['temp1']['temperature']:.1f}°C")
```

---

## Path 2: ESP32 Device

### Step 1: Create Device Config

Create `my_device.yaml`:

```yaml
device:
  id: my-esp32
  name: My First ESP32 Device
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
  - name: led
    type: relay
    pins:
      output: 2
    default:
      state: off
```

### Step 2: Build oasis-build CLI

```bash
cd oasis-firmware/oasis-core
cargo build --release
```

### Step 3: Generate Firmware

```bash
./target/release/oasis-build generate --config my_device.yaml --output ./build/
```

### Step 4: Flash to ESP32

```bash
cd build
cargo build --release
espflash flash target/release/my-esp32
```

---

## Path 3: Arduino (oasis-mcu)

### Step 1: Install arduino-cli

```bash
# macOS
brew install arduino-cli

# Linux
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

# Install Arduino Uno core
arduino-cli core install arduino:avr
```

### Step 2: List Available Apps

```bash
cd oasis-firmware/oasis-mcu
python build.py --platform atmega328p_uno --list-apps
```

### Step 3: Build Firmware

```bash
# Single app (no menu)
python build.py --platform atmega328p_uno --apps greenhouse_sensors

# Multiple apps (with menu)
python build.py --platform atmega328p_uno --apps greenhouse_sensors,led_controller
```

### Step 4: Flash to Arduino

```bash
python build.py --platform atmega328p_uno --apps greenhouse_sensors --port /dev/ttyUSB0 --flash
```

---

## Path 4: Raspberry Pi (Legacy Toolkit)

### Step 1: Flash Raspberry Pi OS

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Flash Raspberry Pi OS Lite to SD card
3. Enable SSH in Imager settings
4. Boot the Pi

### Step 2: Install oasis-rpi

SSH into your Pi:

```bash
ssh pi@raspberrypi.local

# Install
sudo apt-get update -y
sudo apt-get install git -y
git clone https://github.com/oasis-main/oasis-firmware.git
cd oasis-firmware/oasis-rpi/legacy/rpi
. install.sh
```

### Step 3: Configure

Edit `configs/feature_toggles.json` to enable your sensors/actuators.

### Step 4: Start

```bash
. start.sh
```

---

## MCP Server Configuration

Add to your AI assistant's MCP config (Windsurf/Cursor/Claude Desktop):

```json
{
  "mcpServers": {
    "oasis-simulation": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/oasis-firmware/oasis-rpi/simulation"
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `sim_start` | Start simulation session |
| `sim_step` | Advance simulation time |
| `sim_get_state` | Get current state |
| `sim_set_sensor_value` | Set sensor input |
| `sim_inject_fault` | Inject fault |
| `component_list` | List components |
| `component_add` | Add component |
| `datasheet_parse` | Parse PDF datasheet |

---

## Example Projects

### Greenhouse Monitor

```yaml
# greenhouse.yaml
device:
  id: greenhouse-monitor
  name: Greenhouse Environmental Monitor
  board:
    platform: mcu
    model: esp32_devkit

sensors:
  - name: air
    type: dht22
    pins: { data: 4 }
    sampling: { interval_ms: 5000 }
    
  - name: soil
    type: capacitive_moisture
    pins: { adc: 34 }
    sampling: { interval_ms: 10000 }

actuators:
  - name: pump
    type: relay
    pins: { output: 16 }
    
  - name: fan
    type: relay
    pins: { output: 17 }

control_loops:
  - name: irrigation
    type: threshold
    input: { sensor: soil, measurement: moisture }
    output: { actuator: pump }
    threshold: { setpoint: 40, hysteresis: 10, direction: heat }
```

### Temperature Logger

```yaml
# temp_logger.yaml
device:
  id: temp-logger
  name: Temperature Logger
  board:
    platform: mcu
    model: arduino_uno

sensors:
  - name: temp
    type: ds18b20
    pins: { data: 2 }
    sampling: { interval_ms: 60000 }

data_publishing:
  mqtt:
    enabled: false
  local_storage:
    enabled: true
    max_records: 1440  # 24 hours at 1 min intervals
```

---

## Troubleshooting

### "oasis-build: command not found"

```bash
# Add to PATH
export PATH="$PATH:/path/to/oasis-firmware/oasis-core/target/release"
```

### "No module named 'behavioral'"

```bash
cd oasis-firmware/oasis-rpi/simulation
pip install -e .
```

### "arduino-cli: board not found"

```bash
# List connected boards
arduino-cli board list

# Install missing core
arduino-cli core install arduino:avr
```

### ESP32 flash fails

```bash
# Install espflash
cargo install espflash

# Put ESP32 in boot mode (hold BOOT button while pressing RESET)
espflash flash --monitor target/release/firmware
```

---

## Next Steps

1. **Learn the schema**: Read [DEVICE_SCHEMA.md](oasis-rpi/docs/DEVICE_SCHEMA.md)
2. **Explore simulation**: See [SIMULATION_ARCHITECTURE.md](oasis-rpi/docs/SIMULATION_ARCHITECTURE.md)
3. **Create custom components**: Add YAML files to `simulation/components/`
4. **Integrate with KiCAD**: Use `oasis-kicad` tools

---

## Getting Help

- **Documentation**: See `README.md` and `docs/` in each subdirectory
- **AI Agents**: Read [README_FOR_AI_AGENTS.md](README_FOR_AI_AGENTS.md)
- **GitHub**: [oasis-main/oasis-firmware](https://github.com/oasis-main/oasis-firmware)
