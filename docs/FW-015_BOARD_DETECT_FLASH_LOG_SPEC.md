# FW-015 — Board detect, flash recipe, log capture (spec, draft)

Status: DRAFT for review. Spec only; no code, nothing compiled (no cargo on the author's host).
Scope: hardware terminal, oasis-firmware/desktop (oasis-studio, egui 0.27).
Verification levels use the FW-013 tags: placeholder < compiles < sim-validated < hw-validated.
Everything below is `placeholder` until built; anything that touches a real board is `hw-validated` only after a human with a board runs it.

## 1. Where the app is today (read from desktop/src/panels/deploy.rs, state.rs)

- The Deploy tab is a static mock. Port and baud combo boxes bind to temporary literals (`&mut "/dev/ttyUSB0"`), so a selection cannot persist. The radio buttons bind to `&mut "usb"`, which also cannot change.
- "Refresh Ports", "Build Firmware", "Flash to Device", "Test Connection" have empty bodies ("Would ...").
- The only state is `DeploymentStatus { Idle, Building, Flashing, Verifying, Success, Failed(String) }` and `DeployTarget { method, host, port, user }` as strings.
- The build output pane prints canned text per status, not real output.
- `docs/DESKTOP_APP_DESIGN.md` plans `services/{serial,build,flash}.rs` with `serialport`, `which`, espflash/probe-rs. None exist yet.

FW-015 therefore means building the services layer behind the existing panel, in this order.

## 2. Scope and non-goals

In: USB board detection, a flash recipe per board family, build and flash as supervised child processes, live log capture to the UI and to a file, a report of the run.
Out (this FW): OTA over MQTT, SSH/rsync deploy to RPi (kept as existing stubs), auto-flashing anything not selected by the user, any flashing without an explicit button press plus a confirm dialog naming the port and board.

## 3. Board detection (`services/serial.rs`)

- Enumerate with `serialport::available_ports()`; keep `UsbPortInfo { vid, pid, serial_number, manufacturer, product }`.
- Match (vid:pid) against a table in `desktop/boards.yaml` (data, not code, so it can be extended without a rebuild). Candidate rows, **to be verified against vendor docs before use**:
  - Espressif native USB (ESP32-S2/S3/C3): vid 0x303A. Flash tool: espflash.
  - Common USB-UART bridges used on ESP32 dev boards: CP210x (10C4:EA60), CH340 (1A86:7523), FTDI (0403:6001). These do not identify the board, only the bridge, so the result is "ESP-class candidate", and the user confirms the model.
  - RP2040 BOOTSEL mass storage (2E8A:0003) and RP2040 CDC (2E8A:000A): flash by UF2 copy or picotool.
  - STM32 ST-LINK (0483:3748 / 374B): flash with probe-rs.
  - Arduino/ATmega bridges: avrdude, serial-port route.
- Output type: `DetectedBoard { port, vid, pid, serial, family: Option<Family>, confidence: Exact | BridgeOnly | Unknown }`.
- Rule: `BridgeOnly` and `Unknown` never enable the Flash button until the user picks a family from a drop-down.
- Hot-plug: poll every 1 s on a background thread, send diffs over a channel to `AppState.ports` (no blocking the egui frame). "Refresh Ports" forces an immediate poll.
- Linux permission failures (dialout/uucp group, udev rules) are detected on open and shown as a specific message with the fix, not as a generic error.

## 4. Flash recipe (`services/flash.rs`)

A recipe is a declarative struct stored per family in `boards.yaml`:

```
family: esp32s3
tool: espflash          # espflash | probe-rs | picotool | uf2-copy | avrdude
tool_min_version: "3.0"
args: ["flash", "--port", "{port}", "--baud", "{baud}", "{artifact}"]
artifact: target/{target_triple}/release/{bin}
pre: []                 # e.g. hold-BOOT instructions shown to user
verify: tool-native     # tool's own verify, then a boot banner check (section 5)
timeout_s: 120
```

Steps, each one a state in `DeploymentStatus` (add `Detecting`, keep the rest):
1. Preflight: tool found via `which`, version >= min, artifact exists, port still present. Fail early with a named reason.
2. Confirm dialog: board family, port, serial number, artifact path and sha256. Default focus on Cancel.
3. Flash: spawn the tool as a child process, stream stdout/stderr line by line to the log pane. Cancel button sends SIGTERM, then SIGKILL after 3 s.
4. Verify: tool-native verify, then reopen the port and wait up to 10 s for the boot banner or the first expected log line (section 5).
5. Report (section 6).

Rules: one flash at a time; the app never retries a failed flash on its own; the app never erases or writes anything except the selected artifact to the selected port. Bootloader/eFuse/security operations are not exposed.

## 5. Log capture (`services/serial.rs` monitor half)

- Open the selected port (default 115200 8N1, per-family override in `boards.yaml`) on a reader thread; bounded channel (e.g. 10k lines) to the UI. Drop-oldest with a visible "N lines dropped" counter if the UI lags.
- Each line stored as `{ host_monotonic_ms, host_utc, raw_bytes_lossy_utf8 }`. Host timestamps only; the device clock is not trusted.
- Tee to `logs/{board_serial}_{utc}.log` (append, flushed per line) so a crash of the app keeps the capture. Rotate at 50 MB.
- Parsers, optional and layered on the raw log (never replacing it): ESP-IDF log level prefixes (`E (123) tag:`), panic/backtrace detection, and a JSON-line sensor format for the FW-012/014 fusion output so a log can be replayed through the fusion filter.
- Monitor pane: autoscroll toggle, level filter, text filter, Clear, Save As. Send-line input is off by default.
- Reconnect: if the port disappears (reset, re-enumeration after flash), keep the pane open and re-attach when the same serial number reappears, within 15 s.

## 6. Report

Written next to the log as `report_{utc}.json` and shown in the UI:

```
{ "board": {family, vid, pid, serial}, "tool": {name, version},
  "artifact": {path, sha256, size}, "flash": {ok, seconds, exit_code},
  "verify": {banner_seen, seconds}, "log_file": "...", "app_version": "...",
  "level": "hw-validated | not-run" }
```

`level` is `hw-validated` only when a real flash plus verify succeeded on a detected board. A simulated or dry-run report is marked `dry-run` and cannot carry that tag. This feeds the FW-013 driver status tags.

## 7. Dry-run / test seams (so this is testable without a board)

- Trait `PortSource` (real = serialport, fake = scripted list) and `Runner` (real = process, fake = canned stdout/exit code). The detection table, recipe expansion (`{port}` substitution), preflight, state machine, line parser, log rotation and reconnect logic are all unit-testable with fakes. These can reach `compiles` and `sim-validated` without hardware.
- A `--dry-run` flag runs the full flow with the fake runner and prints the exact command line it would run. No process is spawned against a real port in dry-run.

## 8. Milestones

- L1 (compiles): `services/` skeleton, traits, `boards.yaml` loader, recipe expansion, state machine with unit tests; deploy.rs bound to real state (fixes the literal-binding bug in section 1).
- L2 (sim-validated): detection with fake ports, log capture with a pty pair or a fake source, dry-run end to end.
- L3 (real USB, no flashing): enumerate and monitor a board that is already running, read-only.
- L4 (hw-validated): flash + verify on a bench board. **Needs the maintainer's bench device and a human on USB/SWD.** Out of reach for automation; project policy bars flashing any device that is not the maintainer's bench board.

## 9. Open questions for Mike

1. Which boards are on the bench for L3/L4 (family and model)? The vid:pid table in section 3 is a starting list, not a statement of what you own.
2. Is the egui-vs-alternative decision still open? This spec is toolkit-neutral for `services/`; only the Deploy and Monitor panels depend on egui.
3. Is host-side timestamping enough for the kart consumer (FW-012), or does the device need to send a monotonic counter in the log lines?
4. Do you want cargo/crates and espflash/probe-rs egress for the bot host so L1 and L2 can at least compile and run in tests? Without it, this lane produces spec and unreviewed code only.

## 10. Risks

- vid:pid table entries are from memory and unverified; treat as hypotheses until checked against vendor listings.
- espflash and probe-rs CLI flags change between major versions; the recipe pins `tool_min_version` for that reason, and flag syntax in section 4 is illustrative.
- Nothing here has been compiled or run.
