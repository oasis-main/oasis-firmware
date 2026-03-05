# Oasis Unified Simulation Architecture

## Overview

Oasis Simulation provides a **federated co-simulation framework** that unifies:
- MCU firmware emulation (ESP32, Arduino, STM32, RPi)
- Component behavioral models (sensors, actuators)
- Physical dynamics (thermal, mechanical via Modelica/FMI)
- Optional FEA integration (structural analysis)

All exposed via an **MCP server** for AI-assisted development and testing.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Server                               │
│              (JSON-RPC 2.0 over stdio/HTTP)                     │
│                                                                 │
│  Tools:                                                         │
│  • sim_start, sim_stop, sim_step                               │
│  • sim_inject_fault, sim_set_sensor_value                      │
│  • sim_get_state, sim_capture_waveform                         │
│  • component_add, component_list, component_describe           │
│  • datasheet_ingest (PDF → component model)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Simulation Orchestrator                       │
│                      (Rust + Python)                            │
│                                                                 │
│  • FMI 2.0/3.0 Master algorithm                                │
│  • Time synchronization (fixed-step / variable-step)           │
│  • Signal routing between simulators                           │
│  • Event handling (interrupts, GPIO edges)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  MCU Emulators │   │  Behavioral   │   │   Physical    │
│               │   │   Models      │   │   Models      │
│ • Wokwi/QEMU  │   │               │   │               │
│   (ESP32)     │   │ • Sensors     │   │ • Modelica    │
│ • Renode      │   │ • Actuators   │   │   FMUs        │
│   (STM32/ARM) │   │ • Protocols   │   │ • Thermal     │
│ • simavr      │   │   (I2C, SPI)  │   │ • Mechanical  │
│   (Arduino)   │   │               │   │               │
│ • mock_gpio   │   │ YAML DSL →    │   │ OpenModelica  │
│   (RPi)       │   │ Python runtime│   │ → FMU export  │
└───────────────┘   └───────────────┘   └───────────────┘
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Signal Bus (Shared Memory)                   │
│                                                                 │
│  GPIO[0..39], ADC[0..7], I2C_SDA, I2C_SCL, SPI_MOSI, ...       │
│  TEMP_AMBIENT, MOTOR_TORQUE, ENCLOSURE_TEMP, STRESS_MAX, ...   │
└─────────────────────────────────────────────────────────────────┘
```

## Key Concepts

### 1. Functional Mock-up Interface (FMI)

FMI is an industry standard (modelica-fmi.org) for model exchange and co-simulation.
Each component exports an **FMU** (Functional Mock-up Unit) - a ZIP containing:
- `modelDescription.xml` - Interface definition (inputs, outputs, parameters)
- Compiled binary or source code
- Optional resources (lookup tables, etc.)

**Why FMI?**
- Tool-agnostic: Modelica, Simulink, Python, C++ all export FMUs
- Standardized API: `fmi2DoStep()`, `fmi2GetReal()`, `fmi2SetReal()`
- Industry adoption: Automotive, aerospace, robotics

### 2. Co-Simulation Master

The orchestrator implements the FMI Master algorithm:

```python
while sim_time < end_time:
    # 1. Exchange signals between FMUs
    for connection in signal_connections:
        value = source_fmu.get(connection.source_var)
        target_fmu.set(connection.target_var, value)
    
    # 2. Step all FMUs forward
    for fmu in fmus:
        fmu.do_step(sim_time, step_size)
    
    # 3. Handle events (GPIO edges, interrupts)
    process_events()
    
    sim_time += step_size
```

### 3. Signal Bus

A shared memory region for signal exchange:

| Signal Type | Example | Resolution |
|-------------|---------|------------|
| Digital GPIO | `GPIO_4 = HIGH` | 1-bit |
| Analog ADC | `ADC_0 = 2.34V` | 12-bit (0-4095) |
| I2C Bus | `I2C_ADDR=0x76, DATA=[0x88, 0x00]` | Packet |
| Physical | `TEMP_AMBIENT = 25.3°C` | Float64 |
| Mechanical | `MOTOR_RPM = 1200` | Float64 |

### 4. Behavioral Component Models

YAML-defined models for sensors/actuators that don't need full circuit simulation:

```yaml
# components/dht22.yaml
component:
  id: dht22
  type: sensor
  protocol: single_wire
  
  inputs:
    - name: temp_actual
      type: float
      unit: "°C"
      source: physical  # From Modelica thermal model
    - name: humidity_actual
      type: float
      unit: "%"
      source: physical
      
  outputs:
    - name: data_pin
      type: digital
      protocol: dht_single_wire
      
  parameters:
    accuracy_temp: 0.5
    accuracy_humidity: 2.0
    read_interval_ms: 2000
    
  behavior:
    model: gaussian_noise
    on_read:
      - add_noise: { stddev: "${accuracy_temp}" }
      - quantize: { bits: 16 }
      - encode: dht_protocol
```

### 5. MCP Server Interface

Full simulation control via MCP tools:

```typescript
// Available MCP Tools
interface SimulationTools {
  // Lifecycle
  sim_start(config: DeviceYamlPath): SimulationId;
  sim_stop(sim_id: SimulationId): void;
  sim_step(sim_id: SimulationId, duration_ms: number): StepResult;
  
  // Observation
  sim_get_state(sim_id: SimulationId): FullState;
  sim_get_signal(sim_id: SimulationId, signal: string): SignalValue;
  sim_capture_waveform(sim_id: SimulationId, signals: string[], duration_ms: number): Waveform;
  
  // Injection
  sim_set_sensor_value(sim_id: SimulationId, sensor: string, value: number): void;
  sim_inject_fault(sim_id: SimulationId, fault: FaultSpec): void;
  sim_trigger_interrupt(sim_id: SimulationId, interrupt: string): void;
  
  // Component Library
  component_list(): ComponentInfo[];
  component_describe(id: string): ComponentSchema;
  component_add(yaml: string): ComponentId;
  
  // AI-Assisted
  datasheet_ingest(pdf_path: string): ComponentYaml;
  generate_test_suite(device_yaml: string): TestSuite;
}
```

## Simulation Modes

### Mode 1: Behavioral Only (Fast)
- No MCU emulation, just component models
- ~10,000x real-time
- Good for: Algorithm testing, data flow validation

### Mode 2: MCU + Behavioral (Standard)
- Full firmware execution + component models
- ~10-100x real-time
- Good for: Firmware development, integration testing

### Mode 3: Full Physics (Accurate)
- MCU + Behavioral + Modelica FMUs
- ~0.1-1x real-time
- Good for: Thermal validation, motor control tuning

### Mode 4: HIL (Hardware-in-the-Loop)
- Real MCU + simulated components
- Real-time
- Good for: Pre-deployment validation

## Implementation Phases

### Phase 1: Behavioral DSL + MCP Server (2 weeks)
- [ ] Define component YAML schema
- [ ] Implement Python behavioral runtime
- [ ] Build MCP server with simulation tools
- [ ] Create 10 common component models (DHT22, BME280, relay, etc.)

### Phase 2: MCU Emulator Integration (3 weeks)
- [ ] Renode wrapper for STM32
- [ ] simavr wrapper for Arduino/AVR
- [ ] QEMU-based ESP32 emulation (or Wokwi API)
- [ ] Signal bus bridging (GPIO ↔ behavioral models)

### Phase 3: FMI Co-Simulation (2 weeks)
- [ ] Integrate FMPy (Python FMI library)
- [ ] Export behavioral models as FMUs
- [ ] OpenModelica thermal/mechanical examples
- [ ] Co-simulation master algorithm

### Phase 4: Datasheet Ingestion (2 weeks)
- [ ] PDF parsing for datasheets
- [ ] AI-assisted parameter extraction
- [ ] Auto-generate component YAML from specs
- [ ] Validation against known components

## Directory Structure

```
oasis-firmware/
├── simulation/
│   ├── orchestrator/        # Rust co-simulation master
│   │   ├── src/
│   │   │   ├── main.rs
│   │   │   ├── fmi_master.rs
│   │   │   ├── signal_bus.rs
│   │   │   └── mcp_server.rs
│   │   └── Cargo.toml
│   ├── behavioral/          # Python behavioral runtime
│   │   ├── runtime.py
│   │   ├── protocols/
│   │   │   ├── i2c.py
│   │   │   ├── spi.py
│   │   │   └── single_wire.py
│   │   └── models/
│   ├── components/          # Component YAML definitions
│   │   ├── sensors/
│   │   │   ├── dht22.yaml
│   │   │   ├── bme280.yaml
│   │   │   └── scd40.yaml
│   │   ├── actuators/
│   │   │   ├── relay.yaml
│   │   │   └── servo.yaml
│   │   └── mcu/
│   │       ├── esp32.yaml
│   │       └── stm32f4.yaml
│   ├── emulators/           # MCU emulator wrappers
│   │   ├── renode/
│   │   ├── simavr/
│   │   └── qemu_esp32/
│   ├── modelica/            # Physical models
│   │   ├── thermal/
│   │   └── mechanical/
│   └── tests/
│       ├── test_cosim.py
│       └── fixtures/
```

## Example: Full System Simulation

```yaml
# device.yaml - Greenhouse controller
device:
  id: greenhouse-v2
  board: { platform: mcu, model: esp32_devkit }

sensors:
  - name: ambient_temp
    type: dht22
    pins: { data: 4 }
  - name: soil_moisture
    type: capacitive_soil
    pins: { adc: 34 }

actuators:
  - name: heater
    type: relay
    pins: { control: 5 }
  - name: pump
    type: relay
    pins: { control: 6 }

simulation:
  mode: full_physics
  
  physical_models:
    - type: thermal_zone
      name: greenhouse_enclosure
      initial_temp: 20.0
      heat_sources:
        - actuator: heater
          power_watts: 500
      heat_sinks:
        - type: ambient
          coefficient: 10.0  # W/°C
      connects_to:
        - sensor: ambient_temp
          
  test_scenarios:
    - name: cold_start
      initial_conditions:
        ambient: 5.0
      success_criteria:
        - after: 30min
          sensor: ambient_temp
          range: [18, 22]
```

Running the simulation:

```bash
# CLI
oasis-sim run --config device.yaml --scenario cold_start --duration 1h

# MCP (from AI assistant)
sim_id = sim_start("device.yaml")
sim_step(sim_id, 1800000)  # 30 minutes
state = sim_get_state(sim_id)
assert 18 <= state.sensors.ambient_temp <= 22
```

## References

- [FMI Standard](https://fmi-standard.org/)
- [Renode](https://renode.io/)
- [simavr](https://github.com/buserror/simavr)
- [OpenModelica](https://openmodelica.org/)
- [FMPy](https://github.com/CATIA-Systems/FMPy)
- [MCP Protocol](https://modelcontextprotocol.io/)
