# Oasis Firmware: Current State vs. Target Architecture

**Date:** November 23, 2024  
**Objective:** Transform firmware into modular "operating systems" with app-based interfaces for Raspberry Pi and Arduino platforms

---

## Executive Summary

**Current State:** Collection of monolithic scripts and Arduino sketches with hardcoded functionality  
**Target State:** Modular OS-like systems with app stores, runtime environments, and standardized interfaces

### Key Gaps Identified:
1. **No application framework** - Current code is project-specific, not app-based
2. **No runtime environment** - No OS layer to load/manage apps dynamically
3. **Limited abstraction** - Direct hardware access without HAL (Hardware Abstraction Layer)
4. **No app lifecycle management** - No install/uninstall/update mechanisms
5. **Minimal UI framework** - No Android-like interface for Pi display

---

## Current State Analysis

### Raspberry Pi (oasis-rpi)

#### What Exists:
- **Core System**: Python-based control system with PID loops, sensor reading, equipment control
- **API Layer**: `api.py` provides programmatic control (start/stop, set targets, read sensors)
- **Modular Structure**: 
  - `equipment/` - Relay control for heaters, fans, lights, etc.
  - `peripherals/` - Camera, buttons, displays
  - `networking/` - WiFi management, database tools
  - `imaging/` - Camera utilities, NDVI analysis
  - `utils/` - Concurrent state management, system tools
- **Configuration System**: JSON-based configs for features, hardware mapping, control parameters
- **Systemd Integration**: Background service capability
- **Arduino Communication**: Serial interface to read sensor data from Arduino "minions"

#### What's Missing:
- ❌ **App Framework**: No concept of installable/removable applications
- ❌ **App Store/Repository**: No mechanism to discover and install apps
- ❌ **Display UI Framework**: No touchscreen interface (currently headless or web-based only)
- ❌ **Sandboxing**: Apps would have full system access (security risk)
- ❌ **Package Manager**: No dependency management for apps
- ❌ **Runtime Isolation**: All code runs in single Python process
- ❌ **Hot-Reload**: System restart required for code changes

#### Architecture Pattern:
```
Current: Monolithic Python Application
├── main.py (orchestrates everything)
├── equipment/ (hardcoded equipment types)
├── peripherals/ (hardcoded peripherals)
└── configs/ (JSON configuration)

Target: Application Platform
├── oasis-os/ (core OS services)
│   ├── app-runtime/ (load/unload apps)
│   ├── hardware-abstraction/ (HAL for sensors/actuators)
│   ├── ui-framework/ (touchscreen interface)
│   └── package-manager/ (install/update apps)
└── apps/ (user-installable applications)
    ├── greenhouse-control/
    ├── timelapse-camera/
    └── environmental-monitor/
```

---

### Arduino (oasis-ino / oasis-mcu)

#### What Exists:
- **Code Standard**: `oasis-ino` defines a structured control flow protocol
  - Organized stages: Setup → Loop with timed sections
  - Sections: Sensor Reads → Processing → I/O → Communication → Housekeeping
- **Example Sketches**: Collection of `.ino` files in `oasis-rpi/minions/`
  - DHT22 + LEDs combinations
  - BME688, TDS, pH sensors
  - SCD30/SCD40 CO2 sensors
- **Platform Directories**: `oasis-ino/platforms/` and `oasis-mcu/platforms/` (mostly empty)
- **Communication Protocol**: Serial output of sensor data as JSON/dict format

#### What's Missing:
- ❌ **RTOS Integration**: No real-time operating system (bare metal only)
- ❌ **Task Scheduler**: Manual timing in loop() - no proper task management
- ❌ **App Loading**: Sketches must be compiled and flashed - no runtime app loading
- ❌ **OTA Updates**: No over-the-air firmware updates
- ❌ **Hardware Abstraction**: Direct pin access - no HAL
- ❌ **Module System**: No dynamic loading of sensor/actuator modules
- ❌ **Interrupt Management**: Basic interrupt handling only
- ❌ **Memory Management**: No dynamic memory allocation strategy

#### Architecture Pattern:
```
Current: Bare Metal Arduino Sketches
├── setup() - Initialize hardware
└── loop() - Sequential execution with delays

Target: FreeRTOS-Based Application Platform
├── FreeRTOS Kernel
├── Task Manager (concurrent tasks)
├── Hardware Abstraction Layer
├── App Runtime (load compiled modules)
├── Communication Stack (MQTT, Serial, WiFi)
└── OTA Update System
```

---

## Target Architecture

### Raspberry Pi: Android-Like Application Platform

#### Core OS Components:

**1. Oasis-OS Core**
- **Base**: Modified Debian/Raspbian (maintain compatibility)
- **Init System**: systemd with custom services
- **Display Server**: Wayland/Weston (lightweight, touch-optimized)
- **UI Framework**: 
  - Option A: Flutter (Dart) - Cross-platform, beautiful UIs
  - Option B: Qt/QML - Mature, C++/Python bindings
  - Option C: React Native - Web tech stack, large ecosystem
  - **Recommendation**: **Flutter** - Best balance of performance, beauty, and ease

**2. Application Runtime**
```python
# Conceptual API
class OasisApp:
    def __init__(self, manifest):
        self.name = manifest['name']
        self.permissions = manifest['permissions']
        self.hardware_requirements = manifest['hardware']
    
    def on_install(self): pass
    def on_start(self): pass
    def on_stop(self): pass
    def on_uninstall(self): pass

class AppManager:
    def install_app(self, package_path)
    def uninstall_app(self, app_id)
    def start_app(self, app_id)
    def stop_app(self, app_id)
    def list_apps(self)
```

**3. Hardware Abstraction Layer (HAL)**
```python
# Unified interface for all hardware
class HardwareInterface:
    def get_gpio_controller(self) -> GPIOController
    def get_serial_port(self, port) -> SerialPort
    def get_camera(self) -> Camera
    def get_display(self) -> Display
    def get_sensor(self, sensor_type) -> Sensor
    def get_actuator(self, actuator_type) -> Actuator
```

**4. UI Framework**
- **Home Screen**: Grid of installed apps with icons
- **Status Bar**: System info (WiFi, temp, time)
- **Settings App**: System configuration
- **App Store**: Browse and install apps
- **Notification System**: Alerts and status updates

**5. Package Manager**
- **Format**: `.oasis` packages (tar.gz with manifest)
- **Manifest**: JSON with metadata, dependencies, permissions
- **Repository**: Central app repository (hosted or local)
- **Versioning**: Semantic versioning with update checks

#### Example Apps:

**Greenhouse Control App**
```
greenhouse-control/
├── manifest.json
├── main.py (app entry point)
├── ui/ (Flutter/Qt UI files)
├── controllers/ (PID, scheduling)
└── assets/ (icons, images)
```

**Timelapse Camera App**
```
timelapse-camera/
├── manifest.json
├── main.py
├── ui/
├── capture.py
└── video_generator.py
```

---

### Arduino: FreeRTOS-Based Modular Platform

#### Why FreeRTOS?

**Pros:**
- ✅ **Industry Standard**: Used in millions of devices
- ✅ **Preemptive Multitasking**: True concurrent task execution
- ✅ **Small Footprint**: Runs on ATmega328P (Arduino Uno) with 32KB flash
- ✅ **Rich Ecosystem**: Queues, semaphores, timers, event groups
- ✅ **Arduino Compatible**: Can use existing Arduino libraries
- ✅ **Active Development**: Well-maintained, extensive documentation

**Cons:**
- ⚠️ **Learning Curve**: More complex than bare Arduino
- ⚠️ **Memory Overhead**: ~2-4KB RAM for kernel (tight on Uno)
- ⚠️ **Debugging**: Harder to debug than simple loop()

**Alternatives Considered:**
- **Zephyr RTOS**: More features but larger footprint, less Arduino-friendly
- **Mbed OS**: Good but ARM-focused, limited AVR support
- **ChibiOS**: Lightweight but smaller community
- **Bare Metal**: Current approach - no multitasking

**Recommendation**: **FreeRTOS** for ESP32/SAMD21, **Cooperative Scheduler** for ATmega328P

#### Core Architecture:

**1. Task-Based Design**
```cpp
// FreeRTOS tasks replace loop sections
void TaskSensorRead(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    for(;;) {
        readSensors();
        vTaskDelayUntil(&xLastWakeTime, pdMS_TO_TICKS(1000)); // 1Hz
    }
}

void TaskActuatorControl(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    for(;;) {
        updateActuators();
        vTaskDelayUntil(&xLastWakeTime, pdMS_TO_TICKS(100)); // 10Hz
    }
}

void TaskCommunication(void *pvParameters) {
    for(;;) {
        sendDataToRPi();
        vTaskDelay(pdMS_TO_TICKS(5000)); // 0.2Hz
    }
}
```

**2. Hardware Abstraction Layer**
```cpp
class Sensor {
public:
    virtual float read() = 0;
    virtual bool isAvailable() = 0;
};

class DHT22Sensor : public Sensor {
    float read() override { /* DHT22-specific code */ }
    bool isAvailable() override { return dht.begin(); }
};

class SensorManager {
    void registerSensor(String name, Sensor* sensor);
    float readSensor(String name);
    void listSensors();
};
```

**3. Module System**
```cpp
// Modules are compiled into firmware but can be enabled/disabled
struct Module {
    const char* name;
    void (*init)();
    void (*task)(void*);
    bool enabled;
};

Module modules[] = {
    {"DHT22", initDHT22, TaskDHT22, true},
    {"LEDs", initLEDs, TaskLEDs, true},
    {"TDS", initTDS, TaskTDS, false},
};

void loadModules() {
    for(auto& mod : modules) {
        if(mod.enabled) {
            mod.init();
            xTaskCreate(mod.task, mod.name, 128, NULL, 1, NULL);
        }
    }
}
```

**4. Configuration System**
```cpp
// EEPROM-based configuration
struct Config {
    bool moduleDHT22Enabled;
    bool moduleLEDsEnabled;
    uint16_t sensorReadInterval;
    uint16_t commInterval;
    // ... more settings
};

void loadConfig();
void saveConfig();
void setConfigValue(String key, String value); // Via serial commands
```

**5. OTA Update Support (ESP32/ESP8266)**
```cpp
#ifdef ESP32
#include <Update.h>
void checkForUpdates() {
    // HTTP client to fetch firmware
    // Update.begin()
    // Update.writeStream()
    // Update.end()
}
#endif
```

---

## Implementation Roadmap

### Phase 1: Foundation (Months 1-2)

#### Raspberry Pi:
- [ ] **Design app manifest format** (JSON schema)
- [ ] **Create HAL for GPIO, Serial, Camera** (Python abstraction layer)
- [ ] **Build basic AppManager** (install/uninstall/start/stop)
- [ ] **Set up UI framework** (Flutter or Qt)
- [ ] **Create home screen** (app launcher)
- [ ] **Port 1-2 existing functions as apps** (e.g., greenhouse control, timelapse)

#### Arduino:
- [ ] **Evaluate FreeRTOS on target boards** (ESP32, SAMD21, ATmega328P)
- [ ] **Create HAL for sensors/actuators** (C++ abstraction)
- [ ] **Port 1 existing sketch to FreeRTOS tasks** (e.g., DHT22 + LEDs)
- [ ] **Design module system** (enable/disable modules)
- [ ] **Implement EEPROM config storage**

### Phase 2: Core Features (Months 3-4)

#### Raspberry Pi:
- [ ] **Build app store UI** (browse/install apps)
- [ ] **Create package repository** (local or cloud-based)
- [ ] **Implement permissions system** (hardware access control)
- [ ] **Add settings app** (system configuration UI)
- [ ] **Create 3-5 example apps** (showcase capabilities)
- [ ] **Documentation for app developers**

#### Arduino:
- [ ] **Port all existing sketches to modular format**
- [ ] **Implement task priorities and scheduling**
- [ ] **Add inter-task communication** (queues, semaphores)
- [ ] **Create serial command protocol** (enable/disable modules remotely)
- [ ] **OTA updates for ESP32/ESP8266**

### Phase 3: Polish & Ecosystem (Months 5-6)

#### Raspberry Pi:
- [ ] **Optimize UI performance** (smooth animations, fast loading)
- [ ] **Add app sandboxing** (security isolation)
- [ ] **Create developer SDK** (templates, testing tools)
- [ ] **Build CI/CD for app packaging**
- [ ] **Community app submissions**

#### Arduino:
- [ ] **Power management** (sleep modes, battery optimization)
- [ ] **Watchdog integration** (auto-recovery from crashes)
- [ ] **Logging and diagnostics** (debug over serial)
- [ ] **Performance profiling** (task timing, memory usage)
- [ ] **Documentation and examples**

---

## Technical Decisions

### Raspberry Pi UI Framework Comparison

| Framework | Pros | Cons | Recommendation |
|-----------|------|------|----------------|
| **Flutter** | Beautiful UIs, fast, hot reload, Dart | Learning curve, larger binaries | ⭐ **Best Choice** |
| **Qt/QML** | Mature, C++ performance, Python bindings | Licensing (GPL/Commercial), heavier | Good alternative |
| **React Native** | Web skills, huge ecosystem | Performance overhead, not native | For web devs only |
| **Kivy** | Python-native, simple | Less polished, smaller community | Quick prototyping |

### Arduino RTOS Comparison

| RTOS | Pros | Cons | Recommendation |
|------|------|------|----------------|
| **FreeRTOS** | Industry standard, Arduino support, small | Learning curve | ⭐ **Best for ESP32/SAMD21** |
| **Zephyr** | Modern, feature-rich | Large footprint, complex | Overkill for Arduino |
| **Cooperative Scheduler** | Simple, tiny footprint | No true multitasking | ⭐ **Best for ATmega328P** |
| **Bare Metal** | Full control, no overhead | Manual everything | Current state (not scalable) |

---

## Example: Greenhouse Control App

### Raspberry Pi App Structure

```
greenhouse-control/
├── manifest.json
├── main.py
├── ui/
│   ├── home_screen.dart (Flutter)
│   ├── settings_screen.dart
│   └── charts_screen.dart
├── controllers/
│   ├── pid_controller.py
│   ├── scheduler.py
│   └── data_logger.py
├── models/
│   ├── sensor_data.py
│   └── control_params.py
└── assets/
    ├── icon.png
    └── splash.png
```

**manifest.json:**
```json
{
  "name": "Greenhouse Control",
  "version": "1.0.0",
  "author": "Oasis-X",
  "description": "Automated greenhouse climate control",
  "permissions": [
    "gpio.read",
    "gpio.write",
    "serial.read",
    "camera.access"
  ],
  "hardware_requirements": {
    "gpio_pins": [14, 15, 18, 23, 24, 25],
    "serial_ports": ["/dev/ttyUSB0"]
  },
  "dependencies": {
    "numpy": ">=1.20.0",
    "matplotlib": ">=3.3.0"
  },
  "entry_point": "main.py",
  "ui_entry": "ui/home_screen.dart"
}
```

### Arduino Module Structure

```cpp
// modules/dht22_module.h
#ifndef DHT22_MODULE_H
#define DHT22_MODULE_H

#include "module_interface.h"
#include <DHT.h>

class DHT22Module : public Module {
private:
    DHT dht;
    float temperature;
    float humidity;
    
public:
    DHT22Module(uint8_t pin) : dht(pin, DHT22) {}
    
    void init() override {
        dht.begin();
    }
    
    void task(void* params) override {
        TickType_t xLastWakeTime = xTaskGetTickCount();
        for(;;) {
            temperature = dht.readTemperature();
            humidity = dht.readHumidity();
            
            // Publish to data bus
            publishData("temperature", temperature);
            publishData("humidity", humidity);
            
            vTaskDelayUntil(&xLastWakeTime, pdMS_TO_TICKS(2000));
        }
    }
    
    const char* getName() override { return "DHT22"; }
};

#endif
```

---

## Resource Requirements

### Development Resources:
- **Raspberry Pi 4 (4GB+)**: For UI development and testing
- **ESP32 Dev Boards**: FreeRTOS testing (better than Uno for RTOS)
- **Arduino Uno/Nano**: Cooperative scheduler testing
- **Touchscreen Display**: 7" HDMI or DSI display for Pi
- **Development Time**: 6 months (1-2 developers)

### Runtime Requirements:
- **Raspberry Pi**: 
  - Pi 3B+ minimum (Pi 4 recommended)
  - 16GB+ SD card
  - Official 7" touchscreen or HDMI display
- **Arduino**:
  - ESP32 (recommended): 520KB RAM, 4MB flash
  - SAMD21 (Nano 33 IoT): 32KB RAM, 256KB flash
  - ATmega328P (Uno): 2KB RAM, 32KB flash (tight!)

---

## Next Steps

### Immediate Actions:
1. **Prototype Flutter UI** on Raspberry Pi (1 week)
   - Install Flutter SDK
   - Create basic home screen with app grid
   - Test touch input and performance

2. **FreeRTOS Proof-of-Concept** on ESP32 (1 week)
   - Port DHT22 sketch to FreeRTOS tasks
   - Implement sensor task + LED task + communication task
   - Measure memory usage and performance

3. **Define App Manifest Schema** (3 days)
   - JSON structure for app metadata
   - Permission system design
   - Hardware requirements format

4. **Create HAL Prototype** (1 week)
   - Python GPIO abstraction
   - C++ sensor abstraction
   - Test with existing hardware

### Decision Points:
- ✅ **Confirm UI framework**: Flutter vs Qt vs React Native
- ✅ **Confirm RTOS strategy**: FreeRTOS for ESP32, cooperative for Uno
- ✅ **Confirm app packaging format**: .oasis (tar.gz) vs custom binary
- ✅ **Confirm repository hosting**: Self-hosted vs cloud (GitHub releases?)

---

## Conclusion

**Current State**: Functional but monolithic systems with hardcoded functionality  
**Target State**: Modular OS platforms with app ecosystems

**Key Transformations:**
1. **Raspberry Pi**: Headless Python scripts → Android-like touchscreen OS with app store
2. **Arduino**: Bare metal sketches → FreeRTOS-based modular platform with HAL

**Feasibility**: ✅ **Achievable in 6 months** with focused development

**Biggest Challenges:**
- UI framework learning curve (Flutter/Qt)
- FreeRTOS memory constraints on ATmega328P
- App sandboxing and security
- Developer documentation and ecosystem building

**Recommended Starting Point**: 
- **Week 1**: Flutter UI prototype on Pi + FreeRTOS proof-of-concept on ESP32
- **Week 2**: HAL design and basic app manager
- **Week 3**: Port one existing project as first app

This roadmap transforms oasis-firmware from a collection of scripts into a true embedded application platform. 🚀
