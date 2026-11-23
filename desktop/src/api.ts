// Typed calls to the Rust back end (src-tauri/src/lib.rs).
//
// In a plain browser (`npm run dev` without Tauri) there is no back end.
// The app then shows sample data and a "Browser preview" badge, so the UI
// can be checked without a desktop build. Sample data never reaches a device.

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export type Confidence = "exact" | "bridge" | "unknown";

export interface AppInfo { version: string; os: string; arch: string; data_dir: string; projects_dir: string }
export interface DetectedPort {
  port: string; kind: string; vid: number | null; pid: number | null;
  serial_number: string | null; manufacturer: string | null; product: string | null;
  family: string | null; confidence: Confidence; label: string | null;
}
export interface ToolStatus { name: string; purpose: string; path: string | null; version: string | null }
export interface Simulate {
  engine: string; args: string[]; platform?: string | null; uart?: string | null;
  accepts: string[]; elf_machine?: number | null;
}
export type Transport = "usb" | "probe" | "ssh";
export interface Family {
  family: string; label: string; tool: string; baud: number; chip?: string | null; args: string[];
  transport?: Transport; backup?: { args: string[]; ext: string } | null; probe_arg?: string | null; timeout_s?: number;
  simulate?: Simulate | null;
}
export interface ConfigSummary {
  id: string; name: string; platform: string; model: string; rust_target: string;
  sensors: number; actuators: number; control_loops: number;
}
export interface ValidateResult { ok: boolean; summary: ConfigSummary | null; errors: string[] }
export interface GenerateResult { output_dir: string; files: string[] }
export type IdentityKind = "usb_serial" | "mac" | "probe_id" | "hostname";
export interface OwnedDevice {
  id: string; name: string; identity_kind: IdentityKind; identity: string;
  family: string | null; notes: string; declared_owned_at: string;
}
export interface NewDevice {
  name: string; identity_kind: IdentityKind; identity: string;
  family: string | null; notes: string; owned: boolean;
}
export interface AuditEntry { at: string; actor: string; action: string; target: string; result: string }
export interface PlanRequest {
  port: string; family: string; artifact: string; usb_serial: string | null;
  usb_vid?: number | null; usb_pid?: number | null; device_id?: string | null; fqbn?: string | null;
}
export interface ArduinoPort {
  port: string; vid: number | null; pid: number | null; serial: string | null;
  matches: { name: string; fqbn: string }[];
}
/** True when the family's write arguments name {fqbn} (the arduino-cli family). */
export const needsFqbn = (f: Family | undefined) => !!f?.args.some((a) => a.includes("{fqbn}"));
export interface FlashStep { name: string; program: string; program_path: string | null; args: string[]; summary: string; timeout_s: number }
export interface FlashPlan {
  port: string; family: string; transport: Transport; tool: string; tool_path: string | null; args: string[];
  steps: FlashStep[]; artifact: string; artifact_sha256: string | null; artifact_size: number | null;
  owned_device: string | null; owned_device_id: string | null; backup_method: string | null;
  remote_backup: string | null; fqbn: string | null; blockers: string[];
}
export interface RunRequest { plan: PlanRequest; expected_sha256: string; allow_no_backup: boolean }
export interface FlashLine { run_id: string; step: string; stream: "stdout" | "stderr" | "app"; text: string }
export interface FlashStepResult { name: string; program: string; args: string[]; exit: SimExit | null; seconds: number }
export interface FlashDone {
  run_id: string; ok: boolean; steps: FlashStepResult[]; backup_file: string | null;
  log_file: string | null; report_file: string | null; error: string | null;
}

export interface SimRequest { family: string; artifact: string; seconds: number }
export interface SimPlan {
  family: string; engine: string | null; engine_path: string | null; args: string[]; script: string | null;
  artifact: string; artifact_kind: string | null; artifact_sha256: string | null; seconds: number; blockers: string[];
}
export interface SimLine { run_id: string; kind: "uart" | "log"; text: string }
export type SimExit = { reason: "exited"; code: number | null } | { reason: "time_limit" } | { reason: "stopped" };
export interface SimDone { run_id: string; exit: SimExit; uart_lines: number; truncated: boolean; error: string | null }

export const isDesktop = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

// ---------------------------------------------------------------- preview data
const preview = {
  devices: [] as OwnedDevice[],
  audit: [] as AuditEntry[],
};
const now = () => new Date().toISOString();
const log = (action: string, target: string, result: string) =>
  preview.audit.unshift({ at: now(), actor: "user", action, target, result });

const FAMILIES: Family[] = [
  { family: "esp32", label: "ESP32 (espflash)", tool: "espflash", baud: 115200, args: ["flash", "--port", "{port}", "{artifact}"] },
  { family: "rpi", label: "Raspberry Pi (SSH, systemd)", tool: "ssh", baud: 115200, args: [], transport: "ssh" },
  { family: "rp2040", label: "RP2040 (picotool)", tool: "picotool", baud: 115200, args: ["load", "-v", "-x", "{artifact}"], backup: { args: ["save", "-a", "{backup}"], ext: "uf2" } },
  { family: "stm32", label: "STM32 over a debug probe (probe-rs)", tool: "probe-rs", baud: 115200, chip: "STM32F103C8", args: ["download", "--chip", "{chip}", "{artifact}"],
    simulate: { engine: "renode", args: [], platform: "platforms/cpus/stm32f103.repl", uart: "usart1", accepts: ["elf"], elf_machine: 40 } },
  { family: "avr_uno", label: "Arduino Uno / ATmega328P (avrdude)", tool: "avrdude", baud: 115200, args: ["-p", "atmega328p", "-c", "arduino", "-P", "{port}", "-b", "{baud}", "-U", "flash:w:{artifact}:i"],
    simulate: { engine: "simavr", args: ["-m", "atmega328p", "-f", "16000000", "{artifact}"], accepts: ["elf", "hex"], elf_machine: 83 } },
  { family: "arduino", label: "Arduino board, any model (arduino-cli)", tool: "arduino-cli", baud: 115200,
    args: ["upload", "-v", "--verify", "--port", "{port}", "--fqbn", "{fqbn}", "--input-file", "{artifact}"] },
];

// Browser preview: simulation events go through this target instead of Tauri.
const previewEvents = new EventTarget();
let previewRun: number | null = null;

function previewSimPlan(r: SimRequest): SimPlan {
  const fam = FAMILIES.find((f) => f.family === r.family);
  const blockers: string[] = [];
  if (!fam?.simulate) blockers.push(`The "${r.family}" family has no simulator yet.`);
  if (!r.artifact.trim()) blockers.push("Choose a firmware file.");
  const sim = fam?.simulate;
  return {
    family: r.family, engine: sim?.engine ?? null, engine_path: sim ? `/sample/bin/${sim.engine}` : null,
    args: sim?.engine === "simavr" ? sim.args.map((a) => a.replace("{artifact}", r.artifact))
      : ["--disable-xwt", "--plain", "-e", 'include "{run_dir}/run.resc"'],
    script: sim?.engine === "renode"
      ? `mach create "sim"\nmachine LoadPlatformDescription @${sim.platform}\nsysbus LoadELF "${r.artifact}"\nsysbus.${sim.uart} CreateFileBackend "{run_dir}/uart.txt" true\nemulation RunFor "${r.seconds}"\nquit\n`
      : null,
    artifact: r.artifact, artifact_kind: "elf", artifact_sha256: null, seconds: r.seconds, blockers,
  };
}

function previewSimStart(r: SimRequest): string {
  const plan = previewSimPlan(r);
  if (plan.blockers.length) throw new Error(plan.blockers.join(" "));
  if (previewRun !== null) throw new Error("A simulation is still running. Stop it first.");
  const run_id = `preview-${Date.now()}`;
  const send = (kind: "uart" | "log", text: string) =>
    previewEvents.dispatchEvent(new CustomEvent("line", { detail: { run_id, kind, text } satisfies SimLine }));
  const finish = (exit: SimExit, uart_lines: number) => {
    if (previewRun !== null) clearInterval(previewRun);
    previewRun = null;
    log("sim.run", `${r.family} ${plan.engine}`, `${exit.reason}; ${uart_lines} UART lines`);
    previewEvents.dispatchEvent(new CustomEvent("done", { detail: { run_id, exit, uart_lines, truncated: false, error: null } satisfies SimDone }));
  };
  send("log", "Browser preview: sample output. The desktop app runs the real simulator.");
  let n = 0;
  previewRun = window.setInterval(() => {
    send("uart", r.family === "stm32" ? "oasis f103 hello" : `tick ${n}`);
    n += 1;
    if (r.family === "stm32" || n >= 6) finish({ reason: "exited", code: 0 }, n);
  }, 300);
  previewEvents.addEventListener("stop", () => finish({ reason: "stopped" }, n), { once: true });
  return run_id;
}

async function previewCall<T>(cmd: string, args: Record<string, unknown>): Promise<T> {
  await new Promise((r) => setTimeout(r, 150));
  switch (cmd) {
    case "app_info":
      return { version: "0.1.0", os: "browser", arch: "-", data_dir: "(browser preview)", projects_dir: "(browser preview)" } as T;
    case "list_ports":
      return [
        { port: "/dev/cu.usbmodem1101", kind: "usb", vid: 0x303a, pid: 0x1001, serial_number: "SAMPLE-ESP32S3", manufacturer: "Espressif", product: "USB JTAG/serial debug unit", family: "esp32", confidence: "exact", label: "Espressif native USB (ESP32-S2/S3/C3)" },
        { port: "/dev/cu.usbserial-0001", kind: "usb", vid: 0x10c4, pid: 0xea60, serial_number: "0001", manufacturer: "Silicon Labs", product: "CP2102 USB to UART", family: null, confidence: "bridge", label: "Silicon Labs CP210x USB-UART bridge" },
        { port: "/dev/cu.usbmodem3101", kind: "usb", vid: 0x2341, pid: 0x0042, serial_number: "SAMPLE-MEGA", manufacturer: "Arduino (www.arduino.cc)", product: null, family: null, confidence: "bridge", label: "Arduino board (pick the family; arduino-cli finds the model)" },
      ] as T;
    case "arduino_boards":
      return [
        { port: "/dev/cu.usbmodem3101", vid: 0x2341, pid: 0x0042, serial: "SAMPLE-MEGA", matches: [{ name: "Arduino Mega or Mega 2560", fqbn: "arduino:avr:mega" }] },
        { port: "/dev/cu.usbserial-0001", vid: 0x10c4, pid: 0xea60, serial: "0001", matches: [] },
      ] as T;
    case "list_tools":
      return [
        { name: "cargo", purpose: "Rust build tool (generated firmware)", path: "/sample/bin/cargo", version: "cargo 1.93.1" },
        { name: "espflash", purpose: "ESP32 flash tool", path: null, version: null },
        { name: "probe-rs", purpose: "Debug-probe flash and log tool (STM32, RP2040)", path: null, version: null },
        { name: "simavr", purpose: "AVR simulator (Arduino Uno)", path: "/sample/bin/simavr", version: null },
        { name: "renode", purpose: "STM32 simulator", path: null, version: null },
      ] as T;
    case "list_families":
      return FAMILIES as T;
    case "validate_config": {
      const yaml = String(args.yaml ?? "");
      const id = /\bid:\s*([\w-]+)/.exec(yaml)?.[1];
      if (!id) return { ok: false, summary: null, errors: ["Browser preview: no device.id found. The desktop app runs the real validator."] } as T;
      return { ok: true, errors: [], summary: { id, name: "(preview)", platform: "mcu", model: /model:\s*(\w+)/.exec(yaml)?.[1] ?? "?", rust_target: "(desktop app only)", sensors: (yaml.match(/- name:/g) ?? []).length, actuators: 0, control_loops: 0 } } as T;
    }
    case "generate_firmware":
      throw new Error("Browser preview: generation runs only in the desktop app.");
    case "registry_list":
      return preview.devices as T;
    case "registry_add": {
      const d = args.device as NewDevice;
      if (!d.owned) throw new Error('Tick "I own this device" to add the device.');
      const dev: OwnedDevice = { ...d, id: `dev-${Date.now()}`, declared_owned_at: now() };
      preview.devices.push(dev);
      log("registry.add", d.identity, "ok");
      return dev as T;
    }
    case "registry_remove":
      preview.devices = preview.devices.filter((x) => x.id !== args.id);
      log("registry.remove", String(args.id), "ok");
      return undefined as T;
    case "audit_tail":
      return preview.audit as T;
    case "flash_plan": {
      const r = args.request as PlanRequest;
      const fam = FAMILIES.find((f) => f.family === r.family);
      const ssh = fam?.transport === "ssh";
      const host = r.port.split("@")[1]?.split(":")[0] ?? "";
      const owned = ssh
        ? preview.devices.find((d) => d.identity_kind === "hostname" && d.identity === host)
        : preview.devices.find((d) => d.identity_kind === "usb_serial" && d.identity === r.usb_serial);
      const blockers = [`Browser preview: the desktop app checks the tool and the firmware file${ssh ? ", and builds the SSH steps" : ""}.`];
      if (needsFqbn(fam) && !r.fqbn) blockers.push("An Arduino flash needs the board name (FQBN), for example arduino:avr:mega. Press \"Find board\" or run arduino-cli board list.");
      if (!owned) blockers.push(ssh
        ? `Host ${host || "(none)"} is not in the owned-device list. Add it on the Devices page (identity: Hostname) first.`
        : `USB serial ${r.usb_serial ?? "(none)"} is not in the owned-device list. Add the board on the Devices page first.`);
      log("flash.plan", r.port, "blocked");
      const wargs = (fam?.args ?? []).map((a) => a.replace("{port}", r.port).replace("{artifact}", r.artifact).replace("{chip}", fam?.chip ?? "").replace("{fqbn}", r.fqbn ?? ""));
      return {
        port: r.port, family: r.family, transport: fam?.transport ?? "usb", tool: fam?.tool ?? "", tool_path: null, args: wargs,
        steps: [{ name: "write", program: fam?.tool ?? "", program_path: null, args: wargs, summary: "Write and verify the new firmware.", timeout_s: 180 }],
        artifact: r.artifact, artifact_sha256: null, artifact_size: null, owned_device: owned?.name ?? null, owned_device_id: owned?.id ?? null,
        backup_method: null, remote_backup: null, fqbn: needsFqbn(fam) ? r.fqbn ?? null : null, blockers,
      } as T;
    }
    case "flash_start":
      throw new Error("Browser preview: flashing runs only in the desktop app.");
    case "flash_stop":
      return false as T;
    case "sim_plan":
      return previewSimPlan(args.request as SimRequest) as T;
    case "sim_start":
      return previewSimStart(args.request as SimRequest) as T;
    case "sim_stop":
      previewEvents.dispatchEvent(new Event("stop"));
      return (previewRun !== null) as T;
  }
  throw new Error(`unknown command ${cmd}`);
}

function call<T>(cmd: string, args: Record<string, unknown> = {}): Promise<T> {
  return isDesktop ? invoke<T>(cmd, args) : previewCall<T>(cmd, args);
}

export const api = {
  appInfo: () => call<AppInfo>("app_info"),
  listPorts: () => call<DetectedPort[]>("list_ports"),
  listTools: () => call<ToolStatus[]>("list_tools"),
  listFamilies: () => call<Family[]>("list_families"),
  arduinoBoards: () => call<ArduinoPort[]>("arduino_boards"),
  validate: (yaml: string) => call<ValidateResult>("validate_config", { yaml }),
  generate: (yaml: string) => call<GenerateResult>("generate_firmware", { yaml }),
  registryList: () => call<OwnedDevice[]>("registry_list"),
  registryAdd: (device: NewDevice) => call<OwnedDevice>("registry_add", { device }),
  registryRemove: (id: string) => call<void>("registry_remove", { id }),
  auditTail: (limit = 200) => call<AuditEntry[]>("audit_tail", { limit }),
  flashPlan: (request: PlanRequest) => call<FlashPlan>("flash_plan", { request }),
  flashStart: (request: RunRequest) => call<string>("flash_start", { request }),
  flashStop: () => call<boolean>("flash_stop"),
  simPlan: (request: SimRequest) => call<SimPlan>("sim_plan", { request }),
  simStart: (request: SimRequest) => call<string>("sim_start", { request }),
  simStop: () => call<boolean>("sim_stop"),
};

/** Subscribe to simulation output. Returns a function that ends the subscription. */
export async function onSim(onLine: (l: SimLine) => void, onDone: (d: SimDone) => void): Promise<() => void> {
  if (isDesktop) {
    const a = await listen<SimLine>("sim://line", (e) => onLine(e.payload));
    const b = await listen<SimDone>("sim://done", (e) => onDone(e.payload));
    return () => { a(); b(); };
  }
  const l = (e: Event) => onLine((e as CustomEvent<SimLine>).detail);
  const d = (e: Event) => onDone((e as CustomEvent<SimDone>).detail);
  previewEvents.addEventListener("line", l);
  previewEvents.addEventListener("done", d);
  return () => { previewEvents.removeEventListener("line", l); previewEvents.removeEventListener("done", d); };
}

/** Subscribe to flash output. Returns a function that ends the subscription. */
export async function onFlash(onLine: (l: FlashLine) => void, onDone: (d: FlashDone) => void): Promise<() => void> {
  if (!isDesktop) return () => {};
  const a = await listen<FlashLine>("flash://line", (e) => onLine(e.payload));
  const b = await listen<FlashDone>("flash://done", (e) => onDone(e.payload));
  return () => { a(); b(); };
}

export function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function hex4(n: number | null): string {
  return n === null ? "-" : n.toString(16).toUpperCase().padStart(4, "0");
}
