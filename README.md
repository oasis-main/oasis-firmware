# Oasis Firmware

**Configuration-driven firmware generation for IoT devices with KiCAD integration.**

Oasis Firmware is a unified hardware management framework that supports:
- **Multi-platform**: ESP32, Raspberry Pi, Arduino, STM32
- **Declarative config**: Define devices in YAML, generate firmware code
- **Simulation**: Wokwi simulation configs for ESP32
- **KiCAD integration**: Import PCB designs, export scaffolds, junction advisor
- **Legacy support**: Preserved Python RPi toolkit and Arduino sensor templates

## Architecture

```
oasis-firmware/
├── src/                    # Rust firmware generator (oasis-build CLI)
├── examples/               # device.yaml examples (greenhouse, drone)
├── docs/                   # Schema docs, deployment guide, desktop app design
├── kicad_bridge/           # Python KiCAD integration tools
└── legacy/
    ├── rpi/                # Original Python RPi toolkit (oasis-grow)
    └── ino/                # Arduino sensor templates (oasis-ino)
```

## Quick Start

### New Projects (Recommended)

1. Define your device in YAML (see `examples/`):
```yaml
device:
  id: my-greenhouse
  board: { platform: mcu, model: esp32_devkit }
sensors:
  - name: temp_humidity
    type: dht22
    pins: { data: 4 }
```

2. Validate and generate firmware:
```bash
cargo run --bin oasis-build -- validate --config device.yaml
cargo run --bin oasis-build -- generate --config device.yaml --output ./build/
```

3. Flash to device (see `docs/DEPLOYMENT.md`)

### KiCAD Integration

```bash
cd kicad_bridge && pip install -e .

# Import existing PCB to device.yaml
oasis-kicad import ./my-project.kicad_pro --output device.yaml

# Generate KiCAD scaffold from device.yaml
oasis-kicad scaffold --config device.yaml --output ./kicad/

# Get connector/cable/enclosure recommendations
oasis-kicad review --config device.yaml
```

### Legacy RPi Toolkit

The original Python-based RPi toolkit is preserved in `legacy/rpi/`:

```bash
cd legacy/rpi
. install.sh
. start.sh
```

See `legacy/rpi/README.md` for full documentation.

## Documentation

- [Device Schema](docs/DEVICE_SCHEMA.md) - YAML configuration reference
- [Deployment Guide](docs/DEPLOYMENT.md) - Flashing and deployment techniques
- [Desktop App Design](docs/DESKTOP_APP_DESIGN.md) - Planned egui desktop application

## Supported Platforms

| Platform | Generator | Simulation | Deployment |
|----------|-----------|------------|------------|
| ESP32    | Rust (embassy) | Wokwi | espflash, OTA |
| RPi      | Rust (tokio) | mock_gpio | SSH, systemd |
| Arduino  | C++ templates | - | arduino-cli |
| STM32    | Rust (embassy) | - | probe-rs |

## Contributing

We encourage users to contribute device definitions, example apps, and platform drivers. See `CONTRIBUTING.md` for guidelines.

---

## Architecture (Current)

The current architecture separates concerns across three layers:

| Layer | Component | Language | Purpose |
|-------|-----------|----------|---------|
| Build | `oasis-build` CLI | Rust | YAML → firmware code generation |
| Runtime (RPi) | Launcher + app folder | Rust + egui | Sandboxed app execution via systemd |
| Runtime (MCU) | `oasis-mcu` | C++ (Arduino) | Compile-time app composition with menu system |
| Desktop | `oasis-manager` | Rust + egui | SD flashing, Arduino flashing, app repository |
| Simulation | BehavioralRuntime | Python | Hardware-in-the-loop testing, MCP server |

See [SIMPLIFIED_ARCHITECTURE.md](SIMPLIFIED_ARCHITECTURE.md) for the full design rationale and [FIRMWARE_ANALYSIS_AND_ROADMAP.md](FIRMWARE_ANALYSIS_AND_ROADMAP.md) for current status and roadmap.

---

## Non-Trivial Programs: Robots & Drone Controllers

Simple sensor/actuator programs (greenhouse, irrigation) map cleanly onto the declarative YAML schema. Programs with **tight real-time control loops**, **state machines**, or **custom hardware interfaces** — such as robot arms, drone flight controllers, and motor driver stacks — require a different approach.

### When to use declarative YAML

The `device.yaml` schema works well when:
- Sensors publish measurements on a fixed interval
- Actuators respond to threshold or PID triggers
- No inter-component timing dependencies tighter than ~100ms

### When to write a custom app

For robots and drones, write a **custom RPi app** or **custom MCU sketch** and register it with the launcher:

#### RPi: Custom app folder

Create `/opt/oasis-apps/my-robot/`:

```
my-robot/
├── manifest.json       # app metadata + dependencies
├── run.sh              # entrypoint — launcher calls this
├── stop.sh             # graceful shutdown
└── robot_control.py   # your control logic
```

`manifest.json`:
```json
{
  "id": "my-robot",
  "name": "Robot Arm Controller",
  "version": "1.0.0",
  "runtime": "python3",
  "entrypoint": "run.sh",
  "requires": ["smbus2", "RPi.GPIO", "numpy"]
}
```

`run.sh` (launcher invokes this):
```bash
#!/bin/bash
cd "$(dirname "$0")"
pip install -r requirements.txt --quiet
exec python3 robot_control.py
```

The launcher manages the process lifecycle (start, stop, restart on crash) via systemd. Your app gets full GPIO, I2C, SPI, and UART access.

#### MCU: Custom sketch

For drone ESC control or motor driver timing (where microsecond precision matters), write a standard `app.ino` and register it under the correct platform:

```
oasis-mcu/
└── platforms/
    └── esp32_devkit/
        └── drone_controller/
            ├── manifest.json
            └── app.ino        ← your sketch here
```

The `oasis-mcu` build system will compile and link it correctly. For multi-app boards, the menu system handles runtime selection without recompiling.

### Runtime environment setup alongside flash

For programs that require a specific Python environment, system packages, or config files to be present **before the app first runs**, use the **pre-flash bootstrap script**:

```bash
# scripts/bootstrap_device.sh
# Run this once after flashing the SD card, before first boot

DEVICE_MOUNT="/Volumes/bootfs"   # macOS; adjust for Linux

# Write app config
cp configs/robot_config.json "$DEVICE_MOUNT/oasis-config.json"

# Write a first-boot systemd service that runs setup
cat > "$DEVICE_MOUNT/oasis-firstboot.service" << 'EOF'
[Unit]
Description=Oasis First-Boot Setup
After=network.target
ConditionPathExists=/boot/oasis-config.json

[Service]
Type=oneshot
ExecStart=/opt/oasis-apps/my-robot/setup.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

echo "Bootstrap complete. Eject and insert SD card."
```

`setup.sh` (runs once on first boot, then the service disables itself):
```bash
#!/bin/bash
apt-get install -y python3-pip libopencv-dev
pip3 install -r /opt/oasis-apps/my-robot/requirements.txt
systemctl disable oasis-firstboot
rm /boot/oasis-config.json
```

This pattern ensures the runtime environment is fully configured before the main app starts, without requiring a network connection at flash time.

### Oasis Manager (Desktop)

The `oasis-manager` desktop app (`oasis-manager/`) automates the above workflow:
1. Select your target board (RPi SD card or Arduino port)
2. Choose apps from the repository browser
3. Click **Flash** — manager handles SD imaging, app installation, and bootstrap config in one step

See [SIMPLIFIED_ARCHITECTURE.md](SIMPLIFIED_ARCHITECTURE.md) for the full manager UI design.

---

## Legacy Python Toolkit

The original Python-based RPi toolkit (`legacy/rpi/`) is preserved for reference and backward compatibility with existing deployments. It is **not recommended for new projects**. See `legacy/rpi/README.md` for its documentation.

---

## Sample Projects

| Project | Platform | Complexity |
|---------|----------|------------|
| Greenhouse monitor | ESP32 | Simple — use YAML |
| Time-lapse camera | RPi | Simple — use YAML |
| Mushroom chamber | RPi + Arduino | Simple — use YAML |
| Drone flight controller | ESP32 / custom MCU | Advanced — custom sketch |
| Robot arm (6-DOF) | RPi + I2C servo driver | Advanced — custom app |
| Outdoor weather station | ESP32 | Simple — use YAML |
| Automated irrigation grid | RPi + relay bank | Moderate — YAML + control loop |

---

## License

Apache License 2.0. See [LICENSE](LICENSE).

Third-party components in this repository keep their own licenses. See
[NOTICE](NOTICE). The vendored `simavr/` emulator is GPL-3.0.
