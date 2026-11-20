// The assistant column. v0.1 shows what the assistant will do and how it is
// limited. The chat itself comes with account sign-in (next release).
//
// The tool list comes from the shared tool catalog
// (desktop/studio-core/src/catalog.rs). The MCP server oasis-studio-mcp
// gives MCP clients the same list. A Rust test keeps tool-catalog.json in
// step with the catalog.

import catalog from "../tool-catalog.json";

type ToolClass = "observe" | "propose";
const TOOLS = catalog as { name: string; class: ToolClass; summary: string }[];

export function AssistantPanel() {
  return (
    <aside className="assistant" aria-label="Assistant">
      <h3>Assistant</h3>
      <p className="muted">
        The assistant uses the same tools as the buttons in this app. It can read. It can prepare a change. Only you
        can confirm a flash or a command to a device.
      </p>
      <ul className="plain">
        {TOOLS.map((t) => (
          <li key={t.name}>
            <span className="tool">{t.name}</span>{" "}
            <span className={t.class === "observe" ? "ok" : "warn"}>({t.class === "observe" ? "read" : "you confirm"})</span>
            <div className="muted">{t.summary}</div>
          </li>
        ))}
      </ul>
      <div className="lock">
        <b>Chat is not on yet.</b>
        <p className="muted" style={{ marginBottom: 0 }}>
          Sign-in to an Oasis account turns on the chat in a later release. Everything else in Oasis Studio works
          offline, with no account. Agents outside the app can use the same tools through the MCP server
          (oasis-studio-mcp).
        </p>
      </div>
    </aside>
  );
}
