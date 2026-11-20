import { useEffect, useState } from "react";
import { api, isDesktop, type AppInfo, type DetectedPort } from "./api";
import { AssistantPanel } from "./components/AssistantPanel";
import { Hardware } from "./views/Hardware";
import { Design } from "./views/Design";
import { Devices } from "./views/Devices";
import { Flash } from "./views/Flash";
import { Simulate } from "./views/Simulate";
import { Activity } from "./views/Activity";
import icon from "../app-icon.svg";

export type ViewId = "hardware" | "design" | "simulate" | "devices" | "flash" | "activity";

const NAV: { group: string; items: { id: ViewId; label: string }[] }[] = [
  { group: "Build", items: [{ id: "design", label: "Design" }, { id: "simulate", label: "Simulate" }, { id: "flash", label: "Flash" }] },
  { group: "Reach", items: [{ id: "hardware", label: "Hardware" }, { id: "devices", label: "Owned devices" }] },
  { group: "Record", items: [{ id: "activity", label: "Activity log" }] },
];

export function App() {
  const [view, setView] = useState<ViewId>("hardware");
  const [info, setInfo] = useState<AppInfo | null>(null);
  // A port picked on the Hardware page carries over to the Flash page.
  const [flashPort, setFlashPort] = useState<DetectedPort | null>(null);

  useEffect(() => {
    api.appInfo().then(setInfo, () => setInfo(null));
  }, []);

  const toFlash = (p: DetectedPort) => {
    setFlashPort(p);
    setView("flash");
  };

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">
          <img src={icon} alt="" /> Oasis Studio
        </span>
        <span className="badge">v{info?.version ?? "…"}</span>
        {!isDesktop && <span className="badge warn" title="No desktop back end. The app shows sample data.">Browser preview</span>}
        <span className="spacer" />
        {info && isDesktop && <span className="muted">{info.os} · {info.arch}</span>}
      </header>
      <div className="workspace">
        <nav className="nav" aria-label="Views">
          {NAV.map((g) => (
            <div key={g.group}>
              <div className="group">{g.group}</div>
              {g.items.map((it) => (
                <button key={it.id} className={view === it.id ? "active" : ""} onClick={() => setView(it.id)}>
                  {it.label}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <main className="view">
          {view === "hardware" && <Hardware onFlash={toFlash} onAdd={() => setView("devices")} />}
          {view === "design" && <Design info={info} />}
          {view === "simulate" && <Simulate />}
          {view === "devices" && <Devices />}
          {view === "flash" && <Flash port={flashPort} />}
          {view === "activity" && <Activity info={info} />}
        </main>
        <AssistantPanel />
      </div>
    </div>
  );
}
