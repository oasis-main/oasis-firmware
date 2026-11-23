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
├── desktop/                # Oasis Studio desktop app (Tauri 2)
│   ├── src-tauri/          #   app back end (thin Tauri commands)
│   └── studio-core/        #   tool registry + MCP server (oasis-studio-mcp)
├── simulation/             # Python behavioral runtime, emulator wrappers, fixtures
├── site/                   # Oasis Studio overview and download pages
├── docs/                   # Schema docs, deployment guide, desktop app design
├── kicad_bridge/           # Python KiCAD integration tools
└── legacy/
    ├── rpi/                # Original Python RPi toolkit (oasis-grow)
    └── ino/                # Arduino sensor templates (oasis-ino)
```

## For AI agents

This section is for an AI agent (Claude Code, Claude Desktop, Cursor, or
another MCP client) that reads this repository for the first time. Follow
the steps in order.

### What the platform does

- You describe a device (board, sensors, actuators, control loops) in a
  `device.yaml` file. Examples are in `examples/`.
- `oasis-core` (the root crate) validates the file and generates a firmware
  crate for the board.
- Oasis Studio (`desktop/`) is a desktop app. It finds boards on USB, makes
  a flash plan, and runs firmware in a simulator: simavr for Arduino Uno
  (ATmega328P), Renode for STM32F103.
- `oasis-studio-mcp` is an MCP (Model Context Protocol) server. It gives an
  agent the same tools that the app uses. The app and the server call the
  same Rust functions in `desktop/studio-core`.

### Safety rules

1. No MCP tool writes to a device. No MCP tool runs a flash or sends a
   command to a board. `flash_plan` only shows the plan.
2. A write to a device needs a row in the owned-device list. Only a person
   adds a row, on the Owned devices page of the app. No MCP tool adds a row.
   `registry_list` only reads the list.
3. Each change writes one line to the action log, `audit.jsonl` in the data
   folder. A line has the time, the actor (`user`, `assistant`, or `mcp`),
   the action, the target, and the result. `audit_tail` reads the log.
4. External programs run with an argument list. No shell reads the
   arguments (`desktop/studio-core/src/tools.rs`, `runner.rs`).
5. `sim_run` runs only a local simulator, one run at a time, with a time
   limit of not more than 60 simulated seconds.

Do not change these rules in code without a person's review.

### Step 1: install the programs

The MCP server needs Rust only. The other programs are for the desktop
app, the simulators, and the Arduino build.

| Program | Needed for | macOS | Linux (Ubuntu/Debian) | Windows |
|---------|------------|-------|-----------------------|---------|
| Rust (stable, 1.77 or later) | MCP server, app, firmware | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` | same as macOS | `winget install Rustlang.Rustup` |
| Build packages | serial port listing | `xcode-select --install` | `sudo apt install build-essential pkg-config libudev-dev` | Microsoft C++ Build Tools |
| Node.js 20 or later | desktop app only | `brew install node` | Node.js 20 or later from nodejs.org (the Ubuntu 22.04 package is too old) | `winget install OpenJS.NodeJS.LTS` |
| simavr | Arduino Uno simulation | `brew tap osx-cross/avr` then `brew install osx-cross/avr/simavr` | `sudo apt install simavr` | no official build; use WSL 2 and the Linux steps |
| Renode 1.16.1 | STM32F103 simulation | `renode_1.16.1.dmg` (Intel) or `renode-1.16.1-dotnet.osx-arm64-portable.dmg` (Apple silicon); move Renode.app to `/Applications` | `renode-1.16.1.linux-portable-dotnet.tar.gz`; put the folder on PATH | `renode-1.16.1.setup.exe` |
| arduino-cli | Arduino build of the simavr fixture | `brew install arduino-cli` | `arduino-cli_<version>_Linux_64bit.tar.gz`; put `arduino-cli` on PATH | `arduino-cli_<version>_Windows_64bit.zip` |

- Renode files: <https://github.com/renode/renode/releases/tag/v1.16.1>.
- arduino-cli files: <https://github.com/arduino/arduino-cli/releases>.
- After you install arduino-cli, install the AVR core:
  `arduino-cli core update-index` and then `arduino-cli core install arduino:avr`.
- For the STM32 fixture, add the Rust target:
  `rustup target add thumbv7m-none-eabi`.
- Linux only: to see board details on USB, add the user to the serial
  group (`sudo usermod -aG dialout $USER`), then log out and log in.
- Desktop app packages for Linux and Windows: [docs/STUDIO_RELEASE.md](docs/STUDIO_RELEASE.md).

Open a new shell after the install. Then check the programs:

```bash
cargo --version
command -v simavr
renode --version
arduino-cli version
```

On macOS, `renode` is on PATH only if you link it:
`ln -s /Applications/Renode.app/Contents/MacOS/Renode /usr/local/bin/renode`.
The MCP server also finds Renode in `/Applications/Renode.app/Contents/MacOS`
without the link.

### Step 2: build the MCP server

Run from the repository root:

```bash
cargo build --release --locked --manifest-path desktop/studio-core/Cargo.toml --bin oasis-studio-mcp
desktop/studio-core/target/release/oasis-studio-mcp --version
desktop/studio-core/target/release/oasis-studio-mcp --list-tools
```

The program is `desktop/studio-core/target/release/oasis-studio-mcp`
(`oasis-studio-mcp.exe` on Windows). Use its absolute path in the client
configuration below.

### Step 3: register the server with your client

The server uses the stdio transport. The client starts the program and
sends one JSON-RPC 2.0 message on each line of stdin. The server writes one
message on each line of stdout, and diagnostic text on stderr. The server
accepts the MCP protocol versions `2025-06-18`, `2025-03-26`, and
`2024-11-05`.

Claude Code (run from the repository root):

```bash
claude mcp add oasis-studio -- "$PWD/desktop/studio-core/target/release/oasis-studio-mcp"
claude mcp list
```

`claude mcp list` must show `oasis-studio: <path> - ✔ Connected`. The default
scope is `local` (this folder, this user). Add `--scope user` for all
folders, or `--scope project` to write `.mcp.json` in this folder.

Claude Desktop: edit `claude_desktop_config.json`, then restart Claude
Desktop. The file is in `~/Library/Application Support/Claude/` on macOS
and in `%APPDATA%\Claude\` on Windows.

```json
{
  "mcpServers": {
    "oasis-studio": {
      "command": "/ABSOLUTE/PATH/oasis-firmware/desktop/studio-core/target/release/oasis-studio-mcp",
      "args": []
    }
  }
}
```

Cursor: put the same `mcpServers` object in `.cursor/mcp.json` in the
project, or in `~/.cursor/mcp.json` for all projects.

Other MCP clients (generic stdio configuration):

| Field | Value |
|-------|-------|
| transport | `stdio` |
| command | absolute path to `oasis-studio-mcp` |
| args | none, or `--data-dir <dir>` and `--projects-dir <dir>` |
| env (optional) | `OASIS_STUDIO_DATA_DIR`, `OASIS_STUDIO_PROJECTS_DIR` |

The server uses the same folders as the desktop app, so the app and the
server share the owned-device list and the action log:

| Folder | macOS | Linux | Windows |
|--------|-------|-------|---------|
| data (owned-device list, `audit.jsonl`, `sim-runs/`) | `~/Library/Application Support/io.oasis-x.studio` | `~/.local/share/io.oasis-x.studio` | `%APPDATA%\io.oasis-x.studio` |
| projects (generated firmware) | `~/Documents/Oasis Studio` | `~/Documents/Oasis Studio` | `Documents\Oasis Studio` |

Give each file path to a tool as an absolute path. A relative path is
relative to the folder where the client starts the server.

### Tools

Class `observe`: the tool reads only. Class `propose`: the tool prepares a
change and writes one action-log line with actor `mcp`. No tool writes to
a device. The tool list is in `desktop/studio-core/src/catalog.rs`. The
app's assistant panel shows the same list.

| Tool | Class | What it does |
|------|-------|--------------|
| `app_info` | observe | Version, OS, data folder, projects folder. |
| `list_ports` | observe | Serial ports, USB ids, USB serial numbers, board family. Opens no port. |
| `list_tools` | observe | Installed external programs (cargo, espflash, probe-rs, picotool, mpremote, arduino-cli, avrdude, simavr, renode). |
| `list_families` | observe | Board families: flash recipe and simulator. |
| `validate_config` | observe | Validates a `device.yaml` (`yaml` text or `path`). Returns a summary and the errors. |
| `generate_firmware` | propose | Generates firmware into `<projects>/<device id>/firmware`. Writes no other folder. |
| `registry_list` | observe | Reads the owned-device list. |
| `audit_tail` | observe | Reads the newest action-log lines (`limit`, 1 to 1000). |
| `flash_plan` | propose | Builds a flash plan: tool, argument list, firmware sha256, owned device, blockers. Never runs the flash tool. |
| `sim_plan` | observe | Checks if a firmware file can run in the simulator for a family. Runs nothing. |
| `sim_run` | propose | Runs firmware in simavr (`avr_uno`) or Renode (`stm32`) until exit, the time limit (`seconds`, default 5, maximum 60), or a cancel. Returns the exit reason and the last `max_lines` UART lines (default 200). Writes the full UART output to `uart.log` in the run folder. |

`sim_run` sends `notifications/progress` while UART lines arrive if the
request has `_meta.progressToken`. A `notifications/cancelled` for the
request stops the run. The result then has `"exit": {"reason": "stopped"}`.

A first session to check the setup:

1. Call `validate_config` with `path` set to the absolute path of
   `examples/greenhouse-demo.yaml`. The result has `"ok": true`.
2. Call `list_tools`. Each installed program has a `path`.
3. Call `audit_tail`. The log has no `mcp` line yet, because steps 1 and 2
   change nothing.

### Run the tests

Run from the repository root:

```bash
cargo test --locked --manifest-path desktop/studio-core/Cargo.toml
```

This command runs the tool handler tests, the MCP protocol tests, and an
end-to-end test. The end-to-end test starts `oasis-studio-mcp` and sends
`initialize`, `tools/list`, and `tools/call` over stdio.

The desktop app back end (needs Node.js and the Tauri packages):

```bash
cd desktop && npm ci && npm run build && cd src-tauri && cargo test --locked
```

The simulator tests run only when the fixture files exist. Build the
fixtures, set two variables, and run the `sim` tests. Build the STM32
fixture from its own folder: its `.cargo/config.toml` sets the target.

```bash
arduino-cli compile --fqbn arduino:avr:uno --output-dir /tmp/uno simulation/fixtures/avr_uno_serial
(cd simulation/fixtures/stm32f103_usart && cargo build --release)
export OASIS_SIM_AVR_ELF=/tmp/uno/avr_uno_serial.ino.elf
export OASIS_SIM_STM32_ELF="$PWD/simulation/fixtures/stm32f103_usart/target/thumbv7m-none-eabi/release/stm32f103_usart"
cargo test --locked --manifest-path desktop/studio-core/Cargo.toml sim -- --nocapture
```

The firmware generator (root crate) and the Python simulation package:

```bash
cargo test
cd simulation && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest tests
```

### Other MCP server in this repository

`simulation/mcp_server.py` is an older, experimental Python MCP server. It
controls the Python behavioral runtime and the emulator wrappers in
`simulation/`. It does not write the action log and has no time limit on
emulator runs. Use `oasis-studio-mcp` for the tools in the table above.

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
- [Oasis Studio](desktop/README.md) - Desktop app (Tauri 2) for macOS, Windows, and Linux
- [Oasis Studio build and release](docs/STUDIO_RELEASE.md) - Build from source, release, signing
- [Desktop App Design](docs/DESKTOP_APP_DESIGN.md) - Original egui design (superseded by Oasis Studio)

## Supported Platforms

| Platform | Generator | Simulation | Deployment |
|----------|-----------|------------|------------|
| ESP32    | Rust (embassy) | Wokwi | espflash, OTA |
| RPi      | Rust (tokio) | mock_gpio | SSH, systemd |
| Arduino  | C++ templates | simavr (Uno / ATmega328P) | avrdude (Oasis Studio), arduino-cli |
| STM32    | Rust (embassy) | Renode (STM32F103) | probe-rs |

Oasis Studio runs Arduino and STM32 firmware files in the simulators on the
Simulate page. Firmware generation for these two families is not complete
yet; see [docs/SIMULATION_PATHS_AVR_STM32.md](docs/SIMULATION_PATHS_AVR_STM32.md).

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
| Desktop | Oasis Studio (`desktop/`) | Rust + Tauri 2 + React | Design, generate, simulate (simavr, Renode), board detection, owned-device list, flash plan |
| Desktop (spec) | `oasis-manager` | Rust + egui | SD flashing, Arduino flashing, app repository |
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
