import { useCallback, useEffect, useState } from "react";
import { api, errText, type IdentityKind, type NewDevice, type OwnedDevice } from "../api";

const KINDS: { id: IdentityKind; label: string; hint: string }[] = [
  { id: "usb_serial", label: "USB serial number", hint: "From the Hardware page, for example 7C:DF:A1:00:11:22 or 0001" },
  { id: "mac", label: "MAC address", hint: "For a device on your network, from your router's client list" },
  { id: "probe_id", label: "Debug probe id", hint: "The serial number of an ST-LINK or other probe" },
  { id: "hostname", label: "Hostname", hint: "For a computer you reach over SSH, for example pi4.local" },
];

const EMPTY: NewDevice = { name: "", identity_kind: "usb_serial", identity: "", family: null, notes: "", owned: false };

export function Devices() {
  const [devices, setDevices] = useState<OwnedDevice[] | null>(null);
  const [form, setForm] = useState<NewDevice>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.registryList().then(setDevices, (e) => setError(errText(e)));
  }, []);
  useEffect(load, [load]);

  const add = async () => {
    setError(null);
    try {
      await api.registryAdd(form);
      setForm(EMPTY);
      load();
    } catch (e) {
      setError(errText(e));
    }
  };

  const remove = async (d: OwnedDevice) => {
    if (!window.confirm(`Remove ${d.name} from the owned-device list? The app will then refuse to flash or command it.`)) return;
    try {
      await api.registryRemove(d.id);
      load();
    } catch (e) {
      setError(errText(e));
    }
  };

  const kind = KINDS.find((k) => k.id === form.identity_kind)!;

  return (
    <>
      <h2>Owned devices</h2>
      <p className="lede">
        Oasis Studio writes only to devices on this list. A flash or a command to any other device is refused. Add a
        device only if you own it or have the owner's permission to work on it.
      </p>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <h3>Add a device</h3>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <label className="field">Name
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Bench ESP32" />
          </label>
          <label className="field">Identity type
            <select value={form.identity_kind} onChange={(e) => setForm({ ...form, identity_kind: e.target.value as IdentityKind })}>
              {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
            </select>
          </label>
          <label className="field" style={{ flex: 1, minWidth: 220 }}>Identity
            <input className="mono" value={form.identity} onChange={(e) => setForm({ ...form, identity: e.target.value })} placeholder={kind.hint} />
          </label>
        </div>
        <label className="field" style={{ marginTop: 8 }}>Notes
          <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Where it is, what it does" />
        </label>
        <div className="row" style={{ marginTop: 10 }}>
          <label className="row" style={{ gap: 6 }}>
            <input type="checkbox" checked={form.owned} onChange={(e) => setForm({ ...form, owned: e.target.checked })} />
            I own this device, or I have the owner's permission to work on it.
          </label>
          <span className="spacer" />
          <button className="btn primary" onClick={add} disabled={!form.owned || !form.name.trim() || !form.identity.trim()}>Add device</button>
        </div>
      </div>

      <div className="card">
        <h3>List</h3>
        {devices === null ? <p className="muted">Loading…</p> : devices.length === 0 ? (
          <p className="muted">No devices yet.</p>
        ) : (
          <table>
            <thead><tr><th>Name</th><th>Identity</th><th>Added</th><th>Notes</th><th /></tr></thead>
            <tbody>
              {devices.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td className="mono">{d.identity}<div className="muted">{KINDS.find((k) => k.id === d.identity_kind)?.label}</div></td>
                  <td>{new Date(d.declared_owned_at).toLocaleString()}</td>
                  <td>{d.notes}</td>
                  <td><button className="btn danger" onClick={() => remove(d)}>Remove</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
