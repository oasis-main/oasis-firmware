import { useCallback, useEffect, useState } from "react";
import { api, errText, hex4, type DetectedPort, type ToolStatus } from "../api";

const CONF_TEXT = {
  exact: { cls: "ok", text: "board identified" },
  bridge: { cls: "warn", text: "USB bridge only: pick the board" },
  unknown: { cls: "muted", text: "unknown" },
} as const;

export function Hardware({ onFlash, onAdd }: { onFlash: (p: DetectedPort) => void; onAdd: () => void }) {
  const [ports, setPorts] = useState<DetectedPort[] | null>(null);
  const [tools, setTools] = useState<ToolStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setError(null);
    api.listPorts().then(setPorts, (e) => setError(errText(e)));
  }, []);

  useEffect(() => {
    refresh();
    api.listTools().then(setTools, (e) => setError(errText(e)));
  }, [refresh]);

  return (
    <>
      <h2>Hardware</h2>
      <p className="lede">
        Boards on USB and the flash tools on this computer. This page only reads. It does not open a port or write to a
        board.
      </p>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3>Connected ports</h3>
          <button className="btn" onClick={refresh}>Refresh</button>
        </div>
        {ports === null ? (
          <p className="muted">Reading ports…</p>
        ) : ports.length === 0 ? (
          <p className="muted">No serial ports found. Connect a board with a data cable (some USB cables carry power only).</p>
        ) : (
          <table>
            <thead>
              <tr><th>Port</th><th>USB id</th><th>Serial number</th><th>Device</th><th>Detection</th><th /></tr>
            </thead>
            <tbody>
              {ports.map((p) => (
                <tr key={p.port}>
                  <td className="mono">{p.port}</td>
                  <td className="mono">{p.vid === null ? p.kind : `${hex4(p.vid)}:${hex4(p.pid)}`}</td>
                  <td className="mono">{p.serial_number ?? <span className="muted">none</span>}</td>
                  <td>{[p.manufacturer, p.product].filter(Boolean).join(" · ") || <span className="muted">-</span>}<div className="muted">{p.label}</div></td>
                  <td className={CONF_TEXT[p.confidence].cls}>{CONF_TEXT[p.confidence].text}{p.family ? ` (${p.family})` : ""}</td>
                  <td>
                    {p.kind === "usb" && (
                      <div className="row">
                        <button className="btn" onClick={onAdd} title="Add this board to the owned-device list">Own…</button>
                        <button className="btn" onClick={() => onFlash(p)}>Plan flash</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3>Flash tools</h3>
        {tools === null ? (
          <p className="muted">Checking tools…</p>
        ) : (
          <table>
            <thead><tr><th>Tool</th><th>Purpose</th><th>Status</th></tr></thead>
            <tbody>
              {tools.map((t) => (
                <tr key={t.name}>
                  <td className="mono">{t.name}</td>
                  <td>{t.purpose}</td>
                  <td>{t.path ? <span className="ok">{t.version ?? "found"}</span> : <span className="muted">not installed</span>}
                    {t.path && <div className="muted mono">{t.path}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
