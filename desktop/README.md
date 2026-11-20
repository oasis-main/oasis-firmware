# Oasis Studio (desktop app)

Design a device in a `device.yaml`, generate firmware, run firmware in a
simulator, find boards on USB, and plan a flash. Runs on macOS, Windows, and Linux. Works offline.

- Back end: Rust, Tauri 2 (`src-tauri/`). Links `oasis-core` from the
  repository root.
- Front end: React + Vite + TypeScript (`src/`).
- Board table and flash recipes: `src-tauri/boards.yaml` (data, not code).

## Run

```bash
npm ci
npm run tauri dev
```

Build, test, and release steps: [`docs/STUDIO_RELEASE.md`](../docs/STUDIO_RELEASE.md).

## What v0.1 does

| Page | Function | Class |
|------|----------|-------|
| Hardware | Lists serial ports, USB ids, serial numbers; names the board family from `boards.yaml`; lists installed flash tools | read |
| Design | Validates a `device.yaml`; generates firmware into `Documents/Oasis Studio/<device id>/firmware` | writes files on this computer only |
| Owned devices | The list of devices the app may write to. You add each one and declare ownership | local list |
| Simulate | Runs a firmware file in simavr (Arduino Uno, ATmega328P) or Renode (STM32F103) for a time limit and shows the UART output | runs a simulator on this computer; no hardware |
| Flash | Builds a flash plan: tool, argument list, firmware sha256, and every blocker | plan only, no flash yet |
| Activity log | One JSON line for each change (`audit.jsonl` in the app data folder) | read |

## Safety rules in the code

1. The app writes to a device only if the device is in the owned-device
   list (`src-tauri/src/registry.rs`).
2. The app runs external tools with an argument list. No shell reads the
   arguments (`src-tauri/src/tools.rs`, `src-tauri/src/runner.rs`, tests in
   the same files).
3. Each change writes one line to the activity log.
4. The assistant (later release) calls the same commands as the buttons.
   A flash or a device command always needs your confirm.

The egui prototype that came before this app is in
`legacy/oasis-studio-egui/`.
