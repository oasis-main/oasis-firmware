import { useEffect, useRef, useState } from "react";
import {
  api, errText, needsFqbn, onFlash, type DetectedPort, type Family, type FlashDone, type FlashLine, type FlashPlan, type PlanRequest,
} from "../api";

function exitText(e: FlashDone["steps"][number]["exit"]): string {
  if (!e) return "did not start";
  switch (e.reason) {
    case "exited": return e.code === 0 ? "ok" : e.code === null ? "stopped by a signal" : `exit code ${e.code}`;
    case "time_limit": return "time limit";
    case "stopped": return "stopped";
  }
}

export function Flash({ port }: { port: DetectedPort | null }) {
  const [families, setFamilies] = useState<Family[]>([]);
  const [portName, setPortName] = useState(port?.port ?? "");
  const [usbSerial, setUsbSerial] = useState(port?.serial_number ?? "");
  const [family, setFamily] = useState(port?.family ?? "");
  const [artifact, setArtifact] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [fqbn, setFqbn] = useState("");
  const [boardNote, setBoardNote] = useState<string | null>(null);
  const [finding, setFinding] = useState(false);
  const [plan, setPlan] = useState<FlashPlan | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [noBackupOk, setNoBackupOk] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [lines, setLines] = useState<FlashLine[]>([]);
  const [done, setDone] = useState<FlashDone | null>(null);
  const [error, setError] = useState<string | null>(null);
  const runRef = useRef<string | null>(null);
  const consoleRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    api.listFamilies().then(setFamilies, (e) => setError(errText(e)));
  }, []);

  useEffect(() => {
    let off: (() => void) | undefined;
    let cancelled = false;
    // One flash at a time. Events can arrive before flashStart() returns.
    const mine = (id: string) => {
      if (runRef.current === "pending") runRef.current = id;
      return runRef.current === id;
    };
    onFlash(
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
  }, [lines]);

  const fam = families.find((f) => f.family === family);
  const ssh = fam?.transport === "ssh";
  const arduino = needsFqbn(fam);

  const request = (): PlanRequest => ({
    port: portName,
    family,
    artifact,
    usb_serial: ssh ? null : usbSerial || null,
    usb_vid: ssh ? null : port?.vid ?? null,
    usb_pid: ssh ? null : port?.pid ?? null,
    device_id: ssh ? deviceId || null : null,
    fqbn: arduino ? fqbn.trim() || null : null,
  });

  // Ask arduino-cli which board model is on the port. The command only reads.
  const findBoard = async () => {
    setError(null);
    setBoardNote(null);
    setFinding(true);
    try {
      const ports = await api.arduinoBoards();
      const hit = ports.find((p) => p.port === portName);
      if (!hit) {
        setBoardNote(`arduino-cli found no USB serial port with the name ${portName}. Check the port name.`);
      } else if (hit.matches.length === 0) {
        setBoardNote("arduino-cli does not know the board model on this port. Install the core of the board (arduino-cli core install <core>), or type the FQBN.");
      } else {
        setFqbn(hit.matches[0].fqbn);
        if (!usbSerial && hit.serial) setUsbSerial(hit.serial);
        setPlan(null);
        setBoardNote(hit.matches.length === 1
          ? `arduino-cli found ${hit.matches[0].name}.`
          : `arduino-cli found more than one model: ${hit.matches.map((m) => `${m.name} (${m.fqbn})`).join(", ")}. The first one is filled in. Change it if necessary.`);
      }
    } catch (e) {
      setError(errText(e));
    } finally {
      setFinding(false);
    }
  };

  const makePlan = async () => {
    setError(null);
    setDone(null);
    try {
      setPlan(await api.flashPlan(request()));
    } catch (e) {
      setError(errText(e));
    }
  };

  const startFlash = async () => {
    if (!plan?.artifact_sha256) return;
    setConfirming(false);
    setError(null);
    setLines([]);
    setDone(null);
    try {
      runRef.current = "pending";
      const id = await api.flashStart({ plan: request(), expected_sha256: plan.artifact_sha256, allow_no_backup: noBackupOk });
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
      await api.flashStop();
    } catch (e) {
      setError(errText(e));
    }
  };

  const bridgeOnly = port?.confidence === "bridge" && !family;
  const canFlash = !!plan && plan.blockers.length === 0 && !!plan.artifact_sha256 && !runId;

  return (
    <>
      <h2>Flash</h2>
      <p className="lede">
        Write firmware to a board that you own. The app builds a plan with every step and its exact arguments. You
        confirm the plan, and then the app saves the current firmware (when the board family has a backup method),
        writes the new firmware, and checks the result. Each flash is written to the activity log.
      </p>
      {error && <div className="error">{error}</div>}
      <div className="card">
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field">Board family
            <select value={family} onChange={(e) => { setFamily(e.target.value); setPlan(null); }} disabled={!!runId}>
              <option value="">Pick a family…</option>
              {families.map((f) => <option key={f.family} value={f.family}>{f.label}</option>)}
            </select>
          </label>
          <label className="field" style={{ minWidth: 240 }}>{ssh ? "Pi address (user@host or user@host:port)" : "Port"}
            <input className="mono" value={portName} onChange={(e) => { setPortName(e.target.value); setPlan(null); }} disabled={!!runId}
              placeholder={ssh ? "oasis@pi4.local" : "/dev/cu.usbmodem1101 or COM3"} />
          </label>
          {ssh ? (
            <label className="field">Device id (device.yaml)
              <input className="mono" value={deviceId} onChange={(e) => { setDeviceId(e.target.value); setPlan(null); }} disabled={!!runId} placeholder="greenhouse-01" />
            </label>
          ) : (
            <label className="field">USB serial
              <input className="mono" value={usbSerial} onChange={(e) => { setUsbSerial(e.target.value); setPlan(null); }} disabled={!!runId} />
            </label>
          )}
        </div>
        <label className="field" style={{ marginTop: 8 }}>{ssh ? "Program file (full path)" : "Firmware file (full path)"}
          <input className="mono" value={artifact} onChange={(e) => { setArtifact(e.target.value); setPlan(null); }} disabled={!!runId}
            placeholder={ssh ? "/path/to/greenhouse-01-supervisor" : "/path/to/firmware.bin"} />
        </label>
        {arduino && (
          <div className="row" style={{ alignItems: "flex-end", marginTop: 8 }}>
            <label className="field" style={{ minWidth: 280 }}>Board name (FQBN)
              <input className="mono" value={fqbn} onChange={(e) => { setFqbn(e.target.value); setPlan(null); }} disabled={!!runId} placeholder="arduino:avr:mega" />
            </label>
            <button className="btn" onClick={findBoard} disabled={!portName || finding || !!runId}>{finding ? "Finding…" : "Find board"}</button>
          </div>
        )}
        {arduino && boardNote && <div className="notice">{boardNote}</div>}
        {arduino && (
          <div className="notice">
            arduino-cli writes the firmware with the upload tool of the board core. arduino-cli cannot read the current
            firmware, so this family has no backup. For an Arduino Uno with a backup, pick "Arduino Uno / ATmega328P".
          </div>
        )}
        {bridgeOnly && <div className="notice">This port is a USB-UART bridge. The bridge does not identify the board. Pick the board family.</div>}
        {ssh && (
          <div className="notice">
            The Pi must accept your SSH key, and its host key must be in your known_hosts file. The app never asks for a
            password. The SSH user needs write access to <span className="mono">/opt/oasis/&lt;device id&gt;/</span> and
            permission to run <span className="mono">sudo systemctl restart</span> for the service with no password.
          </div>
        )}
        <div className="row" style={{ marginTop: 10 }}>
          <button className="btn" onClick={makePlan} disabled={!portName || !family || !artifact || !!runId}>Build plan</button>
          <button className="btn primary" onClick={() => { setNoBackupOk(false); setConfirming(true); }} disabled={!canFlash}>Flash…</button>
          <button className="btn danger" onClick={stop} disabled={!runId}>Stop</button>
          {runId && <span className="muted">Flashing… {lines.filter((l) => l.stream !== "app").length} lines</span>}
        </div>
      </div>

      {confirming && plan && (
        <div className="card confirm" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
          <h3 id="confirm-title">Flash {plan.owned_device}?</h3>
          <table>
            <tbody>
              <tr><th>Owned device</th><td>{plan.owned_device}</td></tr>
              <tr><th>Family</th><td>{fam?.label ?? plan.family}</td></tr>
              {plan.fqbn && <tr><th>Board name</th><td className="mono">{plan.fqbn}</td></tr>}
              <tr><th>{ssh ? "Pi address" : "Port"}</th><td className="mono">{plan.port}</td></tr>
              <tr><th>Firmware</th><td className="mono">{plan.artifact}<div className="muted">sha256 {plan.artifact_sha256} · {plan.artifact_size ?? "?"} bytes</div></td></tr>
              <tr><th>Steps</th><td>{plan.steps.map((s) => s.name).join(" → ")}</td></tr>
              <tr><th>Backup</th><td>{plan.backup_method ?? <span className="bad">No backup method for this family.</span>}</td></tr>
            </tbody>
          </table>
          {!plan.backup_method && (
            <label className="row" style={{ gap: 6, marginTop: 8 }}>
              <input type="checkbox" checked={noBackupOk} onChange={(e) => setNoBackupOk(e.target.checked)} />
              I accept a flash with no backup. The current firmware on the board will be lost.
            </label>
          )}
          <p className="muted">Do not disconnect the board during the flash. A stopped write can leave the board with no working firmware.</p>
          <div className="row">
            <button className="btn" autoFocus onClick={() => setConfirming(false)}>Cancel</button>
            <button className="btn primary" onClick={startFlash} disabled={!plan.backup_method && !noBackupOk}>Flash now</button>
          </div>
        </div>
      )}

      {(runId || done || lines.length > 0) && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Output</h3>
          <pre className="box sim-console" ref={consoleRef}>
            {lines.length === 0 && <span className="muted">Waiting for output…</span>}
            {lines.map((l, i) => (
              <div key={i} className={l.stream === "app" ? "muted" : l.stream === "stderr" ? "warn" : undefined}>
                <span className="muted">[{l.step}]</span> {l.text || " "}
              </div>
            ))}
          </pre>
          {done && (
            <>
              <h3 className={done.ok ? "ok" : "bad"}>{done.ok ? "Flash complete" : "Flash failed"}</h3>
              {done.error && <p className="bad">{done.error}</p>}
              <table>
                <tbody>
                  {done.steps.map((s) => (
                    <tr key={s.name}><th>{s.name}</th><td>{exitText(s.exit)}{s.exit ? ` · ${s.seconds.toFixed(1)} s` : ""}</td></tr>
                  ))}
                  <tr><th>Backup</th><td className="mono">{done.backup_file ?? "-"}</td></tr>
                  <tr><th>Report</th><td className="mono">{done.report_file ?? "-"}</td></tr>
                  <tr><th>Log</th><td className="mono">{done.log_file ?? "-"}</td></tr>
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {plan && (
        <div className="card">
          <h3 className={plan.blockers.length ? "bad" : "ok"}>
            {plan.blockers.length ? `Blocked (${plan.blockers.length})` : "Ready: press Flash… to review and confirm"}
          </h3>
          {plan.blockers.length > 0 && <ul className="plain bad">{plan.blockers.map((b) => <li key={b}>{b}</li>)}</ul>}
          <table style={{ marginTop: 8 }}>
            <tbody>
              <tr><th>Owned device</th><td>{plan.owned_device ?? <span className="muted">not matched</span>}</td></tr>
              {plan.fqbn && <tr><th>Board name</th><td className="mono">{plan.fqbn}</td></tr>}
              <tr><th>Firmware sha256</th><td className="mono">{plan.artifact_sha256 ?? "-"}</td></tr>
              <tr><th>Backup</th><td>{plan.backup_method ?? <span className="warn">No backup method for this family yet.</span>}</td></tr>
              {plan.steps.map((s) => (
                <tr key={s.name}>
                  <th>{s.name}</th>
                  <td>
                    <div>{s.summary}</div>
                    <div className="mono muted">{s.program_path ?? `${s.program} (not found)`}</div>
                    <pre className="box">{s.args.map((a) => JSON.stringify(a)).join("\n")}</pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            Each argument line is one argument. The app passes the list to the program directly. No shell on this
            computer reads it. <span className="mono">{"{backup}"}</span> becomes a new file in the app data folder.
          </p>
        </div>
      )}
    </>
  );
}
