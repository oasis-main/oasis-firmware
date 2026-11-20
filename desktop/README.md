# Oasis Studio (desktop app)

Design a device in a `device.yaml`, generate firmware, run firmware in a
simulator, find boards on USB, and plan a flash. Runs on macOS, Windows, and Linux. Works offline.

- Back end: Rust, Tauri 2 (`src-tauri/`). The Tauri commands are thin
  wrappers over the tool registry.
- Tool registry: `studio-core/` (crate `oasis-studio-core`). Ports, tools,
  board table, validation, generation, flash plan, simulation, owned-device
  list, action log. Links `oasis-core` from the repository root.
- MCP server: `oasis-studio-mcp`, a binary in `studio-core/`. Gives MCP
  clients the same tools. See "For AI agents" in the root
  [README.md](../README.md#for-ai-agents).
- Front end: React + Vite + TypeScript (`src/`). The assistant panel reads
  `src/tool-catalog.json`, a copy of the tool catalog that a test checks.
- Board table and flash recipes: `studio-core/boards.yaml` (data, not code).

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
   list (`studio-core/src/registry.rs`).
2. The app runs external tools with an argument list. No shell reads the
   arguments (`studio-core/src/tools.rs`, `studio-core/src/runner.rs`, tests
   in the same files).
3. Each change writes one line to the activity log, with the actor
   (`user`, `assistant`, or `mcp`).
4. The assistant (later release) and MCP clients call the same functions as
   the buttons (`studio-core/src/catalog.rs`). A flash or a device command
   always needs your confirm. The catalog has no tool that flashes, sends a
   device command, or adds an owned device.

The egui prototype that came before this app is in
`legacy/oasis-studio-egui/`.
