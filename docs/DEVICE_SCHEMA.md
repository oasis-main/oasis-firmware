# Oasis Device Configuration Schema

This document defines the YAML schema for declarative device definitions. The `oasis-build` tool parses these files to generate Rust firmware for both MCU (ESP32, Arduino) and RPi platforms.

## Schema Overview

```
device.yaml
├── device           # Device identity and board config
├── connectivity     # Network/serial communication
├── auth             # Cloud authentication
├── sensors[]        # Sensor definitions
├── actuators[]      # Actuator definitions
├── control_loops[]  # On-device control logic
├── data_publishing  # MQTT/HTTPS output config
└── system           # Logging, watchdog, power, OTA
```

---

## Device Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device.id` | string | ✓ | Unique device identifier (e.g., `greenhouse-node-01`) |
| `device.name` | string | ✓ | Human-readable name |
| `device.board.platform` | enum | ✓ | `rpi` or `mcu` |
| `device.board.model` | string | ✓ | Board model (see supported boards below) |

### Supported Boards

**MCU Platform:**
- `esp32_devkit`, `esp32_c3`, `esp32_s3`
- `arduino_uno`, `arduino_mega`, `arduino_nano`
- `teensy_40`, `teensy_41`
- `stm32f103`, `stm32f411`

**RPi Platform:**
- `rpi_zero_w`, `rpi_zero_2w`
- `rpi_3b`, `rpi_4b`, `rpi_5`

---

## Connectivity Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `connectivity.mode` | enum | ✓ | `direct_mqtt`, `direct_https`, `serial_gateway`, `hybrid` |
| `connectivity.wifi.ssid` | string | * | WiFi SSID (supports `${ENV_VAR}` syntax) |
| `connectivity.wifi.password` | string | * | WiFi password (supports `${ENV_VAR}` syntax) |
| `connectivity.mqtt.broker` | string | * | MQTT broker hostname |
| `connectivity.mqtt.port` | integer | | Default: `8883` |
| `connectivity.mqtt.use_tls` | boolean | | Default: `true` |
| `connectivity.https.endpoint` | string | * | HTTPS endpoint URL |
| `connectivity.serial.baud_rate` | integer | | Default: `115200` |
| `connectivity.serial.protocol` | enum | | `cobs_msgpack`, `cobs_json`, `raw_json` |

*Required depending on connectivity mode

---

## Auth Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `auth.api_key` | string | ✓ | Device API key (supports `${ENV_VAR}` syntax) |
| `auth.source_id` | integer | | Pre-registered source ID in oasis-data |
| `auth.admin_id` | string | | Tenant admin ID for multi-tenant deployments |

---

## Sensors Section

Each sensor in the `sensors[]` array:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✓ | Unique sensor name within device |
| `type` | enum | ✓ | Sensor type (see supported sensors) |
| `pins` | object | ✓ | Pin configuration (varies by sensor) |
| `i2c_address` | integer | | I2C address (hex, e.g., `0x76`) |
| `sampling.interval_ms` | integer | ✓ | Sampling interval in milliseconds |
| `sampling.averaging` | integer | | Number of samples to average |
| `output.measurements[]` | array | ✓ | List of measurement outputs |
| `calibration.offset` | float | | Calibration offset |
| `calibration.scale` | float | | Calibration scale factor |
| `thresholds[]` | array | | Alert thresholds |

### Supported Sensor Types

| Category | Types |
|----------|-------|
| Temperature/Humidity | `dht11`, `dht22`, `bme280`, `bme680`, `sht31`, `ds18b20` |
| Light | `bh1750`, `tsl2561`, `veml7700`, `photoresistor` |
| Moisture | `capacitive_moisture`, `resistive_moisture` |
| Distance | `hcsr04`, `vl53l0x`, `vl53l1x` |
| Motion | `mpu6050`, `mpu9250`, `bno055`, `pir` |
| Gas/Air | `mq2`, `mq135`, `ccs811`, `sgp30` |
| Current/Voltage | `ina219`, `acs712`, `voltage_divider` |
| Weight | `hx711` |
| Camera | `esp_cam`, `rpi_camera` |
| Generic | `adc_raw`, `i2c_custom` |

### Pin Configuration

| Sensor Type | Required Pins |
|-------------|---------------|
| DHT11/22, DS18B20 | `data` |
| I2C sensors | `sda`, `scl` (or use board defaults) |
| HC-SR04 | `trigger`, `echo` |
| ADC sensors | `adc` (channel number) |

---

## Actuators Section

Each actuator in the `actuators[]` array:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✓ | Unique actuator name |
| `type` | enum | ✓ | Actuator type (see supported types) |
| `pins` | object | ✓ | Pin configuration |
| `default.state` | enum | | `on` or `off` |
| `default.value` | integer | | PWM value (0-255 or 0-100%) |
| `constraints.min_value` | integer | | Minimum output value |
| `constraints.max_value` | integer | | Maximum output value |
| `constraints.ramp_rate` | integer | | Max change per second |
| `safety.watchdog_timeout_ms` | integer | | Auto-off if no heartbeat |
| `safety.max_on_duration_ms` | integer | | Max continuous on time |

### Supported Actuator Types

| Category | Types |
|----------|-------|
| Digital | `relay`, `relay_nc`, `led`, `buzzer` |
| PWM | `pwm`, `servo`, `dc_motor` |
| Stepper | `stepper_a4988`, `stepper_drv8825`, `stepper_tmc2209` |
| I2C | `pca9685`, `mcp23017` |
| Communication | `rs485`, `modbus` |

---

## Control Loops Section

On-device control loops for low-latency automation:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✓ | Control loop name |
| `type` | enum | ✓ | `threshold`, `pid`, `schedule`, `state_machine` |
| `input.sensor` | string | ✓ | Input sensor name |
| `input.measurement` | string | ✓ | Which measurement to use |
| `output.actuator` | string | ✓ | Output actuator name |

### Threshold Control

```yaml
threshold:
  setpoint: 25.0
  hysteresis: 2.0
  direction: cool  # 'heat' or 'cool'
```

### PID Control

```yaml
pid:
  kp: 1.0
  ki: 0.1
  kd: 0.05
  setpoint: 25.0
  output_min: 0
  output_max: 255
  sample_time_ms: 1000
```

### Schedule Control

```yaml
schedule:
  - start_time: "06:00"
    end_time: "18:00"
    value: true
    days: [mon, tue, wed, thu, fri]
```

---

## Data Publishing Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mqtt.enabled` | boolean | | Enable MQTT publishing |
| `mqtt.telemetry_topic` | string | | Topic for sensor data |
| `mqtt.state_topic` | string | | Topic for state changes |
| `mqtt.cmd_topic` | string | | Topic for commands |
| `mqtt.publish_interval_ms` | integer | | Aggregation interval |
| `mqtt.qos` | integer | | MQTT QoS (0, 1, or 2) |
| `https.enabled` | boolean | | Enable HTTPS batching |
| `https.batch_interval_s` | integer | | Batch POST interval |
| `https.max_batch_size` | integer | | Max measurements per batch |
| `https.retry_count` | integer | | Retries on failure |
| `local_storage.enabled` | boolean | | Enable offline caching |
| `local_storage.max_records` | integer | | Ring buffer size |
| `local_storage.persist_on_reboot` | boolean | | Persist to flash |

---

## System Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `system.log_level` | enum | | `error`, `warn`, `info`, `debug`, `trace` |
| `system.watchdog.enabled` | boolean | | Enable hardware watchdog |
| `system.watchdog.timeout_ms` | integer | | Watchdog timeout |
| `system.power.sleep_mode` | enum | | `none`, `light`, `deep` |
| `system.power.wake_interval_ms` | integer | | Wake interval for deep sleep |
| `system.power.wake_on_interrupt` | array | | GPIO pins that wake device |
| `system.ota.enabled` | boolean | | Enable OTA updates |
| `system.ota.check_interval_s` | integer | | Update check interval |
| `system.ota.update_topic` | string | | MQTT topic for updates |

---

## Hardware/PCB Section (KiCAD Integration)

Link device configuration to physical PCB design:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `hardware.kicad_project` | string | | Path to `.kicad_pro` file |
| `hardware.symbols[]` | array | | Map components to schematic symbols |
| `hardware.connectors[]` | array | | Connector definitions |
| `hardware.housing` | object | | Enclosure configuration |
| `hardware.bom_overrides[]` | array | | BOM part number overrides |

### Symbol Mapping

```yaml
hardware:
  kicad_project: "./pcb/greenhouse-monitor.kicad_pro"
  symbols:
    - component: air_temp_humidity
      symbol_ref: "U1"
      footprint: "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
    - component: grow_light
      symbol_ref: "K1"
```

### Connectors

```yaml
  connectors:
    - name: "J1"
      connector_type: "screw_terminal_4p"
      signals: [VCC, GND, SOIL_ADC, NC]
      symbol_ref: "J1"
    - name: "J2"
      connector_type: "jst_xh_4"
      signals: [VCC, GND, SDA, SCL]
```

### Housing

```yaml
  housing:
    model: "ip65_abs_100x68x50"
    cad_file: "./enclosure/greenhouse-monitor.FCStd"
    ip_rating: "IP65"
    dimensions_mm: [100, 68, 50]
```

---

## Deployment Section

Configure flashing and deployment methods:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `deployment.flash_method` | enum | | `usb_serial`, `debug_probe`, `ota_mqtt`, `ota_https`, `ssh_rsync`, `docker` |
| `deployment.target_address` | string | | Device address (serial port or IP) |
| `deployment.ssh` | object | | SSH config for RPi deployment |
| `deployment.ota` | object | | OTA update configuration |

### USB Serial (ESP32)

```yaml
deployment:
  flash_method: usb_serial
  target_address: "/dev/ttyUSB0"
```

### SSH Deployment (RPi)

```yaml
deployment:
  flash_method: ssh_rsync
  ssh:
    host: "greenhouse-rpi.local"
    port: 22
    user: "oasis"
    key_path: "~/.ssh/oasis_deploy"
    install_dir: "/opt/oasis/greenhouse-node-01"
```

### OTA Updates

```yaml
deployment:
  flash_method: ota_mqtt
  ota:
    endpoint: "oasis/devices/${device.id}/ota"
    signing_key: "./keys/firmware_signing.pem"
    require_signature: true
```

---

## Environment Variable Substitution

Use `${ENV_VAR}` syntax for secrets:

```yaml
connectivity:
  wifi:
    ssid: "${WIFI_SSID}"
    password: "${WIFI_PASSWORD}"
auth:
  api_key: "${OASIS_API_KEY}"
```

The build tool will:
1. Substitute from environment at build time for MCU (compiled in)
2. Read from `.env` file at runtime for RPi
