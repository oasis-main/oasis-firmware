# Oasis Firmware Deployment Guide

This document covers flashing and deployment techniques for all supported platforms.

## Platform Overview

| Platform | Primary Method | OTA Method | Toolchain |
|----------|----------------|------------|-----------|
| ESP32 | USB serial (`espflash`) | MQTT or HTTPS | Rust + esp-idf |
| STM32 | Debug probe (`probe-rs`) | DFU bootloader | Rust + embassy |
| Arduino | USB serial (`arduino-cli`) | Limited | C++ |
| RPi/SBC | SSH + rsync | MQTT trigger | Rust + tokio |

---

## MCU Deployment (ESP32, STM32)

### Prerequisites

```bash
# ESP32 tooling
cargo install espflash
cargo install espup
espup install

# STM32/ARM tooling  
cargo install probe-rs-tools

# Arduino (optional)
brew install arduino-cli  # macOS
```

### USB Serial Flashing (ESP32)

```bash
# Build firmware
cd generated/greenhouse-node-01
cargo build --release

# Flash to device
espflash flash target/xtensa-esp32-none-elf/release/greenhouse_node_01-firmware

# Monitor serial output
espflash monitor
```

### Debug Probe Flashing (STM32)

```bash
# Build firmware
cargo build --release

# Flash via ST-Link or J-Link
probe-rs run --chip STM32F411CEUx target/thumbv7em-none-eabihf/release/firmware

# Debug with RTT logging
probe-rs attach --chip STM32F411CEUx target/thumbv7em-none-eabihf/release/firmware
```

### device.yaml Deployment Config

```yaml
deployment:
  flash_method: usb_serial
  target_address: "/dev/ttyUSB0"  # or auto-detect
```

---

## Raspberry Pi / SBC Deployment

### Method 1: SSH + Rsync (Recommended for Development)

```bash
# Cross-compile for aarch64
cargo build --release --target aarch64-unknown-linux-gnu

# Deploy via rsync
rsync -avz --progress \
  target/aarch64-unknown-linux-gnu/release/greenhouse_node_01-supervisor \
  oasis@greenhouse-rpi.local:/opt/oasis/

# Restart service
ssh oasis@greenhouse-rpi.local "sudo systemctl restart greenhouse_node_01"
```

### Method 2: systemd Service

The generated firmware includes a systemd service file:

```bash
# On the RPi
sudo cp greenhouse_node_01.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable greenhouse_node_01
sudo systemctl start greenhouse_node_01

# View logs
journalctl -u greenhouse_node_01 -f
```

### Method 3: Docker Deployment

```dockerfile
# Generated Dockerfile
FROM rust:1.75-slim-bookworm AS builder
WORKDIR /app
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/greenhouse_node_01-supervisor /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/greenhouse_node_01-supervisor"]
```

```bash
# Build and push
docker build -t oasis/greenhouse-node-01:latest .
docker push oasis/greenhouse-node-01:latest

# On RPi
docker pull oasis/greenhouse-node-01:latest
docker run -d --privileged --name greenhouse oasis/greenhouse-node-01:latest
```

### device.yaml Deployment Config

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

---

## Over-the-Air (OTA) Updates

### MQTT-Based OTA (ESP32)

1. **Device subscribes** to `oasis/devices/{device_id}/ota`
2. **Cloud publishes** firmware metadata:
   ```json
   {
     "version": "1.2.0",
     "url": "https://firmware.oasis-x.io/greenhouse-node-01/1.2.0.bin",
     "sha256": "abc123...",
     "signature": "..."
   }
   ```
3. **Device downloads** firmware, verifies signature, applies update
4. **Device reports** status to `oasis/devices/{device_id}/ota/status`

### HTTPS-Based OTA (RPi)

```yaml
deployment:
  ota:
    endpoint: "https://firmware.oasis-x.io/api/v1/check"
    signing_key: "./keys/firmware_signing.pem"
    require_signature: true
```

The supervisor polls the endpoint periodically and self-updates when new firmware is available.

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Deploy Firmware

on:
  push:
    branches: [main]
    paths:
      - 'devices/greenhouse-node-01/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust + ESP toolchain
        run: |
          curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
          cargo install espup espflash
          espup install
          
      - name: Build firmware
        run: |
          cd devices/greenhouse-node-01
          cargo build --release
          
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: firmware
          path: target/*/release/*-firmware

  simulate:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Run Wokwi simulation
        uses: wokwi/wokwi-ci-action@v1
        with:
          token: ${{ secrets.WOKWI_CLI_TOKEN }}
          path: devices/greenhouse-node-01
          scenario: test_scenarios/normal.json
          timeout: 30000
```

---

## Deployment Commands (oasis-build CLI)

```bash
# Generate with deployment config
oasis-build generate \
  --config greenhouse-monitor.yaml \
  --output ./out \
  --with-simulation

# Future: Direct deployment
oasis-build deploy \
  --config greenhouse-monitor.yaml \
  --target greenhouse-rpi.local
```

---

## Security Considerations

1. **Firmware Signing**: Always sign firmware for OTA updates
2. **Secure Boot**: Enable on ESP32 for production devices
3. **SSH Keys**: Use dedicated deploy keys, not personal SSH keys
4. **API Keys**: Store in environment variables, never commit to git
5. **TLS**: Always use TLS for MQTT (port 8883) and HTTPS endpoints
