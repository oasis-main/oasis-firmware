# AGENTS.md

Instructions for AI agents (Claude Code, Claude Desktop, Cursor, and other
MCP clients) that work in this repository.

Read the "For AI agents" section of [README.md](README.md#for-ai-agents).
The section gives the install steps for each OS, the MCP server build and
registration, the tool list with classes, the safety rules, and the test
commands.

Short form:

1. Build the MCP server from the repository root:
   `cargo build --release --locked --manifest-path desktop/studio-core/Cargo.toml --bin oasis-studio-mcp`
2. Register the server. Claude Code:
   `claude mcp add oasis-studio -- "$PWD/desktop/studio-core/target/release/oasis-studio-mcp"`
3. Run the tests:
   `cargo test --locked --manifest-path desktop/studio-core/Cargo.toml`

Rules:

- No MCP tool writes to a device or runs a flash. `flash_plan` only shows a
  plan.
- No MCP tool adds an owned device. A person adds each device in the
  Oasis Studio app.
- Each change writes one line with actor `mcp` to the action log
  (`audit.jsonl`).
- The tool list is in `desktop/studio-core/src/catalog.rs`. The desktop app
  and the MCP server use the same functions. Add a tool there, not in the
  Tauri commands, and run
  `UPDATE_TOOL_CATALOG=1 cargo test --manifest-path desktop/studio-core/Cargo.toml catalog_file_matches`
  to update `desktop/src/tool-catalog.json`.

`README_FOR_AI_AGENTS.md` is an older project overview. Where it and
README.md do not agree, README.md is correct.
