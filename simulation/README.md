# Oasis Simulation

Behavioral simulation runtime for Oasis firmware with MCP (Model Context Protocol) interface.

## Features

- **Component Library**: YAML-defined behavioral models for sensors and actuators
- **Behavioral Runtime**: Python runtime that executes component models
- **MCP Server**: AI-accessible API for simulation control
- **Fault Injection**: Test edge cases with disconnect, stuck, offset, and noise faults

## Quick Start

```bash
# Install
cd simulation
pip install -e .

# Run MCP server (stdio mode)
oasis-sim
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
