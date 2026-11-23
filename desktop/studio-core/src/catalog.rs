//! The tool catalog: one list of assistant tools for the in-app assistant
//! and for MCP clients.
//!
//! Each tool has a class:
//! - `observe`: the tool reads state. The tool changes nothing.
//! - `propose`: the tool prepares a change (a plan, generated files in the
//!   projects folder, or a local simulator run). The tool never writes to a
//!   device. A person confirms each write to a device in the app.
//!
//! The catalog has no tool that flashes a device, sends a command to a
//! device, or adds a row to the owned-device list. A test checks this.
//!
//! The UI reads `desktop/src/tool-catalog.json`. A test checks that the
//! file matches this catalog. To write the file again, run
//! `UPDATE_TOOL_CATALOG=1 cargo test catalog_file_matches`.

use crate::{flash, sim, Actor, Studio};
use serde::Serialize;
use serde_json::{json, Map, Value};
use std::collections::VecDeque;
use std::path::Path;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum ToolClass {
    Observe,
    Propose,
}

pub struct ToolDef {
    pub name: &'static str,
    pub title: &'static str,
    pub class: ToolClass,
    /// One line for the app's assistant panel.
    pub summary: &'static str,
    /// Full text for an agent.
    pub description: &'static str,
    schema: fn() -> Value,
}

impl ToolDef {
    /// JSON Schema of the `arguments` object.
    pub fn input_schema(&self) -> Value {
        (self.schema)()
    }
}

/// Simulated seconds for one `sim_run` call from an assistant. The app's
/// Simulate page allows up to `sim::MAX_SECONDS`.
pub const ASSISTANT_SIM_MAX_SECONDS: f64 = 60.0;
pub const SIM_DEFAULT_LINES: usize = 200;
pub const SIM_MAX_LINES: usize = 2000;
/// Largest device.yaml that `validate_config` and `generate_firmware` read.
pub const MAX_CONFIG_BYTES: u64 = 1024 * 1024;

fn no_args() -> Value {
    json!({ "type": "object", "properties": {}, "additionalProperties": false })
}

fn config_args() -> Value {
    json!({
        "type": "object",
        "properties": {
            "yaml": { "type": "string", "description": "device.yaml text. Give `yaml` or `path`, not both." },
            "path": { "type": "string", "description": "Path to a device.yaml file on this computer, for example examples/greenhouse-demo.yaml. A relative path is relative to the server's working folder." }
        },
        "additionalProperties": false
    })
}

fn audit_args() -> Value {
    json!({
        "type": "object",
        "properties": {
            "limit": { "type": "integer", "minimum": 1, "maximum": 1000, "default": 50, "description": "Number of entries, newest first." }
        },
        "additionalProperties": false
    })
}

fn flash_args() -> Value {
    json!({
        "type": "object",
        "properties": {
            "port": { "type": "string", "description": "Serial port from list_ports, for example /dev/cu.usbmodem1101 or COM3. For the rpi family: user@host or user@host:port of the Raspberry Pi (SSH)." },
            "family": { "type": "string", "description": "Board family from list_families: esp32, rpi, avr_uno, stm32, rp2040, or micropython." },
            "artifact": { "type": "string", "description": "Full path to the firmware file (for rpi: the built supervisor program)." },
            "usb_serial": { "type": "string", "description": "USB serial number of the board or the debug probe, from list_ports. The plan is blocked if this serial is not in the owned-device list." },
            "usb_vid": { "type": "integer", "minimum": 0, "maximum": 65535, "description": "USB vendor id from list_ports. The stm32 family needs it to select the owned probe." },
            "usb_pid": { "type": "integer", "minimum": 0, "maximum": 65535, "description": "USB product id from list_ports. The stm32 family needs it to select the owned probe." },
            "device_id": { "type": "string", "description": "device.id from device.yaml. The rpi family needs it: the program goes to /opt/oasis/<device_id>/." }
        },
        "required": ["port", "family", "artifact"],
        "additionalProperties": false
    })
}

fn sim_plan_args() -> Value {
    json!({
        "type": "object",
        "properties": {
            "family": { "type": "string", "description": "Board family with a simulator: avr_uno (simavr) or stm32 (Renode, STM32F103)." },
            "artifact": { "type": "string", "description": "Path to the firmware file (ELF; simavr also accepts Intel HEX)." },
            "seconds": { "type": "number", "exclusiveMinimum": 0, "maximum": sim::MAX_SECONDS, "default": sim::DEFAULT_SECONDS, "description": "Time limit in simulated seconds." }
        },
        "required": ["family", "artifact"],
        "additionalProperties": false
    })
}

fn sim_run_args() -> Value {
    json!({
        "type": "object",
        "properties": {
            "family": { "type": "string", "description": "Board family with a simulator: avr_uno (simavr) or stm32 (Renode, STM32F103)." },
            "artifact": { "type": "string", "description": "Path to the firmware file (ELF; simavr also accepts Intel HEX)." },
            "seconds": { "type": "number", "exclusiveMinimum": 0, "maximum": ASSISTANT_SIM_MAX_SECONDS, "default": sim::DEFAULT_SECONDS, "description": "Time limit in simulated seconds. The run always ends at this limit." },
            "max_lines": { "type": "integer", "minimum": 1, "maximum": SIM_MAX_LINES, "default": SIM_DEFAULT_LINES, "description": "Number of UART lines in the result (the last lines). The full UART output goes to uart.log in the run folder." }
        },
        "required": ["family", "artifact"],
        "additionalProperties": false
    })
}

static TOOLS: &[ToolDef] = &[
    ToolDef {
        name: "app_info",
        title: "App info",
        class: ToolClass::Observe,
        summary: "Show the version, the OS, and the data and projects folders.",
        description: "Return the Oasis Studio version, the OS and CPU, the data folder (owned-device list, action log, simulation runs), and the projects folder (generated firmware).",
        schema: no_args,
    },
    ToolDef {
        name: "list_ports",
        title: "List serial ports",
        class: ToolClass::Observe,
        summary: "List connected boards and what each one is.",
        description: "List the serial ports on this computer. For a USB port: vendor id, product id, USB serial number, and the board family from the board table, with a confidence (exact, bridge, unknown). Opens no port.",
        schema: no_args,
    },
    ToolDef {
        name: "list_tools",
        title: "List external tools",
        class: ToolClass::Observe,
        summary: "Check which flash tools and simulators are installed.",
        description: "Check which external programs are installed (cargo, espflash, probe-rs, picotool, mpremote, arduino-cli, avrdude, simavr, renode). Returns the path and the version line of each program that is found.",
        schema: no_args,
    },
    ToolDef {
        name: "list_families",
        title: "List board families",
        class: ToolClass::Observe,
        summary: "List the board families, flash recipes, and simulators.",
        description: "List the board families from the board table: flash tool, argument template, baud rate, and the simulator (engine, accepted file kinds) if the family has one.",
        schema: no_args,
    },
    ToolDef {
        name: "validate_config",
        title: "Validate device.yaml",
        class: ToolClass::Observe,
        summary: "Check a device.yaml and explain each error.",
        description: "Parse and validate a device.yaml with oasis-core. Returns ok, a summary (device id, platform, board model, Rust target, counts of sensors, actuators, and control loops), and the errors. Give the text in `yaml` or a file in `path`.",
        schema: config_args,
    },
    ToolDef {
        name: "generate_firmware",
        title: "Generate firmware",
        class: ToolClass::Propose,
        summary: "Write firmware for a device.yaml into your projects folder.",
        description: "Validate a device.yaml and generate a firmware crate into <projects folder>/<device id>/firmware. Replaces the files of an earlier generate for the same device id. Writes no other folder and touches no device. Writes one action-log line.",
        schema: config_args,
    },
    ToolDef {
        name: "registry_list",
        title: "List owned devices",
        class: ToolClass::Observe,
        summary: "List the owned devices that the app may write to.",
        description: "List the owned-device list: the devices that a person declared as owned in the app. A flash plan is blocked unless the board's USB serial number is in this list. No tool adds a device: a person adds each device on the Owned devices page of the app.",
        schema: no_args,
    },
    ToolDef {
        name: "audit_tail",
        title: "Read the action log",
        class: ToolClass::Observe,
        summary: "Read the newest entries of the action log.",
        description: "Return the newest entries of the action log (audit.jsonl), newest first. Each entry: time, actor (user, assistant, or mcp), action, target, result.",
        schema: audit_args,
    },
    ToolDef {
        name: "flash_plan",
        title: "Plan a flash",
        class: ToolClass::Propose,
        summary: "Prepare a flash. You review the plan and press Flash yourself.",
        description: "Build a flash plan: every step (backup, write, and for rpi install, restart, verify) with its program, path, and exact argument list; the firmware sha256; the backup method; the matching owned device; and every blocker. The plan never runs a step. No tool runs a flash: a person reviews the plan and flashes from the Oasis Studio app. Writes one action-log line.",
        schema: flash_args,
    },
    ToolDef {
        name: "sim_plan",
        title: "Plan a simulation",
        class: ToolClass::Observe,
        summary: "Check if a firmware file can run in the simulator for a board family.",
        description: "Check if a firmware file can run in the simulator for a board family. Returns the engine, the engine path, the argument list, the Renode script, the detected file kind, the sha256, and every blocker. Runs nothing.",
        schema: sim_plan_args,
    },
    ToolDef {
        name: "sim_run",
        title: "Run a simulation",
        class: ToolClass::Propose,
        summary: "Run firmware in simavr or Renode and read its serial output. You start the run.",
        description: "Run a firmware file in the local simulator (simavr for avr_uno, Renode for stm32) for a time limit, then return the exit reason (exited, time_limit, stopped) and the last UART lines. One run at a time. A cancel request stops the run. Touches no hardware. Writes one action-log line.",
        schema: sim_run_args,
    },
];

pub fn tools() -> &'static [ToolDef] {
    TOOLS
}

pub fn find(name: &str) -> Option<&'static ToolDef> {
    TOOLS.iter().find(|t| t.name == name)
}

/// The UI file `desktop/src/tool-catalog.json`.
pub fn ui_json() -> Value {
    Value::Array(TOOLS.iter().map(|t| json!({ "name": t.name, "class": t.class, "summary": t.summary })).collect())
}

/// Progress callback: (progress so far, message). The value only grows.
pub type ProgressFn<'a> = &'a (dyn Fn(f64, Option<String>) + Sync);

pub struct CallContext<'a> {
    pub actor: Actor,
    /// Set by the caller to stop a long tool (sim_run).
    pub cancel: Arc<AtomicBool>,
    pub progress: Option<ProgressFn<'a>>,
}

impl CallContext<'_> {
    pub fn new(actor: Actor) -> Self {
        CallContext { actor, cancel: Arc::new(AtomicBool::new(false)), progress: None }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub enum CallError {
    /// No tool has this name.
    UnknownTool(String),
    /// The arguments do not match the input schema.
    InvalidArguments(String),
    /// The tool ran and failed.
    Failed(String),
}

impl std::fmt::Display for CallError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CallError::UnknownTool(n) => write!(f, "Unknown tool: {n}"),
            CallError::InvalidArguments(m) => write!(f, "Invalid arguments: {m}"),
            CallError::Failed(m) => f.write_str(m),
        }
    }
}

type R<T> = Result<T, CallError>;

fn bad(msg: impl Into<String>) -> CallError {
    CallError::InvalidArguments(msg.into())
}

/// Arguments as an object. Refuses a key that the schema does not list.
fn object<'v>(def: &ToolDef, args: &'v Value) -> R<&'v Map<String, Value>> {
    static EMPTY: std::sync::OnceLock<Map<String, Value>> = std::sync::OnceLock::new();
    let map = match args {
        Value::Null => EMPTY.get_or_init(Map::new),
        Value::Object(m) => m,
        _ => return Err(bad("arguments must be an object")),
    };
    let schema = def.input_schema();
    let known = schema["properties"].as_object().cloned().unwrap_or_default();
    if let Some(k) = map.keys().find(|k| !known.contains_key(*k)) {
        let names: Vec<&String> = known.keys().collect();
        return Err(bad(format!("unknown argument \"{k}\" for {}. Known: {names:?}", def.name)));
    }
    if let Some(req) = schema["required"].as_array() {
        for r in req.iter().filter_map(Value::as_str) {
            if !map.contains_key(r) {
                return Err(bad(format!("missing required argument \"{r}\"")));
            }
        }
    }
    Ok(map)
}

fn opt_str<'v>(m: &'v Map<String, Value>, key: &str) -> R<Option<&'v str>> {
    match m.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(s)) => Ok(Some(s)),
        Some(_) => Err(bad(format!("\"{key}\" must be a string"))),
    }
}

fn req_str<'v>(m: &'v Map<String, Value>, key: &str) -> R<&'v str> {
    opt_str(m, key)?.ok_or_else(|| bad(format!("missing required argument \"{key}\"")))
}

fn opt_num(m: &Map<String, Value>, key: &str) -> R<Option<f64>> {
    match m.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => v.as_f64().map(Some).ok_or_else(|| bad(format!("\"{key}\" must be a number"))),
    }
}

fn opt_u16(m: &Map<String, Value>, key: &str) -> R<Option<u16>> {
    match m.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => v.as_u64().and_then(|n| u16::try_from(n).ok()).map(Some).ok_or_else(|| bad(format!("\"{key}\" must be an integer from 0 to 65535"))),
    }
}

fn opt_count(m: &Map<String, Value>, key: &str, max: usize) -> R<Option<usize>> {
    match m.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => match v.as_u64() {
            Some(n) if n >= 1 && n as usize <= max => Ok(Some(n as usize)),
            _ => Err(bad(format!("\"{key}\" must be an integer from 1 to {max}"))),
        },
    }
}

/// device.yaml text from `yaml` or from the file in `path`.
fn config_text(m: &Map<String, Value>) -> R<String> {
    match (opt_str(m, "yaml")?, opt_str(m, "path")?) {
        (Some(y), None) => Ok(y.to_string()),
        (None, Some(p)) => {
            let path = Path::new(p);
            let meta = std::fs::metadata(path).map_err(|e| CallError::Failed(format!("cannot read {p}: {e}")))?;
            if !meta.is_file() {
                return Err(CallError::Failed(format!("{p} is not a file")));
            }
            if meta.len() > MAX_CONFIG_BYTES {
                return Err(CallError::Failed(format!("{p} is larger than {MAX_CONFIG_BYTES} bytes")));
            }
            std::fs::read_to_string(path).map_err(|e| CallError::Failed(format!("cannot read {p}: {e}")))
        }
        (Some(_), Some(_)) => Err(bad("give \"yaml\" or \"path\", not both")),
        (None, None) => Err(bad("give \"yaml\" (the text) or \"path\" (a file)")),
    }
}

fn to_value<T: Serialize>(v: T) -> R<Value> {
    serde_json::to_value(v).map_err(|e| CallError::Failed(e.to_string()))
}

/// Call a tool by name. Both the in-app assistant and the MCP server use
/// this function. `args` is the JSON `arguments` object.
pub fn call(studio: &Studio, name: &str, args: &Value, ctx: &CallContext) -> R<Value> {
    let def = find(name).ok_or_else(|| CallError::UnknownTool(name.to_string()))?;
    let m = object(def, args)?;
    match def.name {
        "app_info" => to_value(studio.app_info()),
        "list_ports" => to_value(studio.list_ports().map_err(CallError::Failed)?),
        "list_tools" => to_value(studio.list_tools()),
        "list_families" => to_value(studio.list_families()),
        "validate_config" => to_value(studio.validate_config(&config_text(m)?)),
        "generate_firmware" => to_value(studio.generate_firmware(&config_text(m)?, ctx.actor).map_err(CallError::Failed)?),
        "registry_list" => to_value(studio.registry_list().map_err(CallError::Failed)?),
        "audit_tail" => to_value(studio.audit_tail(opt_count(m, "limit", 1000)?.unwrap_or(50))),
        "flash_plan" => {
            let req = flash::PlanRequest {
                port: req_str(m, "port")?.into(),
                family: req_str(m, "family")?.into(),
                artifact: req_str(m, "artifact")?.into(),
                usb_serial: opt_str(m, "usb_serial")?.map(Into::into),
                usb_vid: opt_u16(m, "usb_vid")?,
                usb_pid: opt_u16(m, "usb_pid")?,
                device_id: opt_str(m, "device_id")?.map(Into::into),
            };
            to_value(studio.flash_plan(&req, ctx.actor))
        }
        "sim_plan" => {
            let req = sim::SimRequest {
                family: req_str(m, "family")?.into(),
                artifact: req_str(m, "artifact")?.into(),
                seconds: opt_num(m, "seconds")?,
            };
            to_value(studio.sim_plan(&req))
        }
        "sim_run" => sim_run(studio, m, ctx),
        other => Err(CallError::UnknownTool(other.to_string())),
    }
}

#[derive(Serialize)]
struct SimRunResult {
    run_id: String,
    family: String,
    engine: Option<String>,
    seconds: f64,
    /// `{"reason": "exited", "code": 0}`, `{"reason": "time_limit"}`, or
    /// `{"reason": "stopped"}`.
    exit: crate::runner::Exit,
    error: Option<String>,
    /// All UART lines of the run (the app keeps at most `sim::MAX_UART_LINES`).
    uart_line_count: usize,
    /// True if the firmware wrote more than `sim::MAX_UART_LINES` lines.
    uart_truncated: bool,
    /// The last `max_lines` UART lines.
    uart: Vec<String>,
    /// The last simulator messages (not firmware output).
    simulator_log: Vec<String>,
    run_dir: String,
    uart_log: String,
}

fn sim_run(studio: &Studio, m: &Map<String, Value>, ctx: &CallContext) -> R<Value> {
    let seconds = opt_num(m, "seconds")?.unwrap_or(sim::DEFAULT_SECONDS);
    if !(seconds > 0.0 && seconds <= ASSISTANT_SIM_MAX_SECONDS) {
        return Err(bad(format!("\"seconds\" must be more than 0 and not more than {ASSISTANT_SIM_MAX_SECONDS}")));
    }
    let max_lines = opt_count(m, "max_lines", SIM_MAX_LINES)?.unwrap_or(SIM_DEFAULT_LINES);
    let req = sim::SimRequest { family: req_str(m, "family")?.into(), artifact: req_str(m, "artifact")?.into(), seconds: Some(seconds) };
    let ticket = studio.sim_begin(&req, ctx.cancel.clone()).map_err(CallError::Failed)?;
    let run_dir = ticket.run_dir.clone();
    let (family, engine) = (ticket.plan.family.clone(), ticket.plan.engine.clone());

    struct Collected {
        uart: Vec<String>,
        log: VecDeque<String>,
        last_progress: Option<Instant>,
    }
    let collected = Arc::new(Mutex::new(Collected { uart: Vec::new(), log: VecDeque::new(), last_progress: None }));
    // The progress callback borrows from the caller, so it cannot move into
    // the emit closure. The emit closure only collects; this thread reports.
    let finished = Arc::new(AtomicBool::new(false));
    let emit = {
        let c = collected.clone();
        Arc::new(move |line: sim::SimLine| {
            let mut c = c.lock().unwrap_or_else(|p| p.into_inner());
            if line.kind == "uart" {
                c.uart.push(line.text);
            } else {
                c.log.push_back(line.text);
                if c.log.len() > 20 {
                    c.log.pop_front();
                }
            }
        })
    };
    let done = std::thread::scope(|s| {
        if let Some(progress) = ctx.progress {
            let (c, finished) = (collected.clone(), finished.clone());
            s.spawn(move || {
                let mut sent = 0usize;
                while !finished.load(std::sync::atomic::Ordering::SeqCst) {
                    std::thread::sleep(Duration::from_millis(250));
                    let mut c = c.lock().unwrap_or_else(|p| p.into_inner());
                    let n = c.uart.len();
                    let due = c.last_progress.map_or(true, |t| t.elapsed() >= Duration::from_millis(500));
                    if n > sent && due {
                        c.last_progress = Some(Instant::now());
                        let msg = c.uart.last().cloned();
                        drop(c);
                        progress(n as f64, msg);
                        sent = n;
                    }
                }
            });
        }
        let done = studio.sim_execute(ticket, ctx.actor, emit);
        finished.store(true, std::sync::atomic::Ordering::SeqCst);
        done
    });

    let c = collected.lock().unwrap_or_else(|p| p.into_inner());
    let uart_log = run_dir.join("uart.log");
    let mut body = c.uart.join("\n");
    if !body.is_empty() {
        body.push('\n');
    }
    if run_dir.is_dir() {
        let _ = std::fs::write(&uart_log, body);
    }
    let start = c.uart.len().saturating_sub(max_lines);
    to_value(SimRunResult {
        run_id: done.run_id,
        family,
        engine,
        seconds,
        exit: done.exit,
        error: done.error,
        uart_line_count: done.uart_lines,
        uart_truncated: done.truncated,
        uart: c.uart[start..].to_vec(),
        simulator_log: c.log.iter().cloned().collect(),
        run_dir: run_dir.to_string_lossy().into_owned(),
        uart_log: uart_log.to_string_lossy().into_owned(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Paths;

    const EXAMPLE: &str = "../../examples/greenhouse-demo.yaml";

    fn studio() -> (tempfile::TempDir, Studio) {
        let tmp = tempfile::tempdir().unwrap();
        let s = Studio::new(Paths { data_dir: tmp.path().join("data"), projects_dir: tmp.path().join("projects") });
        (tmp, s)
    }

    fn ctx() -> CallContext<'static> {
        CallContext::new(Actor::Mcp)
    }

    #[test]
    fn names_are_unique_and_schemas_are_objects() {
        let mut names: Vec<&str> = tools().iter().map(|t| t.name).collect();
        names.sort();
        names.dedup();
        assert_eq!(names.len(), tools().len());
        for t in tools() {
            let s = t.input_schema();
            assert_eq!(s["type"], "object", "{}", t.name);
            assert_eq!(s["additionalProperties"], false, "{}", t.name);
        }
    }

    #[test]
    fn catalog_has_no_device_write_and_no_registry_add() {
        for t in tools() {
            for word in ["flash_run", "flash_write", "flash_start", "upload", "command", "registry_add", "registry_remove", "write"] {
                assert!(!t.name.contains(word), "tool {} must not be in the catalog", t.name);
            }
        }
        for name in ["registry_add", "registry_remove", "flash", "sim_stop"] {
            assert!(find(name).is_none(), "{name}");
        }
    }

    #[test]
    fn catalog_file_matches() {
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("../src/tool-catalog.json");
        let want = serde_json::to_string_pretty(&ui_json()).unwrap() + "\n";
        if std::env::var_os("UPDATE_TOOL_CATALOG").is_some() {
            std::fs::write(&path, &want).unwrap();
        }
        // A Windows checkout can change line endings to CRLF.
        let got = std::fs::read_to_string(&path).unwrap_or_default().replace("\r\n", "\n");
        assert_eq!(got, want, "desktop/src/tool-catalog.json is out of date. Run UPDATE_TOOL_CATALOG=1 cargo test catalog_file_matches");
    }

    #[test]
    fn validate_config_reads_a_path_or_text() {
        let (_t, s) = studio();
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join(EXAMPLE);
        let v = call(&s, "validate_config", &json!({ "path": path }), &ctx()).unwrap();
        assert_eq!(v["ok"], true, "{v}");
        assert_eq!(v["summary"]["model"], "esp32_devkit");
        let v = call(&s, "validate_config", &json!({ "yaml": "device: [" }), &ctx()).unwrap();
        assert_eq!(v["ok"], false);
    }

    #[test]
    fn argument_errors() {
        let (_t, s) = studio();
        let e = |name: &str, args: Value| call(&s, name, &args, &ctx()).unwrap_err();
        assert!(matches!(e("validate_config", json!({})), CallError::InvalidArguments(_)));
        assert!(matches!(e("validate_config", json!({"yaml": "a", "path": "b"})), CallError::InvalidArguments(_)));
        assert!(matches!(e("validate_config", json!({"yml": "a"})), CallError::InvalidArguments(_)));
        assert!(matches!(e("validate_config", json!([1])), CallError::InvalidArguments(_)));
        assert!(matches!(e("flash_plan", json!({"port": "x", "family": "esp32"})), CallError::InvalidArguments(_)));
        assert!(matches!(e("audit_tail", json!({"limit": 0})), CallError::InvalidArguments(_)));
        assert!(matches!(e("sim_run", json!({"family": "avr_uno", "artifact": "/x", "seconds": 61})), CallError::InvalidArguments(_)));
        assert!(matches!(e("validate_config", json!({"path": "/no/such/file.yaml"})), CallError::Failed(_)));
        assert_eq!(e("flash_now", json!({})), CallError::UnknownTool("flash_now".into()));
    }

    #[test]
    fn generate_writes_into_projects_and_audits_the_actor() {
        let (tmp, s) = studio();
        let path = Path::new(env!("CARGO_MANIFEST_DIR")).join(EXAMPLE);
        let v = call(&s, "generate_firmware", &json!({ "path": path }), &ctx()).unwrap();
        assert!(v["output_dir"].as_str().unwrap().starts_with(tmp.path().join("projects").to_str().unwrap()));
        let log = call(&s, "audit_tail", &json!({ "limit": 5 }), &ctx()).unwrap();
        assert_eq!(log[0]["actor"], "mcp");
        assert_eq!(log[0]["action"], "firmware.generate");
        assert_eq!(log[0]["result"], "ok");
    }

    #[test]
    fn flash_plan_is_blocked_without_an_owned_device_and_audits_the_actor() {
        let (_t, s) = studio();
        let v = call(&s, "flash_plan", &json!({ "port": "/dev/cu.test", "family": "esp32", "artifact": "/no.bin", "usb_serial": "XYZ" }), &ctx()).unwrap();
        let blockers: Vec<&str> = v["blockers"].as_array().unwrap().iter().filter_map(Value::as_str).collect();
        assert!(blockers.iter().any(|b| b.contains("owned-device list")), "{blockers:?}");
        let log = s.audit_tail(1);
        assert_eq!((log[0].actor.as_str(), log[0].action.as_str(), log[0].result.as_str()), ("mcp", "flash.plan", "blocked"));
    }

    #[test]
    fn observe_tools_write_no_log_line() {
        let (_t, s) = studio();
        for name in ["app_info", "list_families", "registry_list", "audit_tail"] {
            call(&s, name, &Value::Null, &ctx()).unwrap();
        }
        call(&s, "sim_plan", &json!({ "family": "avr_uno", "artifact": "/no.elf" }), &ctx()).unwrap();
        assert!(s.audit_tail(10).is_empty());
    }

    #[test]
    fn sim_run_with_a_blocker_fails_and_frees_the_slot() {
        let (_t, s) = studio();
        let e = call(&s, "sim_run", &json!({ "family": "avr_uno", "artifact": "/no/such.elf", "seconds": 1 }), &ctx()).unwrap_err();
        assert!(matches!(&e, CallError::Failed(m) if m.contains("not found")), "{e:?}");
        assert!(!s.sim_stop(), "no run is active");
    }

    /// Runs only when the fixture ELF is set (see `sim::tests`).
    #[test]
    fn sim_run_returns_uart_lines_and_exit_reason() {
        let Ok(fw) = std::env::var("OASIS_SIM_AVR_ELF") else {
            eprintln!("skip: OASIS_SIM_AVR_ELF not set");
            return;
        };
        let (_t, s) = studio();
        let reports = Mutex::new(Vec::new());
        let progress = |p: f64, _m: Option<String>| reports.lock().unwrap().push(p);
        let mut c = ctx();
        c.progress = Some(&progress);
        let v = call(&s, "sim_run", &json!({ "family": "avr_uno", "artifact": fw, "seconds": 2, "max_lines": 3 }), &c).unwrap();
        assert_eq!(v["exit"]["reason"], "time_limit", "{v}");
        let uart: Vec<&str> = v["uart"].as_array().unwrap().iter().filter_map(Value::as_str).collect();
        assert_eq!(uart.len(), 3, "{v}");
        assert!(std::fs::read_to_string(v["uart_log"].as_str().unwrap()).unwrap().contains("tick 0"));
        assert_eq!(s.audit_tail(1)[0].actor, "mcp");
        let r = reports.lock().unwrap();
        assert!(r.windows(2).all(|w| w[0] < w[1]), "progress must grow: {r:?}");
    }
}
