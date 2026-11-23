# Install the tools for Oasis Studio

Oasis Studio does not include the build, flash, and simulator programs. You
install only the programs for the work that you do. This guide tells you
which programs each kind of work needs, why the app needs each program, and
how to install each program on macOS, Windows, and Linux.

The Hardware page in the app shows each program that the app found, with
its path and version. After you install a program, open the Hardware page
again to check the result.

The design for the in-app setup wizard is in
[TOOLCHAIN_SETUP_DESIGN.md](TOOLCHAIN_SETUP_DESIGN.md) (work item FW-020).

## 1. What each kind of work needs

You need no programs to design a device, to see the device list, or to read
the activity log.

| Work | Programs | Approximate size |
|------|----------|------------------|
| Simulate an Arduino Uno | simavr | 1 MB |
| Simulate an STM32F103 | Renode | 215 MB (macOS app) |
| Build Arduino firmware | arduino-cli and the `arduino:avr` core | 240 MB (core) |
| Flash an Arduino Uno with a backup | avrdude (included in the `arduino:avr` core) | 1 MB |
| Flash any other Arduino board (Mega, Nano, Leonardo, Uno R4, Nano ESP32, MKR) | arduino-cli and the core of the board, for example `arduino:avr`, `arduino:renesas_uno`, or `arduino:samd` | 240 MB (`arduino:avr` core); other cores not measured |
| Build STM32, ESP32, or RP2040 firmware | Rust (`rustup`, `cargo`) and the chip target | 1.6 GB (stable toolchain) |
| Flash an STM32 or RP2040 with a debug probe | probe-rs | not measured |
| Flash an ESP32 | espflash | not measured |
| Flash an RP2040 over USB (BOOTSEL) | picotool | not measured |
| Copy files to a MicroPython board | mpremote | not measured |

The sizes come from one Mac (2026-11-20). "Not measured" means that the
program was not installed on that Mac.

## 2. Status of these steps

| Program | Tested on macOS | Tested on Linux | Tested on Windows |
|---------|-----------------|-----------------|-------------------|
| simavr | yes | CI (`sim-ci.yml`, Ubuntu 22.04) | no Windows build |
| Renode 1.16.1 | yes | CI (portable package) | no |
| arduino-cli + `arduino:avr` 1.8.6 | yes | CI | no |
| Rust + `thumbv7m-none-eabi` | yes | CI | no |
| avrdude, probe-rs, espflash, picotool, mpremote | no | no | no |

A step with "no" comes from the official documentation of the program. Open
an issue if a step fails on your computer. Give the operating system, the
step, and the error text.

## 3. macOS

### 3.1 Before you start

1. Install the Xcode Command Line Tools. Rust needs the linker in this
   package.

   ```bash
   xcode-select --install
   ```

2. Install Homebrew from <https://brew.sh>. Most steps below use Homebrew.

### 3.2 Simulators

1. Install simavr (Arduino Uno simulator).

   ```bash
   brew install simavr
   ```

2. Install Renode (STM32 simulator). Download `renode_<version>.dmg` from
   <https://github.com/renode/renode/releases>. Drag Renode into
   Applications. The app finds Renode in
   `/Applications/Renode.app/Contents/MacOS`. You do not need to add Renode
   to PATH.

### 3.3 Arduino build and flash

1. Install arduino-cli.

   ```bash
   brew install arduino-cli
   ```

2. Install the AVR core. The core includes the AVR compiler and avrdude.

   ```bash
   arduino-cli core update-index
   ```

   ```bash
   arduino-cli core install arduino:avr
   ```

The core puts avrdude in
`~/Library/Arduino15/packages/arduino/tools/avrdude/<version>/bin/`. The
app does not look in this folder yet (FW-020 phase W1). Until then, install
avrdude also with `brew install avrdude`, or the Hardware page shows
avrdude as missing.

For an Arduino board that is not an Uno, install the core of the board.
The Flash page then uses the family "Arduino board, any model
(arduino-cli)". To find the core and the board name (FQBN) of a connected
board, run this command:

```bash
arduino-cli board list
```

If the FQBN column is empty, find the core with `arduino-cli core search
<board name>`, and install the core with `arduino-cli core install <core>`.
Then run `arduino-cli board list` again.

### 3.4 Rust firmware (STM32, ESP32, RP2040)

1. Install Rust with rustup.

   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

2. Add the STM32 targets.

   ```bash
   rustup target add thumbv7m-none-eabi thumbv7em-none-eabihf
   ```

3. For ESP32 only: install the Xtensa toolchain with espup.

   ```bash
   cargo install espup
   ```

   ```bash
   espup install
   ```

### 3.5 Flash tools

```bash
brew install probe-rs/probe-rs/probe-rs
```

```bash
cargo install espflash
```

```bash
brew install picotool
```

For mpremote, use pipx. Do not install into the system Python.

```bash
brew install pipx
```

```bash
pipx install mpremote
```

## 4. Windows

### 4.1 Before you start

1. Use Windows 10 or Windows 11. The steps use `winget`, which these
   versions include.
2. Open PowerShell. The steps do not need an administrator window. An
   installer can ask for administrator permission.

### 4.2 Simulators

1. simavr has no official Windows build. Arduino Uno simulation is not
   available on Windows in this version (decision D1 in
   [SIMULATION_PATHS_AVR_STM32.md](SIMULATION_PATHS_AVR_STM32.md)). The
   Simulate page shows this blocker.
2. Install Renode. Download the Windows installer from
   <https://github.com/renode/renode/releases> and run the installer.
   Then open a new PowerShell window and check that `renode --version`
   prints a version.

### 4.3 Arduino build and flash

1. Install arduino-cli.

   ```powershell
   winget install ArduinoSA.CLI
   ```

2. Install the AVR core.

   ```powershell
   arduino-cli core update-index
   ```

   ```powershell
   arduino-cli core install arduino:avr
   ```

3. Install the USB serial driver for your board, if Windows does not find
   the board. Boards with a CH340 chip use the WCH driver. Boards with a
   CP210x chip use the Silicon Labs driver. Windows Update often installs
   these drivers.

### 4.4 Rust firmware

1. Install rustup. Rust on Windows needs the Microsoft C++ Build Tools. The
   rustup installer offers to install the Build Tools.

   ```powershell
   winget install Rustlang.Rustup
   ```

2. Open a new PowerShell window. Add the STM32 targets.

   ```powershell
   rustup target add thumbv7m-none-eabi thumbv7em-none-eabihf
   ```

3. For ESP32 only: install espup, then run `espup install`.

### 4.5 Flash tools

1. Install probe-rs with the official PowerShell installer from
   <https://probe.rs/docs/getting-started/installation/>. Read the probe-rs
   page about USB drivers for your debug probe.
2. Install espflash: `cargo install espflash`.
3. Install picotool from the `pico-sdk-tools` releases of the Raspberry Pi
   GitHub organization.
4. Install mpremote: `pipx install mpremote` (install pipx first with
   `python -m pip install --user pipx`).

## 5. Linux

The commands are for Debian and Ubuntu. On Fedora, use `dnf`. On Arch, use
`pacman`.

### 5.1 Before you start

1. Give your user access to serial ports. Then log out and log in again.

   ```bash
   sudo usermod -aG dialout $USER
   ```

   On Arch, the group is `uucp`, not `dialout`.

2. Install the build packages.

   ```bash
   sudo apt install build-essential pkg-config libudev-dev curl
   ```

### 5.2 Simulators

1. Install simavr.

   ```bash
   sudo apt install simavr
   ```

2. Install Renode. Download `renode-<version>.linux-portable-dotnet.tar.gz`
   from <https://github.com/renode/renode/releases>. Check the SHA-256
   value on the release page. Extract the archive into a folder, for
   example `~/.local/opt/renode`. Add that folder to PATH. The CI file
   `.github/workflows/sim-ci.yml` does the same steps.

### 5.3 Arduino build and flash

1. Install arduino-cli with the official script. Read the script before you
   run the script.

   ```bash
   curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR=~/.local/bin sh
   ```

2. Install the AVR core.

   ```bash
   arduino-cli core update-index
   ```

   ```bash
   arduino-cli core install arduino:avr
   ```

3. Install avrdude on PATH. The app does not look in the core folder yet.

   ```bash
   sudo apt install avrdude
   ```

### 5.4 Rust firmware

The steps are the same as macOS section 3.4.

### 5.5 Flash tools

1. Install probe-rs with the official shell installer from
   <https://probe.rs/docs/getting-started/installation/>.
2. Install the probe-rs udev rules, so that your user can open the debug
   probe. The probe-rs page gives the rules file and the steps.
3. Install espflash: `cargo install espflash`.
4. Install picotool: `sudo apt install picotool` on Debian 12 and later. On
   older versions, build picotool from source.
5. Install mpremote: `pipx install mpremote`.

## 6. For contributors: the Python simulation package

The Python package in `simulation/` runs the co-simulation and its MCP
server. Use a virtual environment.

```bash
cd simulation && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
```

```bash
cd simulation && .venv/bin/pytest tests -v -rs
```

The fixture tests skip when a simulator is missing. The fixture steps are in
[simulation/fixtures/README.md](../simulation/fixtures/README.md).
