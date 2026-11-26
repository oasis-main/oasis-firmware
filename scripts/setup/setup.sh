#!/usr/bin/env bash
# Oasis Studio tool setup for macOS and Ubuntu (22.04 or later).
#
# Installs the programs that Oasis Studio uses to flash and simulate boards.
# Oasis Studio itself is a separate installer.
#
#   bash setup.sh                  flash tools (default)
#   bash setup.sh --tools full     flash tools, Rust, simavr, and Renode
#   bash setup.sh --dry-run        show the plan and install nothing
#
# Rules:
# - The script installs only what is missing. It does not upgrade or remove
#   a program that is already installed.
# - macOS: Homebrew installs the flash tools. The script does not install
#   Homebrew.
# - Ubuntu: apt installs the system packages. Other programs come from fixed
#   release files. The script checks the SHA-256 hash of each file before it
#   uses the file, and installs the programs for this user only:
#   ~/.local/share/oasis-studio/tools/ and ~/.local/bin/.
# - sudo is used only for apt, the serial port group, and the USB rules.
#   The script asks before it runs sudo, unless you give --yes.
#
# Works with the bash 3.2 that macOS includes.

set -euo pipefail

TOOLS=flash
DRY_RUN=0
YES=0

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'
Options:
  --tools flash|full   flash: arduino-cli and the Arduino AVR core, avrdude,
                       espflash, probe-rs, picotool, mpremote.
                       full: the flash tools, plus Rust, simavr, and Renode.
  --dry-run            show the plan and install nothing.
  --yes                do not ask before an install or a sudo step.
  --help               show this text.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --tools) TOOLS="${2:-}"; shift 2 ;;
    --tools=*) TOOLS="${1#--tools=}"; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes|-y) YES=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
case "$TOOLS" in flash|full) ;; *) echo "--tools must be flash or full." >&2; exit 2 ;; esac

# ---------------------------------------------------------------- versions
# Fixed release files: tool, platform, version, URL, SHA-256.
# To change a version, download the new file, check the publisher's hash
# where one is published, and replace the row. setup.ps1 has the Windows rows.
PINS='
arduino-cli	linux-x86_64	1.6.0	https://github.com/arduino/arduino-cli/releases/download/v1.6.0/arduino-cli_1.6.0_Linux_64bit.tar.gz	321ee249f44c78053234fec0f36101092bc6021bf24939e15e0cc2449c5ed250
arduino-cli	linux-aarch64	1.6.0	https://github.com/arduino/arduino-cli/releases/download/v1.6.0/arduino-cli_1.6.0_Linux_ARM64.tar.gz	2ed4e1436bb3be1265966af8eba95dd25e28f3a9f92d0a58d371ed14dbaf550f
espflash	linux-x86_64	4.7.0	https://github.com/esp-rs/espflash/releases/download/v4.7.0/espflash-x86_64-unknown-linux-gnu.zip	8ab3bafeb212ccb1d7a9c422936b9bc86f8b00fe2731053ed8ab875c8d2f0c4d
espflash	linux-aarch64	4.7.0	https://github.com/esp-rs/espflash/releases/download/v4.7.0/espflash-aarch64-unknown-linux-gnu.zip	3158e1c78f3e80ad0389c1d925b69736e1955a60b3cadf932e6d0d74d731b448
probe-rs	linux-x86_64	0.32.0	https://github.com/probe-rs/probe-rs/releases/download/v0.32.0/probe-rs-tools-x86_64-unknown-linux-gnu.tar.xz	c2ccc46049e52a5d403ef212078cd637ecda55b662708327960558f83e851ff5
probe-rs	linux-aarch64	0.32.0	https://github.com/probe-rs/probe-rs/releases/download/v0.32.0/probe-rs-tools-aarch64-unknown-linux-gnu.tar.xz	7c818cfd77808e806bf8f4d108c9137910b4fb28e0fe5c464d39782dbbc8af31
picotool	linux-x86_64	2.3.1	https://github.com/raspberrypi/pico-sdk-tools/releases/download/v2.3.1-0/picotool-2.3.1-x86_64-lin.tar.gz	878a1a1e7d8336b8be60300c7218f366d9790c0d3a211b181d6d172e80b1248e
picotool	linux-aarch64	2.3.1	https://github.com/raspberrypi/pico-sdk-tools/releases/download/v2.3.1-0/picotool-2.3.1-aarch64-lin.tar.gz	8cce5579c92e77c0439f34d4f49d37b1dc7d1e7c455233398f2e7b49599f67aa
renode	linux-x86_64	1.16.1	https://github.com/renode/renode/releases/download/v1.16.1/renode-1.16.1.linux-portable-dotnet.tar.gz	00e113cdbd0f5354cf2f64bbe3f5a070d8958409542fca66e45ac97d982938c0
renode	linux-aarch64	1.16.1	https://github.com/renode/renode/releases/download/v1.16.1/renode-1.16.1.linux-arm64-portable-dotnet.tar.gz	fff3a098c96ed0a4ffbdff3f028c9c5fde432db09587c7bd7c99406180f90007
renode	macos-arm64	1.16.1	https://github.com/renode/renode/releases/download/v1.16.1/renode-1.16.1-dotnet.osx-arm64-portable.dmg	99b8ae5897b8926ef179868d39a504fe5296555dc9c9b973718ddf3ab09175d9
renode	macos-x86_64	1.16.1	https://github.com/renode/renode/releases/download/v1.16.1/renode_1.16.1.dmg	7879b2851b446ff99e1d3910b499af278fbd76a3fa8fe5c0d379f30afa0c4ed1
rustup-init	linux-x86_64	1.28.2	https://static.rust-lang.org/rustup/archive/1.28.2/x86_64-unknown-linux-gnu/rustup-init	20a06e644b0d9bd2fbdbfd52d42540bdde820ea7df86e92e533c073da0cdd43c
rustup-init	linux-aarch64	1.28.2	https://static.rust-lang.org/rustup/archive/1.28.2/aarch64-unknown-linux-gnu/rustup-init	e3853c5a252fca15252d07cb23a1bdd9377a8c6f3efa01531109281ae47f841c
rustup-init	macos-arm64	1.28.2	https://static.rust-lang.org/rustup/archive/1.28.2/aarch64-apple-darwin/rustup-init	20ef5516c31b1ac2290084199ba77dbbcaa1406c45c1d978ca68558ef5964ef5
rustup-init	macos-x86_64	1.28.2	https://static.rust-lang.org/rustup/archive/1.28.2/x86_64-apple-darwin/rustup-init	9c331076f62b4d0edeae63d9d1c9442d5fe39b37b05025ec8d41c5ed35486496
udev-probe-rs	linux-any	2026-10-06	https://raw.githubusercontent.com/probe-rs/webpage/2770cdb68de046dbcab17806a81b1e76644b2f1c/public/files/69-probe-rs.rules	09f2ea59a57347687667184dfcd1136f6663dfc0ffdc11eb8eb8d98f31dab45d
udev-picotool	linux-any	2.3.1	https://raw.githubusercontent.com/raspberrypi/picotool/2.3.1/udev/60-picotool.rules	2abead6788e7f0efd87c918e5e7555bb6449273b27a513b19ddd3b66b94727d0
'
ARDUINO_AVR_CORE="arduino:avr@1.8.6"
MPREMOTE_VERSION="1.29.0"
STM32_RUST_TARGET="thumbv7m-none-eabi"

# ---------------------------------------------------------------- helpers
say() { printf '%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

ask() {
  # ask "question" -> 0 for yes. --yes answers yes. No terminal answers no.
  [ "$YES" = 1 ] && return 0
  [ -t 0 ] || return 1
  printf '%s [y/N] ' "$1"
  read -r reply
  case "$reply" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

have() { command -v "$1" >/dev/null 2>&1; }

OS=""
case "$(uname -s)" in
  Darwin) OS=macos ;;
  Linux)
    [ -r /etc/os-release ] || die "This Linux system has no /etc/os-release. The script supports Ubuntu 22.04 or later."
    # shellcheck disable=SC1091
    . /etc/os-release
    case " ${ID:-} ${ID_LIKE:-} " in
      *" ubuntu "*|*" debian "*) OS=ubuntu ;;
      *) die "This script supports Ubuntu and Debian-based systems. This system is ${PRETTY_NAME:-unknown}. Use docs/INSTALL_TOOLCHAINS.md." ;;
    esac
    ;;
  *) die "Unsupported system $(uname -s). On Windows, use setup.ps1." ;;
esac

case "$(uname -m)" in
  x86_64|amd64) ARCH=x86_64 ;;
  arm64|aarch64) ARCH=$([ "$OS" = macos ] && echo arm64 || echo aarch64) ;;
  *) die "Unsupported processor $(uname -m)." ;;
esac
PLATFORM="${OS/ubuntu/linux}-$ARCH"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
TOOL_DIR="$DATA_HOME/oasis-studio/tools"
BIN_DIR="$HOME/.local/bin"
ORIG_PATH="$PATH"
export PATH="$BIN_DIR:$HOME/.cargo/bin:$PATH"
ME="${USER:-$(id -un)}"

pin_field() {
  # pin_field tool platform column -> value (3 version, 4 url, 5 sha256)
  printf '%s\n' "$PINS" | awk -F'\t' -v t="$1" -v p="$2" -v c="$3" '!done && $1 == t && $2 == p { print $c; done = 1 }'
}

sha256_of() {
  if have sha256sum; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

WORK=""
cleanup() { [ -n "$WORK" ] && rm -rf "$WORK"; return 0; }
trap cleanup EXIT

fetch() {
  # fetch tool platform -> path of the checked file in $WORK
  local url sha file got
  url="$(pin_field "$1" "$2" 4)"
  sha="$(pin_field "$1" "$2" 5)"
  [ -n "$url" ] || die "No fixed release file for $1 on $2."
  [ -n "$WORK" ] || WORK="$(mktemp -d)"
  file="$WORK/$(basename "$url")"
  say "    download $url" >&2
  curl --proto '=https' --tlsv1.2 -fsSL --retry 3 -o "$file" "$url" || die "Download failed: $url"
  got="$(sha256_of "$file")"
  if [ "$got" != "$sha" ]; then
    rm -f "$file"
    die "SHA-256 check failed for $(basename "$url"). Expected $sha, got $got. The file was deleted."
  fi
  say "    sha256 ok" >&2
  printf '%s\n' "$file"
}

unpack() {
  # unpack archive dir
  mkdir -p "$2"
  case "$1" in
    *.zip) unzip -q -o "$1" -d "$2" ;;
    *.tar.gz|*.tgz) tar -xzf "$1" -C "$2" ;;
    *.tar.xz) tar -xJf "$1" -C "$2" ;;
    *) die "Unknown archive type: $1" ;;
  esac
}

link_program() {
  # link_program dir name: find the program in dir and link it into BIN_DIR.
  local exe
  # The file nearest to the top of the folder wins.
  exe="$(find "$1" -type f -name "$2" | awk '{ print length($0) "\t" $0 }' | sort -n | head -n 1 | cut -f2-)"
  [ -n "$exe" ] || die "$2 not found in $1."
  chmod +x "$exe"
  mkdir -p "$BIN_DIR"
  ln -sf "$exe" "$BIN_DIR/$2"
  say "    $BIN_DIR/$2 -> $exe"
}

install_release() {
  # install_release tool program...
  local tool="$1"; shift
  local version file dir prog
  version="$(pin_field "$tool" "$PLATFORM" 3)"
  file="$(fetch "$tool" "$PLATFORM")"
  dir="$TOOL_DIR/$tool-$version"
  rm -rf "$dir"
  unpack "$file" "$dir"
  for prog in "$@"; do link_program "$dir" "$prog"; done
}

# ---------------------------------------------------------------- tool list
# name|kit|purpose|size (download size; disk size for the Arduino core and Rust)
TOOL_ROWS='arduino-cli|flash|Uploads firmware to any Arduino board, and builds Arduino sketches.|19 MB
arduino:avr core|flash|Compiler and upload tools for AVR Arduino boards (Uno, Mega, Nano).|240 MB
avrdude|flash|Writes and reads firmware on an Arduino Uno. The Uno backup uses avrdude.|small
espflash|flash|Writes firmware to ESP32 boards.|8 MB
probe-rs|flash|Writes firmware to STM32 chips through a debug probe (ST-LINK).|22 MB
picotool|flash|Writes and reads firmware on RP2040 boards in BOOTSEL mode.|1 MB
mpremote|flash|Copies files to MicroPython boards.|small
rust|full|Rust compiler. Builds firmware and the Oasis Studio MCP server.|1.6 GB
simavr|full|Simulates an Arduino Uno (ATmega328P) with no board. On macOS, Homebrew also installs avr-gcc.|small
renode|full|Simulates STM32 chips with no board.|75 MB'

renode_path() {
  if [ "$OS" = macos ] && [ -x /Applications/Renode.app/Contents/MacOS/renode ]; then
    echo /Applications/Renode.app/Contents/MacOS/renode
  else
    command -v renode 2>/dev/null || true
  fi
}

core_installed() {
  have arduino-cli && arduino-cli core list 2>/dev/null </dev/null | awk '$1 == "arduino:avr" { f = 1 } END { exit !f }'
}

found_at() {
  # found_at name -> path or text when present, empty when missing.
  case "$1" in
    "arduino:avr core") if core_installed; then echo "installed"; fi ;;
    rust) command -v cargo 2>/dev/null || true ;;
    renode) renode_path ;;
    *) command -v "$1" 2>/dev/null || true ;;
  esac
}

in_kit() { [ "$TOOLS" = full ] || [ "$1" = flash ]; }

# The prebuilt probe-rs for Linux needs glibc 2.39 or later (Ubuntu 24.04).
# On an older system, the script builds probe-rs with cargo when Rust is
# present or is part of this install. Otherwise the script skips probe-rs.
PROBE_RS_MIN_GLIBC="2.39"
PROBE_RS_MODE=release
if [ "$OS" = ubuntu ]; then
  glibc="$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{ print $2 }')"
  if [ -n "$glibc" ] && [ "$(printf '%s\n%s\n' "$PROBE_RS_MIN_GLIBC" "$glibc" | sort -V | head -n 1)" != "$PROBE_RS_MIN_GLIBC" ]; then
    if have cargo || [ "$TOOLS" = full ]; then PROBE_RS_MODE=source; else PROBE_RS_MODE=skip; fi
  fi
fi
probe_rs_cargo_cmd() {
  echo "cargo install probe-rs-tools --version $(pin_field probe-rs linux-x86_64 3) --locked"
}

# ---------------------------------------------------------------- plan
step "Oasis Studio tool setup: $OS ($ARCH), tools: $TOOLS"
if [ "$OS" = macos ] && ! have brew; then
  die "Homebrew is not installed. Install Homebrew from https://brew.sh, open a new terminal, and run this script again."
fi

MISSING=""
printf '\n%-18s %-10s %s\n' "Program" "Size" "Status"
while IFS='|' read -r name kit purpose size; do
  in_kit "$kit" || continue
  at="$(found_at "$name" </dev/null)"
  if [ -n "$at" ]; then
    printf '%-18s %-10s found: %s\n' "$name" "-" "$at"
  elif [ "$name" = probe-rs ] && [ "$PROBE_RS_MODE" = skip ]; then
    printf '%-18s %-10s skipped: needs glibc %s (Ubuntu 24.04), or Rust to build it\n' "$name" "-" "$PROBE_RS_MIN_GLIBC"
  elif [ "$name" = probe-rs ] && [ "$PROBE_RS_MODE" = source ]; then
    printf '%-18s %-10s will build from source with cargo (5 to 15 minutes)\n' "$name" "-"
    MISSING="$MISSING|$name|"
  else
    printf '%-18s %-10s will install\n' "$name" "$size"
    MISSING="$MISSING|$name|"
  fi
  printf '%-18s %s\n' "" "$purpose"
done <<EOF
$TOOL_ROWS
EOF

missing() { case "$MISSING" in *"|$1|"*) return 0 ;; *) return 1 ;; esac; }

if [ "$OS" = ubuntu ]; then
  say ""
  say "Programs go in $TOOL_DIR, with links in $BIN_DIR."
fi

linux_group() {
  if getent group uucp >/dev/null 2>&1 && ! getent group dialout >/dev/null 2>&1; then echo uucp; else echo dialout; fi
}
in_group() { id -nG "$ME" | tr ' ' '\n' | awk -v g="$1" '$0 == g { f = 1 } END { exit !f }'; }

if [ "$DRY_RUN" = 1 ]; then
  if [ "$OS" = ubuntu ]; then
    g="$(linux_group)"
    say ""
    if in_group "$g"; then say "Serial ports: $ME is in the '$g' group."; else say "Serial ports: will ask to add $ME to the '$g' group (sudo)."; fi
    for rule in udev-probe-rs udev-picotool; do
      dest="/etc/udev/rules.d/$(basename "$(pin_field "$rule" linux-any 4)")"
      if [ -f "$dest" ]; then say "USB rule: $dest is present."; else say "USB rule: will ask to install $dest (sudo)."; fi
    done
  fi
  say ""
  say "Dry run: nothing was installed."
  exit 0
fi

if [ -z "$MISSING" ]; then
  say ""
  say "All programs for '$TOOLS' are installed."
elif ! ask "Install the missing programs?"; then
  say "Nothing was installed."
  exit 0
fi

# ---------------------------------------------------------------- install
if [ -n "$MISSING" ] && [ "$OS" = macos ]; then
  formulas=""
  for f in arduino-cli avrdude espflash picotool mpremote; do
    missing "$f" && formulas="$formulas $f"
  done
  missing probe-rs && formulas="$formulas probe-rs-tools"
  if [ -n "$formulas" ]; then
    step "Homebrew:$formulas"
    # shellcheck disable=SC2086
    brew install $formulas
  fi
  if missing simavr; then
    step "simavr (Homebrew tap osx-cross/avr)"
    brew tap osx-cross/avr
    brew install osx-cross/avr/simavr
  fi
  if missing renode; then
    step "Renode $(pin_field renode "$PLATFORM" 3)"
    [ -w /Applications ] || die "/Applications is not writable for this user. Install Renode by hand: docs/INSTALL_TOOLCHAINS.md."
    dmg="$(fetch renode "$PLATFORM")"
    mnt="$WORK/renode-mount"
    mkdir -p "$mnt"
    hdiutil attach -nobrowse -readonly -mountpoint "$mnt" "$dmg" >/dev/null
    rm -rf /Applications/Renode.app
    cp -R "$mnt/Renode.app" /Applications/
    hdiutil detach -quiet "$mnt"
    say "    /Applications/Renode.app"
  fi
fi

if [ -n "$MISSING" ] && [ "$OS" = ubuntu ]; then
  pkgs="curl ca-certificates unzip xz-utils libusb-1.0-0 libudev1"
  missing avrdude && pkgs="$pkgs avrdude"
  missing mpremote && pkgs="$pkgs pipx"
  missing simavr && pkgs="$pkgs simavr"
  missing rust && pkgs="$pkgs build-essential"
  if missing probe-rs && [ "$PROBE_RS_MODE" = source ]; then
    case " $pkgs " in *" build-essential "*) ;; *) pkgs="$pkgs build-essential" ;; esac
    pkgs="$pkgs pkg-config libudev-dev"
  fi
  missing renode && pkgs="$pkgs (and the ICU library for Renode)"
  step "apt: $pkgs"
  if ask "Run 'sudo apt-get install' for these packages?"; then
    sudo apt-get update
    pkgs="${pkgs% (and*}"
    if missing renode; then
      # Renode (.NET) needs ICU. The package name has the ICU version: libicu70, libicu74, ...
      icu="$(apt-cache pkgnames libicu | grep -E '^libicu[0-9]+$' | sort -V | tail -n 1 || true)"
      [ -n "$icu" ] && pkgs="$pkgs $icu"
    fi
    # shellcheck disable=SC2086
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $pkgs
  else
    say "Skipped apt. Some installs below can fail."
  fi
  if missing arduino-cli; then step "arduino-cli"; install_release arduino-cli arduino-cli; fi
  if missing espflash; then step "espflash"; install_release espflash espflash; fi
  if missing probe-rs && [ "$PROBE_RS_MODE" = release ]; then step "probe-rs"; install_release probe-rs probe-rs; fi
  if missing picotool; then step "picotool"; install_release picotool picotool; fi
  if missing renode; then
    step "Renode"
    install_release renode renode
  fi
  if missing mpremote; then
    step "mpremote $MPREMOTE_VERSION (pipx)"
    pipx install "mpremote==$MPREMOTE_VERSION"
  fi
fi

if missing rust; then
  step "Rust (rustup $(pin_field rustup-init "$PLATFORM" 3), stable toolchain)"
  init="$(fetch rustup-init "$PLATFORM")"
  chmod +x "$init"
  "$init" -y --profile minimal --default-toolchain stable
  export PATH="$HOME/.cargo/bin:$PATH"
fi
if missing probe-rs && [ "$PROBE_RS_MODE" = source ]; then
  step "probe-rs (build from source: glibc $glibc is older than $PROBE_RS_MIN_GLIBC)"
  cargo install probe-rs-tools --version "$(pin_field probe-rs linux-x86_64 3)" --locked
fi
if [ "$TOOLS" = full ] && have rustup; then
  step "Rust target $STM32_RUST_TARGET (STM32F103)"
  rustup target add "$STM32_RUST_TARGET"
fi

if have arduino-cli && ! core_installed; then
  step "Arduino core $ARDUINO_AVR_CORE"
  arduino-cli core update-index
  arduino-cli core install "$ARDUINO_AVR_CORE"
fi

# ---------------------------------------------------------------- Linux USB access
if [ "$OS" = ubuntu ]; then
  group="$(linux_group)"
  if ! in_group "$group"; then
    step "Serial port access"
    say "Flash tools need membership of the '$group' group to open serial ports."
    if ask "Run 'sudo usermod -aG $group $ME'?"; then
      sudo usermod -aG "$group" "$ME"
      say "Log out and log in again. The new group applies after the next login."
    fi
  fi
  for rule in udev-probe-rs udev-picotool; do
    url="$(pin_field "$rule" linux-any 4)"
    dest="/etc/udev/rules.d/$(basename "$url")"
    [ -f "$dest" ] && continue
    step "USB rule $(basename "$url")"
    say "The rule lets this user open the debug probe or the RP2040 BOOTSEL device with no sudo."
    if ask "Install $dest with sudo?"; then
      file="$(fetch "$rule" linux-any)"
      sudo install -D -m 0644 "$file" "$dest"
      if ! { sudo udevadm control --reload-rules && sudo udevadm trigger; }; then
        say "udev did not reload. The rule applies after the next restart."
      fi
    fi
  done
fi

# ---------------------------------------------------------------- check
step "Check"
FAIL=0
version_of() {
  case "$1" in
    arduino-cli) arduino-cli version 2>&1 | head -n 1 ;;
    "arduino:avr core") arduino-cli core list 2>/dev/null | awk '$1 == "arduino:avr" { print "arduino:avr " $2 }' ;;
    avrdude) avrdude -? 2>&1 | grep -i 'version' | head -n 1 ;;
    espflash) espflash --version 2>&1 | head -n 1 ;;
    probe-rs) probe-rs --version 2>&1 | head -n 1 ;;
    picotool) picotool version 2>&1 | head -n 1 ;;
    mpremote) command -v mpremote ;;
    rust) cargo --version 2>&1 | head -n 1 ;;
    simavr) command -v simavr ;;
    renode) "$(renode_path)" --version 2>&1 | head -n 1 ;;
  esac
}
while IFS='|' read -r name kit _purpose _size; do
  in_kit "$kit" || continue
  if [ -n "$(found_at "$name" </dev/null)" ] && v="$(version_of "$name" </dev/null)" && [ -n "$v" ]; then
    printf '  ok       %-18s %s\n' "$name" "$v"
  elif [ "$name" = probe-rs ] && [ "$PROBE_RS_MODE" = skip ]; then
    printf '  skipped  %-18s needs glibc %s. Install Rust, then run: %s\n' "$name" "$PROBE_RS_MIN_GLIBC" "$(probe_rs_cargo_cmd)"
  else
    printf '  MISSING  %s\n' "$name"
    FAIL=1
  fi
done <<EOF
$TOOL_ROWS
EOF

say ""
case ":$ORIG_PATH:" in
  *":$BIN_DIR:"*) ;;
  *) [ "$OS" = ubuntu ] && say "Open a new terminal, or log out and log in, so that $BIN_DIR is on PATH." ;;
esac
if missing rust; then say "Open a new terminal, so that ~/.cargo/bin is on PATH."; fi
if [ "$FAIL" = 1 ]; then
  say "Some programs are missing. The steps for each program are in docs/INSTALL_TOOLCHAINS.md."
  exit 1
fi
say "Done. Open Oasis Studio. The Hardware page lists these programs."
