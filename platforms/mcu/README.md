# Oasis MCU

**Intelligent compile-time multi-app system for Arduino and microcontrollers.**

---

## Overview

Oasis MCU provides a build system that compiles selected apps into a single firmware binary with intelligent features:

- **Single app mode**: Direct boot with no menu overhead
- **Multi-app mode**: Includes menu system for app switching
- **Flash safety**: Fails before compile if flash overflow detected
- **Cross-platform**: Arduino Uno, ESP32, Nano 33 IoT, STM32

---

## Quick Start

### 1. List Available Apps

```bash
cd oasis-mcu
python build.py --platform atmega328p_uno --list-apps
```

### 2. Build Single App (No Menu)

```bash
python build.py --platform atmega328p_uno --apps greenhouse_sensors
```

### 3. Build Multi-App (With Menu)

```bash
python build.py --platform atmega328p_uno --apps greenhouse_sensors,led_controller
```

### 4. Flash to Board

```bash
python build.py --platform atmega328p_uno --apps greenhouse_sensors --port /dev/ttyUSB0 --flash
```

---

## Directory Structure

```
oasis-mcu/
├── platforms/
│   ├── atmega328p_uno/          # Arduino Uno (32KB flash)
│   │   ├── greenhouse_sensors/
│   │   │   ├── manifest.json
│   │   │   └── app.ino
│   │   └── led_controller/
│   │
│   ├── esp32_devkit/            # ESP32 (4MB flash)
│   │   └── wifi_sensor_hub/
│   │
│   └── stm32f103/               # STM32 Blue Pill
│       └── ...
│
├── core/
│   ├── menu_system.h            # Menu implementation
│   ├── menu_system.cpp
│   ├── app_interface.h          # App contract
│   └── serial_protocol.h        # Serial control protocol
│
├── build.py                     # Main build script
├── templates/                   # Code generation templates
└── build/                       # Generated files (gitignored)
```

---

## Platform Specifications

| Platform | Flash | RAM | FQBN |
|----------|-------|-----|------|
| `atmega328p_uno` | 32KB | 2KB | `arduino:avr:uno` |
| `esp32_devkit` | 4MB | 520KB | `esp32:esp32:esp32` |
| `samd21_nano33iot` | 256KB | 32KB | `arduino:samd:nano_33_iot` |
| `stm32f103` | 64KB | 20KB | `STMicroelectronics:stm32:GenF1` |

---

## Creating an App

### 1. Create App Directory

```bash
mkdir -p platforms/atmega328p_uno/my_sensor
```

### 2. Create manifest.json

```json
{
  "name": "My Sensor",
  "version": "1.0.0",
  "description": "Reads temperature and humidity",
  "author": "Your Name",
  
  "resources": {
    "flash_size_kb": 8,
    "ram_size_kb": 1
  },
  
  "dependencies": {
    "libraries": [
      {"name": "DHT", "version": ">=1.4.0"}
    ]
  },
  
  "hardware": {
    "pins_used": [2, 5],
    "serial_required": true
  },
  
  "menu": {
    "display_name": "My Sensor",
    "icon": "🌡️",
    "category": "sensors"
  }
}
```

### 3. Create app.ino

```cpp
#include <DHT.h>

#define DHTPIN 2
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

// Required: Setup function
void my_sensor_setup() {
    Serial.begin(9600);
    dht.begin();
    Serial.println("My Sensor initialized");
}

// Required: Loop function
void my_sensor_loop() {
    float temp = dht.readTemperature();
    float humidity = dht.readHumidity();
    
    Serial.print("{\"temperature\":");
    Serial.print(temp);
    Serial.print(",\"humidity\":");
    Serial.print(humidity);
    Serial.println("}");
    
    delay(2000);
}

// Required: Cleanup function (for multi-app mode)
void my_sensor_cleanup() {
    Serial.println("My Sensor shutting down");
}
```

**Important**: Function names must follow the pattern `{app_name}_setup`, `{app_name}_loop`, `{app_name}_cleanup`.

---

## Build Script Options

```bash
python build.py --help

Options:
  --platform      Target platform (required)
  --apps          Comma-separated app names
  --list-apps     List available apps for platform
  --info          Show platform specifications
  --dry-run       Check sizes without compiling
  --port          Serial port for flashing
  --flash         Flash after compilation
```

### Examples

```bash
# Check flash usage
python build.py --platform atmega328p_uno --apps app1,app2,app3 --dry-run

# Show platform info
python build.py --platform esp32_devkit --info

# Build and flash
python build.py --platform atmega328p_uno --apps greenhouse_sensors --port /dev/ttyUSB0 --flash
```

---

## Menu System

When multiple apps are compiled, the menu system is automatically included (~2KB overhead).

### Serial Commands

| Command | Description |
|---------|-------------|
| `scroll_forward` | Select next app |
| `scroll_backward` | Select previous app |
| `select` | Launch selected app |
| `back` / `exit` | Return to menu |

### JSON Status Messages

```json
// Menu state
{"type": "menu_state", "selected": 0, "app": "Greenhouse Sensors"}

// App running
{"type": "app_running", "app": "Greenhouse Sensors"}

// App exited
{"type": "app_exited", "app": "Greenhouse Sensors"}
```

---

## Dependencies

- Python 3.8+
- arduino-cli (install from https://arduino.github.io/arduino-cli/)
- Platform-specific Arduino cores

### Install arduino-cli

```bash
# macOS
brew install arduino-cli

# Linux
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

# Install cores
arduino-cli core install arduino:avr
arduino-cli core install esp32:esp32
arduino-cli core install arduino:samd
```

---

## Troubleshooting

### Flash Overflow

```
Build Error: Flash overflow! Apps require 35KB but only 32KB available
```

**Solution**: Remove apps or optimize code. Use `--dry-run` to check sizes before compiling.

### Missing Library

```
fatal error: DHT.h: No such file or directory
```

**Solution**: Install required library:
```bash
arduino-cli lib install "DHT sensor library"
```

### Port Not Found

```
Error: No serial port detected
```

**Solution**: 
- Check USB connection
- Verify port with `ls /dev/tty*` (Linux/macOS) or Device Manager (Windows)
- May need to install USB-to-serial drivers

---

## Documentation

- [BUILD_SYSTEM_SPEC.md](BUILD_SYSTEM_SPEC.md) - Full build system specification
- [../README_FOR_AI_AGENTS.md](../README_FOR_AI_AGENTS.md) - AI agent guide

---

## License

MIT License for a variety of platforms
