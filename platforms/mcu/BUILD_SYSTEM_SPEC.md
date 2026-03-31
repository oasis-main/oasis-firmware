# Arduino Build System Specification

**Purpose**: Intelligent compile-time app loading for Arduino platforms

---

## Overview

The build system compiles selected apps into a single firmware binary:
- **Single app**: Direct boot (no menu overhead)
- **Multiple apps**: Includes menu system for switching
- **Safety**: Fails before compile if flash overflow detected

---

## Directory Structure

```
oasis-mcu/
├── platforms/
│   ├── atmega328p_uno/          # Arduino Uno (32KB flash)
│   │   ├── greenhouse_sensors/
│   │   │   ├── manifest.json
│   │   │   └── app.ino
│   │   ├── led_controller/
│   │   └── timelapse_trigger/
│   │
│   ├── esp32_devkit/            # ESP32 (4MB flash)
│   │   ├── wifi_sensor_hub/
│   │   └── camera_trigger/
│   │
│   └── samd21_nano33iot/        # Nano 33 IoT (256KB flash)
│       ├── iot_gateway/
│       └── bluetooth_sensor/
│
├── core/
│   ├── menu_system.h            # Menu implementation
│   ├── menu_system.cpp
│   ├── app_interface.h          # App contract
│   └── serial_protocol.h        # Serial control protocol
│
├── build.py                     # Main build script
├── templates/
│   ├── main_single.ino.template # Single-app template
│   └── main_menu.ino.template   # Multi-app template
│
└── build/                       # Generated files (gitignored)
    └── {platform}/
        ├── main.ino
        └── compiled.hex
```

---

## App Manifest Format

**File**: `platforms/{platform}/{app_name}/manifest.json`

```json
{
  "name": "Greenhouse Sensors",
  "version": "1.2.0",
  "description": "DHT22 + soil moisture monitoring",
  "author": "Oasis-X",
  
  "resources": {
    "flash_size_kb": 8,
    "ram_size_kb": 1,
    "eeprom_bytes": 0
  },
  
  "dependencies": {
    "libraries": [
      {"name": "DHT", "version": ">=1.4.0"},
      {"name": "Adafruit_Sensor", "version": ">=1.1.0"}
    ]
  },
  
  "hardware": {
    "pins_used": [2, 5, 7],
    "serial_required": true,
    "i2c_required": false,
    "spi_required": false
  },
  
  "menu": {
    "display_name": "Greenhouse",
    "icon": "🌱",
    "category": "sensors"
  }
}
```

---

## App Interface Contract

**File**: `platforms/{platform}/{app_name}/app.ino`

### Required Functions

```cpp
// Setup function - called once when app starts
void {app_name}_setup() {
    // Initialize hardware
    // Set pin modes
    // Begin serial communication
    // Initialize sensors
}

// Loop function - called repeatedly while app is running
void {app_name}_loop() {
    // Read sensors
    // Process data
    // Control actuators
    // Communicate with RPi
}

// Cleanup function - called when exiting to menu (multi-app mode only)
void {app_name}_cleanup() {
    // Turn off actuators
    // Release resources
    // Save state to EEPROM if needed
}
```

### Example App

```cpp
// platforms/atmega328p_uno/greenhouse_sensors/app.ino

#include <DHT.h>

#define DHTPIN 2
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

float temperature = 0;
float humidity = 0;

void greenhouse_sensors_setup() {
    Serial.begin(9600);
    dht.begin();
    Serial.println("Greenhouse sensors initialized");
}

void greenhouse_sensors_loop() {
    temperature = dht.readTemperature();
    humidity = dht.readHumidity();
    
    // Send data as JSON
    Serial.print("{\"temperature\":");
    Serial.print(temperature);
    Serial.print(",\"humidity\":");
    Serial.print(humidity);
    Serial.println("}");
    
    delay(2000);
}

void greenhouse_sensors_cleanup() {
    Serial.println("Greenhouse sensors shutting down");
}
```

---

## Build Script (build.py)

### Usage

```bash
# Build single app (no menu)
python build.py --platform atmega328p_uno --apps greenhouse_sensors

# Build multiple apps (with menu)
python build.py --platform atmega328p_uno --apps greenhouse_sensors,led_controller

# Dry run (check sizes without compiling)
python build.py --platform atmega328p_uno --apps app1,app2,app3 --dry-run

# Flash after build
python build.py --platform atmega328p_uno --apps greenhouse_sensors --port /dev/ttyUSB0 --flash

# List available apps for platform
python build.py --platform atmega328p_uno --list-apps

# Show platform specs
python build.py --platform atmega328p_uno --info
```

### Implementation

```python
#!/usr/bin/env python3
"""
Oasis MCU Build System
Compiles selected apps into single Arduino firmware
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict

# Platform specifications
PLATFORMS = {
    "atmega328p_uno": {
        "fqbn": "arduino:avr:uno",
        "flash_kb": 32,
        "ram_kb": 2,
        "eeprom_bytes": 1024,
    },
    "esp32_devkit": {
        "fqbn": "esp32:esp32:esp32",
        "flash_kb": 4096,
        "ram_kb": 520,
        "eeprom_bytes": 0,
    },
    "samd21_nano33iot": {
        "fqbn": "arduino:samd:nano_33_iot",
        "flash_kb": 256,
        "ram_kb": 32,
        "eeprom_bytes": 0,
    }
}

MENU_OVERHEAD_KB = 2  # Estimated menu system size

class BuildError(Exception):
    pass

class App:
    def __init__(self, platform: str, name: str):
        self.platform = platform
        self.name = name
        self.path = Path(f"platforms/{platform}/{name}")
        
        # Load manifest
        manifest_path = self.path / "manifest.json"
        if not manifest_path.exists():
            raise BuildError(f"Manifest not found: {manifest_path}")
        
        with open(manifest_path) as f:
            self.manifest = json.load(f)
        
        # Validate app.ino exists
        self.ino_path = self.path / "app.ino"
        if not self.ino_path.exists():
            raise BuildError(f"App file not found: {self.ino_path}")
    
    @property
    def flash_size_kb(self) -> float:
        return self.manifest.get("resources", {}).get("flash_size_kb", 0)
    
    @property
    def display_name(self) -> str:
        return self.manifest.get("menu", {}).get("display_name", self.name)
    
    @property
    def setup_func(self) -> str:
        return f"{self.name}_setup"
    
    @property
    def loop_func(self) -> str:
        return f"{self.name}_loop"
    
    @property
    def cleanup_func(self) -> str:
        return f"{self.name}_cleanup"

def load_apps(platform: str, app_names: List[str]) -> List[App]:
    """Load app objects from names"""
    apps = []
    for name in app_names:
        try:
            apps.append(App(platform, name))
        except BuildError as e:
            print(f"Error loading app '{name}': {e}")
            sys.exit(1)
    return apps

def check_flash_size(platform: str, apps: List[App], include_menu: bool) -> None:
    """Check if apps fit in flash memory"""
    platform_spec = PLATFORMS[platform]
    available_kb = platform_spec["flash_kb"]
    
    # Calculate total size
    app_size = sum(app.flash_size_kb for app in apps)
    menu_size = MENU_OVERHEAD_KB if include_menu else 0
    total_size = app_size + menu_size
    
    print(f"\nFlash Memory Analysis:")
    print(f"  Platform: {platform} ({available_kb}KB total)")
    print(f"  Apps: {app_size}KB")
    if include_menu:
        print(f"  Menu System: {menu_size}KB")
    print(f"  Total: {total_size}KB")
    print(f"  Available: {available_kb}KB")
    print(f"  Remaining: {available_kb - total_size}KB")
    
    if total_size > available_kb:
        raise BuildError(
            f"Flash overflow! Apps require {total_size}KB but only {available_kb}KB available"
        )
    
    if total_size > available_kb * 0.9:
        print("  ⚠️  Warning: Using >90% of flash memory")

def generate_single_app_main(app: App, build_dir: Path) -> None:
    """Generate main.ino for single app (no menu)"""
    template = f"""
// Auto-generated by Oasis Build System
// Single app mode: {app.display_name}

#include "{app.ino_path.relative_to(Path.cwd())}"

void setup() {{
    {app.setup_func}();
}}

void loop() {{
    {app.loop_func}();
}}
"""
    
    main_path = build_dir / "main.ino"
    with open(main_path, 'w') as f:
        f.write(template)
    
    print(f"Generated single-app main.ino")

def generate_menu_main(apps: List[App], build_dir: Path) -> None:
    """Generate main.ino for multi-app with menu"""
    
    # Include statements
    includes = "\n".join(
        f'#include "{app.ino_path.relative_to(Path.cwd())}"'
        for app in apps
    )
    
    # App registrations
    registrations = "\n    ".join(
        f'menu.registerApp("{app.display_name}", {app.setup_func}, {app.loop_func}, {app.cleanup_func});'
        for app in apps
    )
    
    template = f"""
// Auto-generated by Oasis Build System
// Multi-app mode with menu

#include "core/menu_system.h"
{includes}

OasisMenuSystem menu;

void setup() {{
    Serial.begin(9600);
    
    // Register apps
    {registrations}
    
    menu.begin();
}}

void loop() {{
    menu.update();
}}
"""
    
    main_path = build_dir / "main.ino"
    with open(main_path, 'w') as f:
        f.write(template)
    
    print(f"Generated multi-app main.ino with {len(apps)} apps")

def compile_firmware(platform: str, build_dir: Path) -> Path:
    """Compile firmware using arduino-cli"""
    platform_spec = PLATFORMS[platform]
    fqbn = platform_spec["fqbn"]
    
    print(f"\nCompiling for {platform}...")
    
    cmd = [
        "arduino-cli", "compile",
        "--fqbn", fqbn,
        "--build-path", str(build_dir),
        str(build_dir / "main.ino")
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Compilation failed:")
        print(result.stderr)
        raise BuildError("Compilation failed")
    
    print("Compilation successful!")
    
    # Find compiled hex file
    hex_file = build_dir / "main.ino.hex"
    if not hex_file.exists():
        raise BuildError("Compiled hex file not found")
    
    return hex_file

def flash_firmware(platform: str, port: str, hex_file: Path) -> None:
    """Flash firmware to Arduino"""
    platform_spec = PLATFORMS[platform]
    fqbn = platform_spec["fqbn"]
    
    print(f"\nFlashing to {port}...")
    
    cmd = [
        "arduino-cli", "upload",
        "--fqbn", fqbn,
        "--port", port,
        "--input-file", str(hex_file)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Flashing failed:")
        print(result.stderr)
        raise BuildError("Flashing failed")
    
    print("Flashing successful!")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Oasis MCU Build System")
    parser.add_argument("--platform", required=True, choices=PLATFORMS.keys())
    parser.add_argument("--apps", help="Comma-separated app names")
    parser.add_argument("--list-apps", action="store_true", help="List available apps")
    parser.add_argument("--info", action="store_true", help="Show platform info")
    parser.add_argument("--dry-run", action="store_true", help="Check sizes without compiling")
    parser.add_argument("--port", help="Serial port for flashing")
    parser.add_argument("--flash", action="store_true", help="Flash after compile")
    
    args = parser.parse_args()
    
    # List apps
    if args.list_apps:
        platform_dir = Path(f"platforms/{args.platform}")
        apps = [d.name for d in platform_dir.iterdir() if d.is_dir()]
        print(f"Available apps for {args.platform}:")
        for app in apps:
            print(f"  - {app}")
        return
    
    # Show platform info
    if args.info:
        spec = PLATFORMS[args.platform]
        print(f"Platform: {args.platform}")
        print(f"  FQBN: {spec['fqbn']}")
        print(f"  Flash: {spec['flash_kb']}KB")
        print(f"  RAM: {spec['ram_kb']}KB")
        print(f"  EEPROM: {spec['eeprom_bytes']} bytes")
        return
    
    # Build firmware
    if not args.apps:
        parser.error("--apps required for build")
    
    app_names = [name.strip() for name in args.apps.split(",")]
    apps = load_apps(args.platform, app_names)
    
    print(f"\nBuilding firmware for {args.platform}")
    print(f"Apps: {', '.join(app.display_name for app in apps)}")
    
    # Check flash size
    include_menu = len(apps) > 1
    check_flash_size(args.platform, apps, include_menu)
    
    if args.dry_run:
        print("\nDry run complete - no compilation performed")
        return
    
    # Create build directory
    build_dir = Path(f"build/{args.platform}")
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate main.ino
    if len(apps) == 1:
        generate_single_app_main(apps[0], build_dir)
    else:
        generate_menu_main(apps, build_dir)
    
    # Compile
    hex_file = compile_firmware(args.platform, build_dir)
    print(f"\nFirmware ready: {hex_file}")
    
    # Flash if requested
    if args.flash:
        if not args.port:
            parser.error("--port required for flashing")
        flash_firmware(args.platform, args.port, hex_file)

if __name__ == "__main__":
    try:
        main()
    except BuildError as e:
        print(f"\nBuild Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBuild cancelled")
        sys.exit(1)
```

---

## Menu System Implementation

**File**: `core/menu_system.h`

```cpp
#ifndef OASIS_MENU_SYSTEM_H
#define OASIS_MENU_SYSTEM_H

#include <Arduino.h>

struct OasisApp {
    const char* name;
    void (*setup)();
    void (*loop)();
    void (*cleanup)();
};

class OasisMenuSystem {
private:
    static const int MAX_APPS = 10;
    OasisApp apps[MAX_APPS];
    int appCount = 0;
    int currentApp = -1;  // -1 = menu mode
    int selectedIndex = 0;
    
    unsigned long lastInputTime = 0;
    const unsigned long DEBOUNCE_MS = 200;
    
public:
    void registerApp(const char* name, 
                    void (*setup)(), 
                    void (*loop)(), 
                    void (*cleanup)());
    
    void begin();
    void update();
    
private:
    void handleSerialInput();
    void handleGPIOInput();
    void showMenu();
    void selectApp(int index);
    void exitApp();
    void sendMenuState();
};

#endif
```

**File**: `core/menu_system.cpp`

```cpp
#include "menu_system.h"

void OasisMenuSystem::registerApp(const char* name, 
                                  void (*setup)(), 
                                  void (*loop)(), 
                                  void (*cleanup)()) {
    if (appCount < MAX_APPS) {
        apps[appCount++] = {name, setup, loop, cleanup};
    }
}

void OasisMenuSystem::begin() {
    Serial.begin(9600);
    while (!Serial) { delay(10); }
    
    Serial.println("Oasis Menu System");
    Serial.print("Apps loaded: ");
    Serial.println(appCount);
    
    showMenu();
}

void OasisMenuSystem::update() {
    if (currentApp == -1) {
        // Menu mode
        handleSerialInput();
        handleGPIOInput();
    } else {
        // Running app
        handleSerialInput();  // Check for exit command
        apps[currentApp].loop();
    }
}

void OasisMenuSystem::handleSerialInput() {
    if (Serial.available()) {
        String input = Serial.readStringUntil('\n');
        input.trim();
        
        if (currentApp == -1) {
            // Menu mode commands
            if (input == "scroll_forward") {
                selectedIndex = (selectedIndex + 1) % appCount;
                showMenu();
            } else if (input == "scroll_backward") {
                selectedIndex = (selectedIndex - 1 + appCount) % appCount;
                showMenu();
            } else if (input == "select") {
                selectApp(selectedIndex);
            }
        } else {
            // App mode commands
            if (input == "back" || input == "exit") {
                exitApp();
            }
        }
    }
}

void OasisMenuSystem::handleGPIOInput() {
    // Optional: Implement button controls
    // Left for platform-specific implementation
}

void OasisMenuSystem::showMenu() {
    Serial.println("\n=== Oasis Menu ===");
    for (int i = 0; i < appCount; i++) {
        if (i == selectedIndex) {
            Serial.print("> ");
        } else {
            Serial.print("  ");
        }
        Serial.println(apps[i].name);
    }
    Serial.println("==================");
    sendMenuState();
}

void OasisMenuSystem::selectApp(int index) {
    if (index >= 0 && index < appCount) {
        currentApp = index;
        Serial.print("Starting: ");
        Serial.println(apps[currentApp].name);
        apps[currentApp].setup();
        
        // Send status
        Serial.print("{\"type\":\"app_running\",\"app\":\"");
        Serial.print(apps[currentApp].name);
        Serial.println("\"}");
    }
}

void OasisMenuSystem::exitApp() {
    if (currentApp != -1) {
        Serial.print("Exiting: ");
        Serial.println(apps[currentApp].name);
        apps[currentApp].cleanup();
        currentApp = -1;
        showMenu();
    }
}

void OasisMenuSystem::sendMenuState() {
    Serial.print("{\"type\":\"menu_state\",\"selected\":");
    Serial.print(selectedIndex);
    Serial.print(",\"app\":\"");
    Serial.print(apps[selectedIndex].name);
    Serial.println("\"}");
}
```

---

## Testing

### Test Single App Build
```bash
cd oasis-mcu
python build.py --platform atmega328p_uno --apps greenhouse_sensors --dry-run
python build.py --platform atmega328p_uno --apps greenhouse_sensors
```

### Test Multi-App Build
```bash
python build.py --platform atmega328p_uno --apps greenhouse_sensors,led_controller --dry-run
python build.py --platform atmega328p_uno --apps greenhouse_sensors,led_controller
```

### Test Flash Overflow
```bash
# Should fail gracefully
python build.py --platform atmega328p_uno --apps app1,app2,app3,app4,app5 --dry-run
```

---

## Integration with Oasis Manager

The desktop app will call build.py programmatically:

```rust
// In oasis-manager
fn compile_arduino_apps(platform: &str, apps: Vec<&str>) -> Result<PathBuf> {
    let output = Command::new("python")
        .arg("build.py")
        .arg("--platform").arg(platform)
        .arg("--apps").arg(apps.join(","))
        .output()?;
    
    if !output.status.success() {
        return Err(anyhow!("Build failed: {}", String::from_utf8_lossy(&output.stderr)));
    }
    
    Ok(PathBuf::from(format!("build/{}/main.ino.hex", platform)))
}
```

---

**Last Updated**: November 23, 2024
