import { useState } from "react";
import { api, errText, type AppInfo, type GenerateResult, type ValidateResult } from "../api";
import starter from "../starter-device.yaml?raw";

export function Design({ info }: { info: AppInfo | null }) {
  const [yaml, setYaml] = useState(starter);
  const [result, setResult] = useState<ValidateResult | null>(null);
  const [gen, setGen] = useState<GenerateResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const validate = async () => {
    setError(null);
    setGen(null);
    try {
      setResult(await api.validate(yaml));
    } catch (e) {
      setError(errText(e));
    }
  };

  const generate = async () => {
    setError(null);
    setBusy(true);
    try {
      setGen(await api.generate(yaml));
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>Design</h2>
      <p className="lede">
        Describe the device in a device.yaml: the board, the sensors, the actuators, and the control loops. Validate
        the file, then generate firmware. Output goes to <span className="mono">{info?.projects_dir ?? "your projects folder"}</span>.
      </p>
      <div className="card">
        <textarea
          className="code"
          spellCheck={false}
          value={yaml}
          onChange={(e) => { setYaml(e.target.value); setResult(null); setGen(null); }}
          aria-label="device.yaml"
        />
        <div className="row" style={{ marginTop: 10 }}>
          <button className="btn" onClick={validate}>Validate</button>
          <button className="btn primary" onClick={generate} disabled={!result?.ok || busy}>
            {busy ? "Generating…" : "Generate firmware"}
          </button>
          <button className="btn" onClick={() => { setYaml(starter); setResult(null); setGen(null); }}>Reset to starter</button>
        </div>
        {error && <div className="error">{error}</div>}
      </div>

      {result && (
        <div className="card">
          <h3 className={result.ok ? "ok" : "bad"}>{result.ok ? "Valid" : "Not valid"}</h3>
          {result.errors.length > 0 && <ul className="plain bad">{result.errors.map((e) => <li key={e}>{e}</li>)}</ul>}
          {result.summary && (
            <table>
              <tbody>
                <tr><th>Device</th><td>{result.summary.id} · {result.summary.name}</td></tr>
                <tr><th>Board</th><td>{result.summary.platform} / {result.summary.model}</td></tr>
                <tr><th>Rust target</th><td className="mono">{result.summary.rust_target || "(no target for this board)"}</td></tr>
                <tr><th>Parts</th><td>{result.summary.sensors} sensors · {result.summary.actuators} actuators · {result.summary.control_loops} control loops</td></tr>
              </tbody>
            </table>
          )}
        </div>
      )}

      {gen && (
        <div className="card">
          <h3 className="ok">Firmware written</h3>
          <p className="mono">{gen.output_dir}</p>
          <pre className="box">{gen.files.join("\n")}</pre>
        </div>
      )}
    </>
  );
}
