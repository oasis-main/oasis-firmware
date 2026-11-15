// The assistant column. v0.1 shows what the assistant will do and how it is
// limited. The chat itself comes with account sign-in (next release).

const TOOLS: { name: string; cls: "observe" | "propose"; text: string }[] = [
  { name: "validate_config", cls: "observe", text: "Check a device.yaml and explain each error." },
  { name: "generate_firmware", cls: "propose", text: "Write firmware for a device.yaml into your projects folder." },
  { name: "list_ports", cls: "observe", text: "List connected boards and what each one is." },
  { name: "list_tools", cls: "observe", text: "Check which flash tools are installed." },
  { name: "flash_plan", cls: "propose", text: "Prepare a flash. You review the plan and press Flash yourself." },
];

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
            <span className={t.cls === "observe" ? "ok" : "warn"}>({t.cls === "observe" ? "read" : "you confirm"})</span>
            <div className="muted">{t.text}</div>
          </li>
        ))}
      </ul>
      <div className="lock">
        <b>Chat is not on yet.</b>
        <p className="muted" style={{ marginBottom: 0 }}>
          Sign-in to an Oasis account turns on the chat in a later release. Everything else in Oasis Studio works
          offline, with no account.
        </p>
      </div>
    </aside>
  );
}
