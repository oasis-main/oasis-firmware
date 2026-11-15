// Typed calls to the Rust back end (src-tauri/src/lib.rs).
//
// In a plain browser (`npm run dev` without Tauri) there is no back end.
// The app then shows sample data and a "Browser preview" badge, so the UI
// can be checked without a desktop build. Sample data never reaches a device.

import { invoke } from "@tauri-apps/api/core";

export type Confidence = "exact" | "bridge" | "unknown";

export interface AppInfo { version: string; os: string; arch: string; data_dir: string; projects_dir: string }
export interface DetectedPort {
  port: string; kind: string; vid: number | null; pid: number | null;
  serial_number: string | null; manufacturer: string | null; product: string | null;
  family: string | null; confidence: Confidence; label: string | null;
}
export interface ToolStatus { name: string; purpose: string; path: string | null; version: string | null }
export interface Family { family: string; label: string; tool: string; baud: number; chip?: string | null; args: string[] }
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
export interface PlanRequest { port: string; family: string; artifact: string; usb_serial: string | null }
export interface FlashPlan {
  port: string; family: string; tool: string; tool_path: string | null; args: string[];
  artifact: string; artifact_sha256: string | null; owned_device: string | null; blockers: string[];
}

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
  { family: "rp2040", label: "RP2040 (picotool)", tool: "picotool", baud: 115200, args: ["load", "-x", "{artifact}"] },
  { family: "stm32", label: "STM32 over a debug probe (probe-rs)", tool: "probe-rs", baud: 115200, chip: "STM32F103C8", args: ["download", "--chip", "{chip}", "{artifact}"] },
];

async function previewCall<T>(cmd: string, args: Record<string, unknown>): Promise<T> {
  await new Promise((r) => setTimeout(r, 150));
  switch (cmd) {
    case "app_info":
      return { version: "0.1.0", os: "browser", arch: "-", data_dir: "(browser preview)", projects_dir: "(browser preview)" } as T;
    case "list_ports":
      return [
        { port: "/dev/cu.usbmodem1101", kind: "usb", vid: 0x303a, pid: 0x1001, serial_number: "SAMPLE-ESP32S3", manufacturer: "Espressif", product: "USB JTAG/serial debug unit", family: "esp32", confidence: "exact", label: "Espressif native USB (ESP32-S2/S3/C3)" },
        { port: "/dev/cu.usbserial-0001", kind: "usb", vid: 0x10c4, pid: 0xea60, serial_number: "0001", manufacturer: "Silicon Labs", product: "CP2102 USB to UART", family: null, confidence: "bridge", label: "Silicon Labs CP210x USB-UART bridge" },
      ] as T;
    case "list_tools":
      return [
        { name: "cargo", purpose: "Rust build tool (generated firmware)", path: "/sample/bin/cargo", version: "cargo 1.93.1" },
        { name: "espflash", purpose: "ESP32 flash tool", path: null, version: null },
        { name: "probe-rs", purpose: "Debug-probe flash and log tool (STM32, RP2040)", path: null, version: null },
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
      const owned = preview.devices.find((d) => d.identity_kind === "usb_serial" && d.identity === r.usb_serial);
      const blockers = ["Browser preview: the desktop app checks the tool and the firmware file."];
      if (!owned) blockers.push(`USB serial ${r.usb_serial ?? "(none)"} is not in the owned-device list. Add the board on the Devices page first.`);
      log("flash.plan", r.port, "blocked");
      return {
        port: r.port, family: r.family, tool: fam?.tool ?? "", tool_path: null,
        args: (fam?.args ?? []).map((a) => a.replace("{port}", r.port).replace("{artifact}", r.artifact).replace("{chip}", fam?.chip ?? "")),
        artifact: r.artifact, artifact_sha256: null, owned_device: owned?.name ?? null, blockers,
      } as T;
    }
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
  validate: (yaml: string) => call<ValidateResult>("validate_config", { yaml }),
  generate: (yaml: string) => call<GenerateResult>("generate_firmware", { yaml }),
  registryList: () => call<OwnedDevice[]>("registry_list"),
  registryAdd: (device: NewDevice) => call<OwnedDevice>("registry_add", { device }),
  registryRemove: (id: string) => call<void>("registry_remove", { id }),
  auditTail: (limit = 200) => call<AuditEntry[]>("audit_tail", { limit }),
  flashPlan: (request: PlanRequest) => call<FlashPlan>("flash_plan", { request }),
};

export function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function hex4(n: number | null): string {
  return n === null ? "-" : n.toString(16).toUpperCase().padStart(4, "0");
}
