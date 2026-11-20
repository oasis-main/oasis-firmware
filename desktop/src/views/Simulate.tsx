import { useEffect, useRef, useState } from "react";
import { api, errText, onSim, type Family, type SimDone, type SimLine, type SimPlan } from "../api";

function exitText(d: SimDone): string {
  if (d.error) return `Error: ${d.error}`;
  switch (d.exit.reason) {
    case "exited": return `The simulator exited${d.exit.code === null ? " on a signal" : ` with code ${d.exit.code}`}.`;
    case "time_limit": return "The run reached the time limit.";
    case "stopped": return "You stopped the run.";
  }
}

export function Simulate() {
  const [families, setFamilies] = useState<Family[]>([]);
  const [family, setFamily] = useState("");
  const [artifact, setArtifact] = useState("");
  const [seconds, setSeconds] = useState(5);
  const [plan, setPlan] = useState<SimPlan | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [lines, setLines] = useState<SimLine[]>([]);
  const [done, setDone] = useState<SimDone | null>(null);
  const [showLog, setShowLog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const consoleRef = useRef<HTMLPreElement>(null);
  const runRef = useRef<string | null>(null);

  useEffect(() => {
    api.listFamilies().then((all) => {
      const sims = all.filter((f) => f.simulate);
      setFamilies(sims);
      setFamily((cur) => cur || sims[0]?.family || "");
    }, (e) => setError(errText(e)));
  }, []);

  useEffect(() => {
    let off: (() => void) | undefined;
    let cancelled = false;
    // Only one run exists at a time. Events can arrive before simStart()
    // returns the run id; while the start is pending, the first event names
    // the run.
    const mine = (id: string) => {
      if (runRef.current === "pending") runRef.current = id;
      return runRef.current === id;
    };
    onSim(
      (l) => { if (mine(l.run_id)) setLines((prev) => [...prev, l]); },
      (d) => {
        if (!mine(d.run_id)) return;
        setDone(d);
        setRunId(null);
        runRef.current = `finished:${d.run_id}`;
      },
    ).then((f) => { if (cancelled) f(); else off = f; });
    return () => { cancelled = true; off?.(); };
  }, []);

  useEffect(() => {
    const el = consoleRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines, showLog]);

  const request = () => ({ family, artifact, seconds });

  const check = async () => {
    setError(null);
    try {
      setPlan(await api.simPlan(request()));
    } catch (e) {
      setError(errText(e));
    }
  };

  const run = async () => {
    setError(null);
    setLines([]);
    setDone(null);
    try {
      const p = await api.simPlan(request());
      setPlan(p);
      if (p.blockers.length) return;
      // Set the run id before the first line can arrive.
      runRef.current = "pending";
      const id = await api.simStart(request());
      if (runRef.current !== `finished:${id}`) {
        runRef.current = id;
        setRunId(id);
      }
    } catch (e) {
      runRef.current = null;
      setError(errText(e));
    }
  };

  const stop = async () => {
    try {
      await api.simStop();
    } catch (e) {
      setError(errText(e));
    }
  };

  const fam = families.find((f) => f.family === family);
  const shown = showLog ? lines : lines.filter((l) => l.kind === "uart");
  const uartCount = lines.filter((l) => l.kind === "uart").length;

  return (
    <>
      <h2>Simulate</h2>
      <p className="lede">
        Run a firmware file in a simulator, with no board connected. The app shows the serial (UART) output of the
        firmware. A simulation does not touch hardware. Each run is written to the activity log.
      </p>
      {error && <div className="error">{error}</div>}
      <div className="card">
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field">Board family
            <select value={family} onChange={(e) => { setFamily(e.target.value); setPlan(null); }}>
              {families.length === 0 && <option value="">No family has a simulator</option>}
              {families.map((f) => <option key={f.family} value={f.family}>{f.label}</option>)}
            </select>
          </label>
          <label className="field">Time limit (s)
            <input type="number" min={0.1} max={600} step={0.1} value={seconds} style={{ width: 90 }}
              onChange={(e) => setSeconds(Number(e.target.value))} />
          </label>
          {fam?.simulate && (
            <span className="muted" style={{ paddingBottom: 7 }}>
              Simulator: <span className="mono">{fam.simulate.engine}</span> · accepts {fam.simulate.accepts.map((a) => `.${a}`).join(", ")}
            </span>
          )}
        </div>
        <label className="field" style={{ marginTop: 8 }}>Firmware file (full path)
          <input className="mono" value={artifact} onChange={(e) => { setArtifact(e.target.value); setPlan(null); }}
            placeholder={fam?.simulate?.engine === "renode" ? "/path/to/firmware (ELF)" : "/path/to/sketch.ino.elf"} />
        </label>
        <div className="row" style={{ marginTop: 10 }}>
          <button className="btn" onClick={check} disabled={!family || !!runId}>Check</button>
          <button className="btn primary" onClick={run} disabled={!family || !artifact || !!runId}>Run</button>
          <button className="btn danger" onClick={stop} disabled={!runId}>Stop</button>
          {runId && <span className="muted">Running… {uartCount} lines</span>}
        </div>
      </div>

      {plan && plan.blockers.length > 0 && (
        <div className="card">
          <h3 className="bad">Blocked ({plan.blockers.length})</h3>
          <ul className="plain bad">{plan.blockers.map((b) => <li key={b}>{b}</li>)}</ul>
        </div>
      )}

      {(runId || done || lines.length > 0) && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Serial output</h3>
            <label className="row muted" style={{ gap: 6 }}>
              <input type="checkbox" checked={showLog} onChange={(e) => setShowLog(e.target.checked)} />
              Show simulator messages
            </label>
          </div>
          <pre className="box sim-console" ref={consoleRef}>
            {shown.length === 0 && <span className="muted">{runId ? "Waiting for output…" : "No output."}</span>}
            {shown.map((l, i) => <div key={i} className={l.kind === "log" ? "muted" : undefined}>{l.text || " "}</div>)}
          </pre>
          {done && (
            <p className={done.error ? "bad" : "muted"} style={{ marginBottom: 0 }}>
              {exitText(done)} {done.uart_lines} UART lines{done.truncated ? " (the console shows the first 5000)" : ""}.
            </p>
          )}
        </div>
      )}

      {plan && (
        <div className="card">
          <h3>Plan</h3>
          <table>
            <tbody>
              <tr><th>Simulator</th><td className="mono">{plan.engine_path ?? plan.engine ?? "-"}</td></tr>
              <tr><th>Arguments</th><td><pre className="box">{plan.args.map((a) => JSON.stringify(a)).join("\n")}</pre></td></tr>
              {plan.script && <tr><th>Renode script</th><td><pre className="box">{plan.script}</pre></td></tr>}
              <tr><th>Firmware</th><td className="mono">{plan.artifact_kind ?? "-"} · sha256 {plan.artifact_sha256 ?? "-"}</td></tr>
            </tbody>
          </table>
          <p className="muted">
            Each argument line is one argument. The app passes the list to the simulator directly. No shell reads it.
            <span className="mono"> {"{run_dir}"}</span> is a new folder for each run, in the app data folder.
          </p>
        </div>
      )}
    </>
  );
}
