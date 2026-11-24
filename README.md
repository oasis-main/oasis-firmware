# Oasis Firmware

Open-source tools to design, simulate, and flash firmware for small
hardware projects: sensor nodes, greenhouse and farm controllers, and
hobby robots. The tools work on boards that you own, on your own computer.
The tools need no account, and the app works offline.

The main tool is **Oasis Studio**, a desktop app for macOS, Windows, and
Linux. An AI agent can use the same functions as the app through an MCP
(Model Context Protocol) server. The agent can read, plan, generate, and simulate.
Only a person can write firmware to a board.

## Principles

- **You own the board.** The app writes only to a device in the
  owned-device list. Only a person adds a device to the list.
- **A person confirms each write.** Each flash starts from a plan that
  shows every program, every argument, the firmware SHA-256 hash, and the
  backup. The flash runs only after a person confirms the plan.
- **Back up first.** If the board family has a read method, the app saves
  the current firmware before the write.
- **No shell.** The app gives each external program an argument list. No
  shell reads the arguments.
- **Each change is logged.** Each change writes one line to an action log,
  with the actor: `user`, `assistant`, or `mcp`.
- **Data, not code.** Board ids and flash recipes are in
  [`desktop/studio-core/boards.yaml`](desktop/studio-core/boards.yaml).
  To add a board, add a row.
- **The same functions for people and agents.** The app buttons, the
  assistant panel, and the MCP server call the same Rust functions in
  `desktop/studio-core`.

## Status

Version 0.1. The table shows what works today.

| Part | State |
|------|-------|
| Oasis Studio: board detection, owned-device list, action log | works |
| Oasis Studio: simulation | works for Arduino Uno (simavr) and STM32F103 (Renode), with a firmware file that you build |
| Oasis Studio: flash | built and tested with fake flash programs for each family. Not yet tested on a real board. |
| MCP server `oasis-studio-mcp` | works. The tools read, plan, generate files, and simulate. No tool writes to a device. |
| `device.yaml` validation (`oasis-build validate`) | works |
| Firmware generation for Raspberry Pi (Rust, tokio, systemd unit) | generates a project; the generated project is not built in CI |
| Firmware generation for microcontrollers (ESP32, STM32, Teensy) | generates a project that does not build yet. See section 4 of [docs/SIMULATION_PATHS_AVR_STM32.md](docs/SIMULATION_PATHS_AVR_STM32.md). |
| Firmware generation for Arduino | not built. Templates are in `legacy/ino/`. |
| In-app assistant | the panel shows the tools that the assistant will use. The chat is not built. |
| Over-the-air (OTA) update | design only, in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| Installers | built by CI on a tag. Not signed or notarized. See [docs/STUDIO_RELEASE.md](docs/STUDIO_RELEASE.md). |

## Repository layout

```
oasis-firmware/
├── src/                    # oasis-core: device.yaml validation and firmware generator (oasis-build CLI)
├── examples/               # device.yaml examples
├── desktop/                # Oasis Studio desktop app (Tauri 2)
│   ├── src/                #   front end (React, Vite, TypeScript)
│   ├── src-tauri/          #   app back end (thin Tauri commands)
│   └── studio-core/        #   tool registry, board table, flash and simulation runners, MCP server
├── simulation/             # Python behavioral runtime, emulator wrappers, simulator test fixtures
├── kicad_bridge/           # Python KiCAD tools (oasis-kicad CLI)
├── platforms/mcu/          # STM32F103 example project and the stm32f1xx-hal crate
├── simavr/                 # simavr AVR simulator source (GPL-3.0, see NOTICE)
├── site/                   # Oasis Studio overview and download pages
├── docs/                   # specifications, install guide, release guide
├── scripts/                # helper scripts
├── oasis-manager/          # older desktop manager specification (not built)
└── legacy/
    ├── ino/                # Arduino sketch templates (oasis-ino)
    └── oasis-studio-egui/  # earlier egui prototype of Oasis Studio
```

The original Python Raspberry Pi toolkit (`legacy/rpi/`) is no longer on
`master`. The branch `prod` keeps a copy.

## Oasis Studio

Oasis Studio has six pages:

| Page | What it does |
|------|--------------|
| Design | Validates a `device.yaml` and generates firmware into `Documents/Oasis Studio/<device id>/firmware` |
| Simulate | Runs a firmware file in simavr or Renode for a time limit and shows the UART output |
| Flash | Builds a flash plan, then backs up, writes, and verifies after you confirm |
| Hardware | Lists serial ports, USB ids, serial numbers, the board family, and the installed tools |
| Owned devices | The list of devices that the app may write to |
| Activity log | The action log |

Flash support by board family:

| Family | Program | Connection | Backup before the write |
|--------|---------|------------|-------------------------|
| `esp32` | espflash | USB serial | no read method yet |
| `avr_uno` | avrdude | USB serial | yes, Intel HEX file |
| `arduino` (any board of an installed arduino-cli core) | arduino-cli | USB serial | no (arduino-cli cannot read firmware) |
| `stm32` | probe-rs | debug probe (the owned probe only) | no read method yet |
| `rp2040` | picotool | USB (BOOTSEL) | yes, UF2 file |
| `micropython` | mpremote | USB serial | yes, a copy of `main.py` |
| `rpi` | ssh and scp | network, SSH key login | yes, a `.bak` copy on the Pi |

The app does not include the flash programs or the simulators. The install
steps for macOS, Windows, and Linux are in
[docs/INSTALL_TOOLCHAINS.md](docs/INSTALL_TOOLCHAINS.md). To run the app
from source, see [desktop/README.md](desktop/README.md).

## For AI agents

This section is for an AI agent (Claude Code, Claude Desktop, Cursor, or
another MCP client) that reads this repository for the first time. Follow
the steps in order.

### What the platform does

- You describe a device (board, sensors, actuators, control loops) in a
  `device.yaml` file. Examples are in `examples/`.
- `oasis-core` (the root crate) validates the file and generates a firmware
  crate for the board.
- Oasis Studio (`desktop/`) is a desktop app. It finds boards on USB, runs
  firmware in a simulator (simavr for Arduino Uno, Renode for STM32F103),
  and flashes boards that a person owns, after the person confirms.
- `oasis-studio-mcp` is an MCP (Model Context Protocol) server. It gives an
  agent the same tools that the app uses. The app and the server call the
  same Rust functions in `desktop/studio-core`.

### Safety rules

1. No MCP tool writes to a device. No MCP tool runs a flash or sends a
   command to a board. `flash_plan` only shows the plan. A flash runs only
   from the Flash page of the app, after a person confirms the plan.
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
| arduino-cli | Arduino build of the simavr fixture; flash of any Arduino board (family `arduino`) | `brew install arduino-cli` | `arduino-cli_<version>_Linux_64bit.tar.gz`; put `arduino-cli` on PATH | `arduino-cli_<version>_Windows_64bit.zip` |

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
| data (owned-device list, `audit.jsonl`, `sim-runs/`, `flash-runs/`, `backups/`) | `~/Library/Application Support/io.oasis-x.studio` | `~/.local/share/io.oasis-x.studio` | `%APPDATA%\io.oasis-x.studio` |
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
| `arduino_boards` | observe | Runs `arduino-cli board list` (read only). Returns each USB serial port with the matching board names (FQBN) of the installed cores. |
| `validate_config` | observe | Validates a `device.yaml` (`yaml` text or `path`). Returns a summary and the errors. |
| `generate_firmware` | propose | Generates firmware into `<projects>/<device id>/firmware`. Writes no other folder. |
| `registry_list` | observe | Reads the owned-device list. |
| `audit_tail` | observe | Reads the newest action-log lines (`limit`, 1 to 1000). |
| `flash_plan` | propose | Builds a flash plan: tool, argument list, firmware sha256, owned device, blockers. Never runs the flash tool. The `arduino` family needs `fqbn`, for example `arduino:avr:mega`. |
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

## Firmware generator (`oasis-build`)

`oasis-build` reads a `device.yaml` and writes a firmware project.

1. Describe the device. More examples are in `examples/`.

   ```yaml
   device:
     id: my-greenhouse
     board: { platform: mcu, model: esp32_devkit }
   sensors:
     - name: temp_humidity
       type: dht22
       pins: { data: 4 }
   ```

2. Validate the file:

   ```bash
   cargo run --bin oasis-build -- validate --config device.yaml
   ```

3. Generate the project. `--with-simulation` also writes a Wokwi project
   (ESP32 and Arduino board models) or a mock GPIO file (Raspberry Pi).

   ```bash
   cargo run --bin oasis-build -- generate --config device.yaml --output ./build/ --with-simulation
   ```

Other commands: `info --config <file>`, `boards`, `sensors`, `actuators`.

Board models:

| Platform | Models | Output |
|----------|--------|--------|
| `rpi` | `rpi_zero_w`, `rpi_zero_2w`, `rpi_3b`, `rpi_4b`, `rpi_5` | Rust supervisor program (tokio, rppal) and a systemd unit |
| `mcu` | `esp32_devkit`, `esp32_c3`, `esp32_s3`, `stm32f103`, `stm32f411`, `teensy_40`, `teensy_41` | Rust project (embassy). The project does not build yet. |

The schema is in [docs/DEVICE_SCHEMA.md](docs/DEVICE_SCHEMA.md).

### Programs that do not fit `device.yaml`

The schema works for sensors that report on a fixed interval and actuators
that respond to thresholds or PID loops. Drone flight controllers, robot
arms, and motor drivers need tighter timing and state machines. For these
projects, write the firmware yourself. Oasis Studio can still simulate the
built file (Uno, STM32F103) and flash it to a board that you own.

## KiCAD bridge (`oasis-kicad`)

```bash
cd kicad_bridge && python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/oasis-kicad import-pcb ./my-project.kicad_pro --output device.yaml
.venv/bin/oasis-kicad scaffold --config device.yaml --output ./kicad/
.venv/bin/oasis-kicad review --config device.yaml
```

- `import-pcb` reads a KiCAD project and writes a `device.yaml`.
- `scaffold` writes a KiCAD project from a `device.yaml`.
- `review` gives connector, cable, and enclosure advice.

See [kicad_bridge/README.md](kicad_bridge/README.md).

## Planned work

- An assistant chat in Oasis Studio. The assistant uses the same tool
  catalog as the MCP server and needs the same confirms.
- Flash from an agent, with a grant that a person gives for each device.
- A serial monitor and a boot-message check after each flash.
- Backup methods for ESP32 and STM32.
- A tool setup wizard for macOS, Windows, and Linux, and later an optional
  tool download from the app
  ([docs/TOOLCHAIN_SETUP_DESIGN.md](docs/TOOLCHAIN_SETUP_DESIGN.md)).
- Firmware generation that builds for Arduino Uno and STM32F103, so that
  Design, Generate, and Simulate work as one flow
  ([docs/SIMULATION_PATHS_AVR_STM32.md](docs/SIMULATION_PATHS_AVR_STM32.md)).
- Signed and notarized installers.

## Documentation

- [Install the tools](docs/INSTALL_TOOLCHAINS.md): flash programs and simulators for macOS, Windows, and Linux
- [Oasis Studio](desktop/README.md): the desktop app
- [Build and release](docs/STUDIO_RELEASE.md): build from source, release, signing
- [Device schema](docs/DEVICE_SCHEMA.md): the `device.yaml` reference
- [Board detection, flash, and log](docs/FW-015_BOARD_DETECT_FLASH_LOG_SPEC.md): flash specification
- [Simulation paths for AVR and STM32](docs/SIMULATION_PATHS_AVR_STM32.md): simulator decisions and generator faults
- [Simulation architecture](docs/SIMULATION_ARCHITECTURE.md)
- [Tool setup design](docs/TOOLCHAIN_SETUP_DESIGN.md)
- [Deployment guide](docs/DEPLOYMENT.md): flash and OTA methods (OTA is not built)
- [Agent instructions](AGENTS.md)

Older planning documents. Some parts are out of date:
[SIMPLIFIED_ARCHITECTURE.md](SIMPLIFIED_ARCHITECTURE.md),
[FIRMWARE_ANALYSIS_AND_ROADMAP.md](FIRMWARE_ANALYSIS_AND_ROADMAP.md),
[PROJECT_GUIDE.md](PROJECT_GUIDE.md), [QUICKSTART.md](QUICKSTART.md),
[README_FOR_AI_AGENTS.md](README_FOR_AI_AGENTS.md),
[docs/DESKTOP_APP_DESIGN.md](docs/DESKTOP_APP_DESIGN.md) (the egui design
that Oasis Studio replaced), and
[oasis-manager/MANAGER_SPEC.md](oasis-manager/MANAGER_SPEC.md).

## Contributing

Pull requests are welcome. Useful contributions:

- A new board: add a USB row or a family to
  [`desktop/studio-core/boards.yaml`](desktop/studio-core/boards.yaml),
  with the vendor document for the USB id.
- A test on real hardware: flash a board with Oasis Studio and report the
  board, the program version, and the result.
- Sensor and actuator drivers for the generator (`src/drivers/`).
- Example `device.yaml` files in `examples/`.

Run the tests in "Run the tests" above before you open a pull request. Do
not change the safety rules without a review.

## License

Apache License 2.0. See [LICENSE](LICENSE).

Third-party components in this repository keep their own licenses. See
[NOTICE](NOTICE). The `simavr/` simulator source is GPL-3.0. The
`stm32f1xx-hal` crate in `platforms/mcu/` is MIT or Apache-2.0.
