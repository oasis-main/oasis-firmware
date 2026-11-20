# oasis-studio-core

The tool registry of Oasis Studio, and the MCP server `oasis-studio-mcp`.

Setup and client configuration: "For AI agents" in the root
[README.md](../../README.md#for-ai-agents).

## Layout

| File | Contents |
|------|----------|
| `src/lib.rs` | `Studio`: the functions behind each Tauri command and each tool. `Paths`, `Actor`. |
| `src/catalog.rs` | The tool catalog (name, class, description, input schema) and `call`, the one dispatcher for assistant tools. |
| `src/mcp.rs` | MCP protocol: `initialize`, `ping`, `tools/list`, `tools/call`, progress, cancel. No I/O. |
| `src/bin/oasis-studio-mcp.rs` | stdio transport for `mcp.rs`. |
| `src/{boards,device,flash,ports,registry,runner,sim,tools}.rs` | Board table, device.yaml, flash plan, serial ports, owned-device list and action log, program runner, simulators, tool discovery. |
| `boards.yaml` | Board table and flash recipes (data). |
| `tests/mcp_stdio.rs` | End-to-end test: starts the binary and sends JSON-RPC over stdio. |

## Design decisions

1. One registry for two front ends. The Tauri app (`desktop/src-tauri`)
   and the MCP server link this crate. The Tauri commands are thin
   wrappers over `Studio`. The MCP server calls `catalog::call`, which
   calls `Studio`. A change to a tool changes both front ends.
2. A separate crate with its own `Cargo.lock`, not a Cargo workspace. A
   workspace at `desktop/` would move the Tauri `target/` folder and the
   lock file, and the release workflow uses those paths. The MCP server
   also builds without the Tauri system packages (WebKitGTK on Linux).
3. The MCP protocol code is in this crate (about 250 lines), not in an
   SDK crate. The server uses only stdio, `tools/*`, progress, and cancel.
   The code has no async runtime and adds no dependency to the app.
4. The catalog has no tool that writes to a device, runs a flash, or adds
   an owned device. `registry_add` stays a Tauri command for the Owned
   devices page only. Tests in `catalog.rs` check this.
5. `sim_run` blocks until the run ends, with a time limit of not more
   than 60 simulated seconds (`ASSISTANT_SIM_MAX_SECONDS`). Renode gets 60
   s more wall time for start-up. The server runs each `tools/call` on its
   own thread, so `ping` and `notifications/cancelled` work during a run.

## The Python server in `simulation/mcp_server.py`

Decision: keep it as a separate, experimental server. Do not wrap it.

- The Python server controls the behavioral runtime and the emulator
  wrappers (GPIO, UART send, steps). `oasis-studio-mcp` does not cover
  these functions.
- The Python server does not follow the safety rules of this crate: no
  action log, no time limit on emulator runs, sessions that stay open.
  A wrapper would give these tools the look of the checked tools.
- The Python server uses protocol version `2024-11-05` and answers only
  `initialize`, `tools/list`, and `tools/call`. The server sent an error
  response to each notification, which JSON-RPC 2.0 does not allow. This
  change stops that response. There is no `ping`.

If a Python tool becomes part of the product, add it to `catalog.rs`
with a class, a time limit, and an action-log line.

## Tests

```bash
cargo test --locked
UPDATE_TOOL_CATALOG=1 cargo test catalog_file_matches   # after a catalog change
```
