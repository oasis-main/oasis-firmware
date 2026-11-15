import { useEffect, useState } from "react";
import { api, errText, type DetectedPort, type Family, type FlashPlan } from "../api";

export function Flash({ port }: { port: DetectedPort | null }) {
  const [families, setFamilies] = useState<Family[]>([]);
  const [portName, setPortName] = useState(port?.port ?? "");
  const [usbSerial, setUsbSerial] = useState(port?.serial_number ?? "");
  const [family, setFamily] = useState(port?.family ?? "");
  const [artifact, setArtifact] = useState("");
  const [plan, setPlan] = useState<FlashPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listFamilies().then(setFamilies, (e) => setError(errText(e)));
  }, []);

  const makePlan = async () => {
    setError(null);
    try {
      setPlan(await api.flashPlan({ port: portName, family, artifact, usb_serial: usbSerial || null }));
    } catch (e) {
      setError(errText(e));
    }
  };

  const bridgeOnly = port?.confidence === "bridge" && !family;

  return (
    <>
      <h2>Flash</h2>
      <p className="lede">
        Build a flash plan: the tool, the exact arguments, and the firmware hash. The plan lists every reason the
        flash cannot run. This release shows the plan only. The supervised flash run comes next.
      </p>
      {error && <div className="error">{error}</div>}
      <div className="card">
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field" style={{ minWidth: 220 }}>Port
            <input className="mono" value={portName} onChange={(e) => setPortName(e.target.value)} placeholder="/dev/cu.usbmodem1101 or COM3" />
          </label>
          <label className="field">USB serial
            <input className="mono" value={usbSerial} onChange={(e) => setUsbSerial(e.target.value)} />
          </label>
          <label className="field">Board family
            <select value={family} onChange={(e) => setFamily(e.target.value)}>
              <option value="">Pick a family…</option>
              {families.map((f) => <option key={f.family} value={f.family}>{f.label}</option>)}
            </select>
          </label>
        </div>
        <label className="field" style={{ marginTop: 8 }}>Firmware file (full path)
          <input className="mono" value={artifact} onChange={(e) => setArtifact(e.target.value)} placeholder="/path/to/firmware.bin" />
        </label>
        {bridgeOnly && <div className="notice">This port is a USB-UART bridge. The bridge does not identify the board. Pick the board family.</div>}
        <div className="row" style={{ marginTop: 10 }}>
          <button className="btn primary" onClick={makePlan} disabled={!portName || !family || !artifact}>Build plan</button>
        </div>
      </div>

      {plan && (
        <div className="card">
          <h3 className={plan.blockers.length ? "bad" : "ok"}>
            {plan.blockers.length ? `Blocked (${plan.blockers.length})` : "Ready: confirm to flash (next release)"}
          </h3>
          {plan.blockers.length > 0 && <ul className="plain bad">{plan.blockers.map((b) => <li key={b}>{b}</li>)}</ul>}
          <table style={{ marginTop: 8 }}>
            <tbody>
              <tr><th>Owned device</th><td>{plan.owned_device ?? <span className="muted">not matched</span>}</td></tr>
              <tr><th>Tool</th><td className="mono">{plan.tool_path ?? plan.tool}</td></tr>
              <tr><th>Arguments</th><td><pre className="box">{plan.args.map((a) => JSON.stringify(a)).join("\n")}</pre></td></tr>
              <tr><th>Firmware sha256</th><td className="mono">{plan.artifact_sha256 ?? "-"}</td></tr>
            </tbody>
          </table>
          <p className="muted">Each line above is one argument. The app passes the list to the tool directly. No shell reads it.</p>
        </div>
      )}
    </>
  );
}
