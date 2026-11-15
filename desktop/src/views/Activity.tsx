import { useEffect, useState } from "react";
import { api, errText, type AppInfo, type AuditEntry } from "../api";

export function Activity({ info }: { info: AppInfo | null }) {
  const [rows, setRows] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.auditTail(200).then(setRows, (e) => setError(errText(e)));
  useEffect(() => { load(); }, []);

  return (
    <>
      <h2>Activity log</h2>
      <p className="lede">
        One line for each action that changes something: a device added or removed, firmware generated, a flash
        planned. The file is <span className="mono">{info ? `${info.data_dir}/audit.jsonl` : "audit.jsonl"}</span>.
      </p>
      {error && <div className="error">{error}</div>}
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3>Latest first</h3>
          <button className="btn" onClick={load}>Refresh</button>
        </div>
        {rows === null ? <p className="muted">Loading…</p> : rows.length === 0 ? <p className="muted">No actions yet.</p> : (
          <table>
            <thead><tr><th>Time</th><th>Who</th><th>Action</th><th>Target</th><th>Result</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.at}-${i}`}>
                  <td>{new Date(r.at).toLocaleString()}</td>
                  <td>{r.actor}</td>
                  <td className="mono">{r.action}</td>
                  <td className="mono">{r.target}</td>
                  <td className={r.result === "ok" || r.result === "ready" ? "ok" : "warn"}>{r.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
