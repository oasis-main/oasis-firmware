//! Flash plan and flash run (FW-015 sections 3, 4, and 6).
//!
//! A plan lists every step (program, path, exact argument list), the
//! firmware hash, the matching owned device, and every reason the flash
//! cannot run. A plan runs nothing.
//!
//! A run executes the steps of a plan in order: backup (read the current
//! firmware), write, and the steps after the write for a Raspberry Pi
//! (install, restart, verify). The run stops at the first step that fails.
//! Only a person starts a run, from the Oasis Studio app (`Studio::flash_begin`
//! refuses any other actor). The MCP server has no tool that runs a flash.
//!
//! Rules (same as `tools.rs` and `runner.rs`): each program gets an argument
//! list; no local shell reads it. For a Raspberry Pi, `ssh` sends one remote
//! command to the shell on the Pi. The app builds that command only from
//! values that pass `safe_token`, so the command has no quotes, spaces, or
//! shell characters from the user.

use crate::boards::{self, Family, Transport};
use crate::registry::{IdentityKind, OwnedDevice, Store};
use crate::runner::{self, Exit, Stream};
use crate::tools;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Deserialize)]
pub struct PlanRequest {
    /// Serial port (usb), any port of the probe (probe), or `user@host` /
    /// `user@host:port` (ssh).
    pub port: String,
    pub family: String,
    pub artifact: String,
    /// USB serial number of the board or the probe, from the port list.
    pub usb_serial: Option<String>,
    /// USB vendor and product id, from the port list. A probe family needs
    /// them to select the owned probe.
    #[serde(default)]
    pub usb_vid: Option<u16>,
    #[serde(default)]
    pub usb_pid: Option<u16>,
    /// `device.id` from device.yaml. A Raspberry Pi needs it: the app installs
    /// the program in `/opt/oasis/<device_id>/`.
    #[serde(default)]
    pub device_id: Option<String>,
    /// Fully qualified board name for arduino-cli, for example
    /// `arduino:avr:mega`. A family whose args name `{fqbn}` needs it.
    #[serde(default)]
    pub fqbn: Option<String>,
}

/// One program run in a flash.
#[derive(Debug, Clone, Serialize)]
pub struct Step {
    /// backup, write, install, restart, verify.
    pub name: String,
    pub program: String,
    pub program_path: Option<String>,
    /// One entry for each argument. `{backup}` is replaced at run time with
    /// the backup file path.
    pub args: Vec<String>,
    pub summary: String,
    /// Seconds before the app stops the step.
    pub timeout_s: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct FlashPlan {
    pub port: String,
    pub family: String,
    pub transport: Transport,
    pub tool: String,
    pub tool_path: Option<String>,
    /// Arguments of the write step.
    pub args: Vec<String>,
    pub steps: Vec<Step>,
    pub artifact: String,
    pub artifact_sha256: Option<String>,
    pub artifact_size: Option<u64>,
    pub owned_device: Option<String>,
    pub owned_device_id: Option<String>,
    /// How the run saves the current firmware first. None: no backup method
    /// for this family yet; the person must accept a flash with no backup.
    pub backup_method: Option<String>,
    /// Raspberry Pi: the path of the backup copy on the Pi.
    pub remote_backup: Option<String>,
    /// arduino-cli board name (FQBN) that the write step uses.
    pub fqbn: Option<String>,
    /// Empty means the plan can run (after the person confirms).
    pub blockers: Vec<String>,
}

/// Replace `{key}` placeholders in one pass. A value that itself contains
/// `{...}` is not read again.
pub fn fill(template: &str, vars: &[(&str, &str)]) -> String {
    let mut out = String::with_capacity(template.len());
    let mut rest = template;
    while let Some(start) = rest.find('{') {
        out.push_str(&rest[..start]);
        let after = &rest[start + 1..];
        match after.find('}').map(|end| (&after[..end], end)) {
            Some((key, end)) if vars.iter().any(|(k, _)| *k == key) => {
                out.push_str(vars.iter().find(|(k, _)| *k == key).map(|(_, v)| *v).unwrap_or(""));
                rest = &after[end + 1..];
            }
            _ => {
                out.push('{');
                rest = after;
            }
        }
    }
    out.push_str(rest);
    out
}

pub fn substitute(template: &[String], port: &str, baud: u32, artifact: &str, chip: Option<&str>) -> Vec<String> {
    substitute_with(template, port, baud, artifact, chip, None)
}

fn substitute_with(template: &[String], port: &str, baud: u32, artifact: &str, chip: Option<&str>, fqbn: Option<&str>) -> Vec<String> {
    let baud = baud.to_string();
    let vars = [("port", port), ("baud", baud.as_str()), ("artifact", artifact), ("chip", chip.unwrap_or("")), ("fqbn", fqbn.unwrap_or(""))];
    template.iter().map(|a| fill(a, &vars)).collect()
}

/// True when the family's write arguments name `{fqbn}` (arduino-cli).
pub fn needs_fqbn(fam: &Family) -> bool {
    fam.args.iter().any(|a| a.contains("{fqbn}"))
}

/// An arduino-cli board name: `vendor:architecture:board`, with an optional
/// fourth part of board options `key=value,key=value`. Each name part has
/// only letters, digits, `_`, `-`, `.`, and does not start with `-`.
pub fn valid_fqbn(s: &str) -> bool {
    let part = |p: &str| {
        !p.is_empty() && p.len() <= 64 && !p.starts_with('-') && p.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.'))
    };
    let parts: Vec<&str> = s.split(':').collect();
    match parts.as_slice() {
        [v, a, b] => part(v) && part(a) && part(b),
        [v, a, b, opts] => {
            part(v) && part(a) && part(b) && opts.split(',').all(|kv| kv.split_once('=').is_some_and(|(k, val)| part(k) && part(val)))
        }
        _ => false,
    }
}

pub(crate) fn sha256_file(p: &Path) -> Option<String> {
    let bytes = std::fs::read(p).ok()?;
    let digest = Sha256::digest(&bytes);
    Some(digest.iter().map(|b| format!("{b:02x}")).collect())
}

/// A value that may go into the remote command on a Raspberry Pi: letters,
/// digits, `.`, `_`, `-`; not empty; does not start with `-` or `.`.
pub fn safe_token(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= 64
        && !s.starts_with('-')
        && !s.starts_with('.')
        && s.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SshTarget {
    pub user: String,
    pub host: String,
    pub port: Option<u16>,
}

/// Parse `user@host` or `user@host:port`. IPv6 addresses are not accepted.
pub fn parse_ssh_target(s: &str) -> Result<SshTarget, String> {
    let (user, rest) = s.split_once('@').ok_or("Write the Raspberry Pi address as user@host, for example oasis@pi4.local.")?;
    let (host, port) = match rest.rsplit_once(':') {
        Some((h, p)) => (h, Some(p.parse::<u16>().ok().filter(|p| *p > 0).ok_or("The SSH port must be a number from 1 to 65535.")?)),
        None => (rest, None),
    };
    let user_ok = !user.is_empty()
        && user.len() <= 32
        && user.chars().next().is_some_and(|c| c.is_ascii_lowercase() || c == '_')
        && user.chars().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || matches!(c, '_' | '-'));
    if !user_ok {
        return Err(format!("\"{user}\" is not a valid Linux user name."));
    }
    let host_ok = !host.is_empty()
        && host.len() <= 253
        && host.chars().next().is_some_and(|c| c.is_ascii_alphanumeric())
        && host.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-'));
    if !host_ok {
        return Err(format!("\"{host}\" is not a valid host name or IPv4 address."));
    }
    Ok(SshTarget { user: user.into(), host: host.into(), port })
}

fn ssh_options() -> Vec<String> {
    // BatchMode: key login only; ssh never asks for a password, so the app
    // never handles one. StrictHostKeyChecking: the Pi must already be in
    // known_hosts (the person trusted its host key before).
    ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10"].map(String::from).to_vec()
}

fn find_owned(store: &Store, kinds: &[IdentityKind], identity: Option<&str>) -> Option<OwnedDevice> {
    let id = identity.filter(|s| !s.is_empty())?;
    kinds.iter().find_map(|k| store.find_by_identity(*k, id))
}

pub fn plan(req: &PlanRequest, store: &Store, actor: &str) -> FlashPlan {
    let mut p = FlashPlan {
        port: req.port.clone(),
        family: req.family.clone(),
        transport: Transport::Usb,
        tool: String::new(),
        tool_path: None,
        args: vec![],
        steps: vec![],
        artifact: req.artifact.clone(),
        artifact_sha256: None,
        artifact_size: None,
        owned_device: None,
        owned_device_id: None,
        backup_method: None,
        remote_backup: None,
        fqbn: None,
        blockers: vec![],
    };
    let Some(fam) = boards::family(&req.family) else {
        p.blockers.push(format!("Unknown board family \"{}\". Pick a family from the list.", req.family));
        return p;
    };
    p.family = fam.family.clone();
    p.transport = fam.transport;
    p.tool = fam.tool.clone();

    let tool_path = tools::find(&fam.tool);
    if tool_path.is_none() {
        p.blockers.push(format!("{} is not installed or not on PATH.", fam.tool));
    }
    p.tool_path = tool_path.as_ref().map(|t| t.to_string_lossy().into_owned());

    let artifact = Path::new(&req.artifact);
    if !artifact.is_absolute() {
        p.blockers.push("Give the firmware file as a full path.".into());
    }
    if artifact.is_file() {
        p.artifact_sha256 = sha256_file(artifact);
        p.artifact_size = std::fs::metadata(artifact).ok().map(|m| m.len());
    }
    if p.artifact_sha256.is_none() {
        p.blockers.push(format!("Firmware file not found: {}", req.artifact));
    }

    match fam.transport {
        Transport::Usb | Transport::Probe => plan_local(fam, req, store, &mut p),
        Transport::Ssh => plan_ssh(fam, req, store, &mut p),
    }

    store.audit(actor, "flash.plan", &req.port, if p.blockers.is_empty() { "ready" } else { "blocked" });
    p
}

fn plan_local(fam: &Family, req: &PlanRequest, store: &Store, p: &mut FlashPlan) {
    let kinds: &[IdentityKind] =
        if fam.transport == Transport::Probe { &[IdentityKind::ProbeId, IdentityKind::UsbSerial] } else { &[IdentityKind::UsbSerial] };
    let owned = find_owned(store, kinds, req.usb_serial.as_deref());
    if owned.is_none() {
        p.blockers.push(match req.usb_serial.as_deref() {
            Some(s) if !s.is_empty() => format!("USB serial {s} is not in the owned-device list. Add the board on the Devices page first."),
            _ => "The board reports no USB serial number, so the app cannot match it to the owned-device list.".into(),
        });
    }
    p.owned_device = owned.as_ref().map(|d| d.name.clone());
    p.owned_device_id = owned.as_ref().map(|d| d.id.clone());

    let fqbn = if needs_fqbn(fam) {
        match req.fqbn.as_deref().map(str::trim).filter(|s| !s.is_empty()) {
            Some(f) if valid_fqbn(f) => Some(f.to_string()),
            Some(f) => {
                p.blockers.push(format!("\"{f}\" is not a valid board name (FQBN). Write it as vendor:architecture:board, for example arduino:avr:mega."));
                None
            }
            None => {
                p.blockers.push("An Arduino flash needs the board name (FQBN), for example arduino:avr:mega. Press \"Find board\" or run arduino-cli board list.".into());
                None
            }
        }
    } else {
        None
    };
    p.fqbn = fqbn.clone();
    let sub = |t: &[String]| substitute_with(t, &req.port, fam.baud, &req.artifact, fam.chip.as_deref(), fqbn.as_deref());
    let mut write = sub(&fam.args);
    let mut backup = fam.backup.as_ref().map(|b| sub(&b.args));
    if let Some(flag) = &fam.probe_arg {
        // Select the owned probe, so that the tool cannot write to another
        // probe on the same computer.
        match (req.usb_vid, req.usb_pid, req.usb_serial.as_deref().filter(|s| !s.is_empty())) {
            (Some(v), Some(pid), Some(serial)) => {
                let sel = format!("{v:04x}:{pid:04x}:{serial}");
                // After the subcommand (probe-rs download --probe ...).
                for list in std::iter::once(&mut write).chain(backup.iter_mut()) {
                    list.splice(1..1, [flag.clone(), sel.clone()]);
                }
            }
            _ => p.blockers.push("A probe flash needs the probe's USB vendor id, product id, and serial number. Pick the probe on the Hardware page.".into()),
        }
    }
    let path = p.tool_path.clone();
    if let (Some(b), Some(args)) = (&fam.backup, backup) {
        p.backup_method = Some(format!("{} reads the current firmware into a .{} file", fam.tool, b.ext));
        p.steps.push(Step {
            name: "backup".into(),
            program: fam.tool.clone(),
            program_path: path.clone(),
            args,
            summary: "Save the firmware that is on the board now.".into(),
            timeout_s: fam.timeout_s,
        });
    }
    p.args = write.clone();
    p.steps.push(Step {
        name: "write".into(),
        program: fam.tool.clone(),
        program_path: path,
        args: write,
        summary: "Write and verify the new firmware.".into(),
        timeout_s: fam.timeout_s,
    });
}

fn plan_ssh(fam: &Family, req: &PlanRequest, store: &Store, p: &mut FlashPlan) {
    let target = match parse_ssh_target(&req.port) {
        Ok(t) => t,
        Err(e) => {
            p.blockers.push(e);
            return;
        }
    };
    let owned = find_owned(store, &[IdentityKind::Hostname], Some(&target.host));
    if owned.is_none() {
        p.blockers.push(format!("Host {} is not in the owned-device list. Add it on the Devices page (identity: Hostname) first.", target.host));
    }
    p.owned_device = owned.as_ref().map(|d| d.name.clone());
    p.owned_device_id = owned.as_ref().map(|d| d.id.clone());

    let Some(device_id) = req.device_id.as_deref().filter(|d| safe_token(d)) else {
        p.blockers.push("A Raspberry Pi flash needs device.id from device.yaml (letters, digits, '.', '_', '-').".into());
        return;
    };
    let scp_path = tools::find("scp");
    if scp_path.is_none() {
        p.blockers.push("scp is not installed or not on PATH.".into());
    }

    // Same names as the generated systemd unit (src/codegen/rpi.rs).
    let service = device_id.replace('-', "_");
    let dir = format!("/opt/oasis/{device_id}");
    let bin = format!("{dir}/{service}-supervisor");
    let unit = format!("{service}.service");
    let dest = format!("{}@{}", target.user, target.host);

    let ssh = |name: &str, remote: String, summary: &str| {
        let mut args = ssh_options();
        if let Some(port) = target.port {
            args.extend(["-p".into(), port.to_string()]);
        }
        args.extend(["--".into(), dest.clone(), remote]);
        Step {
            name: name.into(),
            program: "ssh".into(),
            program_path: p.tool_path.clone(),
            args,
            summary: summary.into(),
            timeout_s: fam.timeout_s,
        }
    };
    let mut scp_args = ssh_options();
    if let Some(port) = target.port {
        scp_args.extend(["-P".into(), port.to_string()]);
    }
    scp_args.extend(["--".into(), req.artifact.clone(), format!("{dest}:{bin}.new")]);

    p.backup_method = Some(format!("the Pi keeps the current program as {bin}.bak"));
    p.remote_backup = Some(format!("{bin}.bak"));
    p.steps = vec![
        ssh("backup", format!("if [ -f {bin} ]; then cp -p {bin} {bin}.bak; fi"), "Keep the program that runs now as a .bak file on the Pi."),
        Step {
            name: "write".into(),
            program: "scp".into(),
            program_path: scp_path.map(|s| s.to_string_lossy().into_owned()),
            args: scp_args.clone(),
            summary: "Copy the new program to the Pi.".into(),
            timeout_s: fam.timeout_s,
        },
        ssh("install", format!("mv {bin}.new {bin} && chmod 755 {bin}"), "Put the new program in place."),
        ssh("restart", format!("sudo -n systemctl restart {unit}"), "Restart the service. The SSH user needs sudo for this command with no password."),
        ssh("verify", format!("systemctl is-active --quiet {unit}"), "Check that the service runs."),
    ];
    p.args = scp_args;
}

// ------------------------------------------------------------------- run

/// What a person confirmed in the app.
#[derive(Debug, Clone, Deserialize)]
pub struct RunRequest {
    pub plan: PlanRequest,
    /// The firmware sha256 that the confirm dialog showed. The run stops if
    /// the file changed after the dialog.
    pub expected_sha256: String,
    /// The person accepted a flash with no backup (only for a family with no
    /// backup method).
    #[serde(default)]
    pub allow_no_backup: bool,
}

/// Check a fresh plan against what the person confirmed.
pub fn check_run(plan: &FlashPlan, req: &RunRequest) -> Result<(), String> {
    if !plan.blockers.is_empty() {
        return Err(plan.blockers.join(" "));
    }
    if plan.artifact_sha256.as_deref() != Some(req.expected_sha256.as_str()) {
        return Err("The firmware file changed after you confirmed. Build the plan again.".into());
    }
    if plan.backup_method.is_none() && !req.allow_no_backup {
        return Err(format!("The {} family has no backup method yet. Accept a flash with no backup to continue.", plan.family));
    }
    if plan.steps.iter().any(|s| s.program_path.is_none()) {
        return Err("A program for one of the steps is missing.".into());
    }
    Ok(())
}

#[derive(Debug, Clone, Serialize)]
pub struct FlashLine {
    pub run_id: String,
    pub step: String,
    /// stdout, stderr, or app (a message from Oasis Studio).
    pub stream: &'static str,
    pub text: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct StepResult {
    pub name: String,
    pub program: String,
    pub args: Vec<String>,
    /// None: the step did not start.
    pub exit: Option<Exit>,
    pub seconds: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct FlashDone {
    pub run_id: String,
    pub ok: bool,
    pub steps: Vec<StepResult>,
    pub backup_file: Option<String>,
    pub log_file: Option<String>,
    pub report_file: Option<String>,
    pub error: Option<String>,
}

impl FlashDone {
    pub fn describe(&self) -> String {
        if self.ok {
            return format!("ok; {} steps", self.steps.len());
        }
        if let Some(e) = &self.error {
            return format!("error: {e}");
        }
        match self.steps.iter().rev().find(|s| s.exit.is_some()) {
            Some(s) => format!("failed at {}: {}", s.name, s.exit.as_ref().map(Exit::describe).unwrap_or_default()),
            None => "failed before the first step".into(),
        }
    }
}

pub type EmitFn = Arc<dyn Fn(FlashLine) + Send + Sync>;

/// Run the steps of a checked plan. Blocks the caller. `backup_dir` gets the
/// backup file; `run_dir` gets `log.txt` and `report.json`.
pub fn execute(plan: &FlashPlan, run_id: &str, run_dir: &Path, backup_dir: &Path, stop: Arc<AtomicBool>, emit: EmitFn) -> FlashDone {
    let mut done = FlashDone {
        run_id: run_id.into(),
        ok: false,
        steps: vec![],
        backup_file: None,
        log_file: None,
        report_file: None,
        error: None,
    };
    if let Err(e) = std::fs::create_dir_all(run_dir) {
        done.error = Some(format!("Cannot make the run folder: {e}"));
        return done;
    }
    let log_path = run_dir.join("log.txt");
    let log = Arc::new(Mutex::new(std::fs::File::create(&log_path).ok()));
    done.log_file = Some(log_path.to_string_lossy().into_owned());

    let say = |step: &str, stream: &'static str, text: String| {
        if let Ok(mut f) = log.lock() {
            if let Some(f) = f.as_mut() {
                let _ = writeln!(f, "[{step}] [{stream}] {text}");
            }
        }
        emit(FlashLine { run_id: run_id.into(), step: step.into(), stream, text });
    };

    let backup_file = backup_dir.join(format!("{run_id}.{}", backup_ext(plan)));
    let backup_str = backup_file.to_string_lossy().into_owned();
    let local_backup = plan.transport != Transport::Ssh && plan.steps.iter().any(|s| s.name == "backup");
    if local_backup {
        if let Err(e) = std::fs::create_dir_all(backup_dir) {
            done.error = Some(format!("Cannot make the backup folder: {e}"));
            return finish(plan, done, run_dir);
        }
    }

    let mut failed = false;
    for step in &plan.steps {
        let args: Vec<String> = step.args.iter().map(|a| fill(a, &[("backup", backup_str.as_str())])).collect();
        let mut result = StepResult { name: step.name.clone(), program: step.program.clone(), args: args.clone(), exit: None, seconds: 0.0 };
        if failed {
            done.steps.push(result);
            continue;
        }
        let Some(program) = step.program_path.as_ref() else {
            failed = true;
            done.steps.push(result);
            continue;
        };
        say(&step.name, "app", format!("{}: {}", step.name, step.summary));
        let spec = runner::Spec {
            program: PathBuf::from(program),
            args,
            cwd: None,
            limit: Duration::from_secs(step.timeout_s),
            pty_stdout: false,
        };
        let name = step.name.clone();
        let sink = {
            let log = log.clone();
            let emit = emit.clone();
            let run_id = run_id.to_string();
            Arc::new(move |s: Stream, text: String| {
                let stream = if s == Stream::Stdout { "stdout" } else { "stderr" };
                if let Ok(mut f) = log.lock() {
                    if let Some(f) = f.as_mut() {
                        let _ = writeln!(f, "[{name}] [{stream}] {text}");
                    }
                }
                emit(FlashLine { run_id: run_id.clone(), step: name.clone(), stream, text });
            })
        };
        let t = Instant::now();
        let exit = runner::run(&spec, stop.clone(), sink);
        result.seconds = t.elapsed().as_secs_f64();
        match exit {
            Ok(exit) => {
                let good = exit == Exit::Exited { code: Some(0) };
                say(&step.name, "app", format!("{}: {}", step.name, exit.describe()));
                result.exit = Some(exit);
                if !good {
                    failed = true;
                }
            }
            Err(e) => {
                say(&step.name, "app", format!("{}: cannot start {}: {e}", step.name, step.program));
                failed = true;
            }
        }
        if !failed && step.name == "backup" && local_backup {
            match std::fs::metadata(&backup_file) {
                Ok(m) if m.len() > 0 => done.backup_file = Some(backup_str.clone()),
                _ => {
                    say("backup", "app", "The backup file is missing or empty. The app does not write the new firmware.".into());
                    failed = true;
                }
            }
        }
        done.steps.push(result);
    }
    done.ok = !failed;
    if plan.transport == Transport::Ssh && done.steps.first().is_some_and(|s| s.exit == Some(Exit::Exited { code: Some(0) })) {
        done.backup_file = plan.remote_backup.as_ref().map(|b| format!("on the Pi: {b}"));
    }
    finish(plan, done, run_dir)
}

fn backup_ext(plan: &FlashPlan) -> String {
    boards::family(&plan.family).and_then(|f| f.backup.as_ref()).map(|b| b.ext.clone()).unwrap_or_else(|| "bak".into())
}

fn finish(plan: &FlashPlan, mut done: FlashDone, run_dir: &Path) -> FlashDone {
    let report = serde_json::json!({
        "run_id": done.run_id,
        "board": { "family": plan.family, "port": plan.port, "fqbn": plan.fqbn, "owned_device": plan.owned_device, "owned_device_id": plan.owned_device_id },
        "artifact": { "path": plan.artifact, "sha256": plan.artifact_sha256, "size": plan.artifact_size },
        "steps": done.steps,
        "backup_file": done.backup_file,
        "ok": done.ok,
        "error": done.error,
        "app_version": env!("CARGO_PKG_VERSION"),
        // hw-validated needs a boot-banner check on the serial port (FW-015
        // section 5). The serial monitor is not built yet.
        "level": if done.ok { "flashed" } else { "not-flashed" },
    });
    let path = run_dir.join("report.json");
    if std::fs::write(&path, serde_json::to_vec_pretty(&report).unwrap_or_default()).is_ok() {
        done.report_file = Some(path.to_string_lossy().into_owned());
    }
    done
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::registry::NewDevice;

    #[test]
    fn substitution_keeps_each_argument_separate() {
        let t = vec!["-P".to_string(), "{port}".to_string(), "flash:w:{artifact}:i".to_string()];
        let out = substitute(&t, "/dev/cu.usb 1; rm -rf ~", 115200, "/tmp/a b.hex", None);
        assert_eq!(out, vec!["-P", "/dev/cu.usb 1; rm -rf ~", "flash:w:/tmp/a b.hex:i"]);
    }

    #[test]
    fn fill_reads_each_placeholder_once() {
        // A port name that looks like a placeholder is not replaced again.
        assert_eq!(fill("{port}:{backup}", &[("port", "{backup}"), ("backup", "/b.hex")]), "{backup}:/b.hex");
        assert_eq!(fill("{unknown} {", &[("port", "x")]), "{unknown} {");
    }

    #[test]
    fn ssh_target_parsing() {
        assert_eq!(parse_ssh_target("oasis@pi4.local").unwrap(), SshTarget { user: "oasis".into(), host: "pi4.local".into(), port: None });
        assert_eq!(parse_ssh_target("pi@10.0.0.7:2222").unwrap().port, Some(2222));
        for bad in ["pi4.local", "oasis@", "@pi", "Oasis@pi", "oasis@-oProxyCommand=x", "oasis@pi;reboot", "oasis@pi:0", "oasis@pi:x", "o a@pi"] {
            assert!(parse_ssh_target(bad).is_err(), "{bad} must fail");
        }
    }

    #[test]
    fn safe_tokens() {
        assert!(safe_token("greenhouse-01"));
        for bad in ["", "-rf", ".hidden", "a b", "a;b", "a/b", "$(x)", "a'b"] {
            assert!(!safe_token(bad), "{bad} must fail");
        }
    }

    fn owned(store: &Store, kind: IdentityKind, identity: &str, family: &str) {
        store
            .add(NewDevice { name: "bench".into(), identity_kind: kind, identity: identity.into(), family: Some(family.into()), notes: String::new(), owned: true })
            .unwrap();
    }

    #[test]
    fn unowned_board_is_blocked() {
        let tmp = tempfile::tempdir().unwrap();
        let store = Store::new(tmp.path().into());
        let p = plan(
            &PlanRequest {
                port: "/dev/cu.test".into(),
                family: "esp32".into(),
                artifact: "/nonexistent.bin".into(),
                usb_serial: Some("XYZ".into()),
                usb_vid: None,
                usb_pid: None,
                device_id: None,
                fqbn: None,
            },
            &store,
            "user",
        );
        assert!(p.blockers.iter().any(|b| b.contains("not in the owned-device list")));
        assert!(p.blockers.iter().any(|b| b.contains("Firmware file not found")));
        assert!(p.backup_method.is_none());
    }

    #[test]
    fn avr_plan_backs_up_then_writes() {
        let tmp = tempfile::tempdir().unwrap();
        let store = Store::new(tmp.path().into());
        owned(&store, IdentityKind::UsbSerial, "UNO1", "avr_uno");
        let fw = tmp.path().join("fw.hex");
        std::fs::write(&fw, b":00000001FF\n").unwrap();
        let p = plan(
            &PlanRequest { port: "/dev/cu.usbmodem1".into(), family: "avr_uno".into(), artifact: fw.to_string_lossy().into(), usb_serial: Some("UNO1".into()), usb_vid: None, usb_pid: None, device_id: None, fqbn: None },
            &store,
            "user",
        );
        let names: Vec<_> = p.steps.iter().map(|s| s.name.as_str()).collect();
        assert_eq!(names, ["backup", "write"]);
        assert!(p.steps[0].args.contains(&"flash:r:{backup}:i".to_string()));
        assert!(p.steps[1].args.iter().any(|a| a.starts_with("flash:w:") && a.ends_with(":i")));
        assert_eq!(p.owned_device.as_deref(), Some("bench"));
    }

    #[test]
    fn stm32_plan_selects_the_owned_probe() {
        let tmp = tempfile::tempdir().unwrap();
        let store = Store::new(tmp.path().into());
        owned(&store, IdentityKind::ProbeId, "066DFF", "stm32");
        let req = |vid| PlanRequest {
            port: "/dev/cu.usbmodem2".into(),
            family: "stm32".into(),
            artifact: "/fw.elf".into(),
            usb_serial: Some("066DFF".into()),
            usb_vid: vid,
            usb_pid: Some(0x374B),
            device_id: None,
            fqbn: None,
        };
        let p = plan(&req(Some(0x0483)), &store, "user");
        assert_eq!(p.owned_device.as_deref(), Some("bench"));
        assert_eq!(&p.args[..3], ["download", "--probe", "0483:374b:066DFF"]);
        assert!(p.args.contains(&"--verify".to_string()));
        let p = plan(&req(None), &store, "user");
        assert!(p.blockers.iter().any(|b| b.contains("vendor id")));
    }

    #[test]
    fn rpi_plan_builds_ssh_steps_from_safe_values() {
        let tmp = tempfile::tempdir().unwrap();
        let store = Store::new(tmp.path().into());
        owned(&store, IdentityKind::Hostname, "pi4.local", "rpi");
        let req = |dev: &str| PlanRequest {
            port: "oasis@pi4.local:2222".into(),
            family: "rpi".into(),
            artifact: "/build/greenhouse-01-supervisor".into(),
            usb_serial: None,
            usb_vid: None,
            usb_pid: None,
            device_id: Some(dev.into()),
            fqbn: None,
        };
        let p = plan(&req("greenhouse-01"), &store, "user");
        assert_eq!(p.owned_device.as_deref(), Some("bench"));
        let names: Vec<_> = p.steps.iter().map(|s| s.name.as_str()).collect();
        assert_eq!(names, ["backup", "write", "install", "restart", "verify"]);
        let write = &p.steps[1].args;
        assert_eq!(&write[write.len() - 3..], ["--", "/build/greenhouse-01-supervisor", "oasis@pi4.local:/opt/oasis/greenhouse-01/greenhouse_01-supervisor.new"]);
        assert!(write.windows(2).any(|w| w == ["-P", "2222"]));
        let restart = &p.steps[3].args;
        assert_eq!(restart.last().unwrap(), "sudo -n systemctl restart greenhouse_01.service");
        assert!(restart.windows(2).any(|w| w == ["-p", "2222"]));
        assert!(restart.contains(&"BatchMode=yes".to_string()));

        let bad = plan(&req("x; reboot"), &store, "user");
        assert!(bad.blockers.iter().any(|b| b.contains("device.id")));
        assert!(bad.steps.is_empty());
    }

    #[test]
    fn fqbn_check() {
        for ok in ["arduino:avr:uno", "arduino:avr:mega:cpu=atmega2560", "esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M", "arduino:renesas_uno:minima"] {
            assert!(valid_fqbn(ok), "{ok}");
        }
        for bad in ["", "arduino:avr", "-x:avr:uno", "arduino:avr:uno:", "arduino:avr:uno:cpu", "arduino:avr:uno a", "a:b:c:d=e:f", "arduino:avr:$(id)"] {
            assert!(!valid_fqbn(bad), "{bad}");
        }
    }

    #[test]
    fn arduino_plan_needs_a_valid_fqbn_and_has_no_backup() {
        let tmp = tempfile::tempdir().unwrap();
        let store = Store::new(tmp.path().into());
        owned(&store, IdentityKind::UsbSerial, "MEGA1", "arduino");
        let fw = tmp.path().join("fw.hex");
        std::fs::write(&fw, b":00000001FF\n").unwrap();
        let req = |fqbn: Option<&str>| PlanRequest {
            port: "/dev/cu.usbmodem1".into(),
            family: "arduino".into(),
            artifact: fw.to_string_lossy().into(),
            usb_serial: Some("MEGA1".into()),
            usb_vid: Some(0x2341),
            usb_pid: Some(0x0042),
            device_id: None,
            fqbn: fqbn.map(Into::into),
        };
        let missing = plan(&req(None), &store, "user");
        assert!(missing.blockers.iter().any(|b| b.contains("needs the board name")), "{:?}", missing.blockers);
        let bad = plan(&req(Some("arduino:avr")), &store, "user");
        assert!(bad.blockers.iter().any(|b| b.contains("not a valid board name")), "{:?}", bad.blockers);

        let p = plan(&req(Some(" arduino:avr:mega ")), &store, "user");
        assert!(p.blockers.iter().all(|b| b.contains("arduino-cli is not installed")), "{:?}", p.blockers);
        assert!(p.backup_method.is_none());
        assert_eq!(p.fqbn.as_deref(), Some("arduino:avr:mega"));
        assert_eq!(p.steps.len(), 1);
        assert_eq!(
            p.steps[0].args,
            ["upload", "-v", "--verify", "--port", "/dev/cu.usbmodem1", "--fqbn", "arduino:avr:mega", "--input-file", &fw.to_string_lossy()]
        );
    }

    #[test]
    fn a_family_without_fqbn_ignores_the_field() {
        let tmp = tempfile::tempdir().unwrap();
        let store = Store::new(tmp.path().into());
        let mut r = PlanRequest { port: "/dev/x".into(), family: "esp32".into(), artifact: "/fw.bin".into(), usb_serial: None, usb_vid: None, usb_pid: None, device_id: None, fqbn: None };
        r.fqbn = Some("not valid".into());
        let p = plan(&r, &store, "user");
        assert!(p.fqbn.is_none());
        assert!(!p.blockers.iter().any(|b| b.contains("FQBN")));
    }

    #[test]
    fn check_run_refuses_a_changed_file_and_a_missing_backup() {
        let mut p = FlashPlan {
            port: "p".into(),
            family: "esp32".into(),
            transport: Transport::Usb,
            tool: "espflash".into(),
            tool_path: Some("/bin/true".into()),
            args: vec![],
            steps: vec![],
            artifact: "/fw".into(),
            artifact_sha256: Some("aa".into()),
            artifact_size: Some(1),
            owned_device: Some("bench".into()),
            owned_device_id: Some("d1".into()),
            backup_method: None,
            remote_backup: None,
            fqbn: None,
            blockers: vec![],
        };
        let req = |sha: &str, allow| RunRequest {
            plan: PlanRequest { port: "p".into(), family: "esp32".into(), artifact: "/fw".into(), usb_serial: None, usb_vid: None, usb_pid: None, device_id: None, fqbn: None },
            expected_sha256: sha.into(),
            allow_no_backup: allow,
        };
        assert!(check_run(&p, &req("bb", true)).unwrap_err().contains("changed"));
        assert!(check_run(&p, &req("aa", false)).unwrap_err().contains("no backup method"));
        assert!(check_run(&p, &req("aa", true)).is_ok());
        p.blockers.push("blocked".into());
        assert!(check_run(&p, &req("aa", true)).is_err());
    }

    #[cfg(unix)]
    mod run {
        use super::*;
        use std::os::unix::fs::PermissionsExt;

        /// A fake flash tool: prints its arguments, writes the backup file for
        /// a read (`flash:r:<file>:i`), and exits with the code in FAIL_ON for
        /// a write.
        fn fake_tool(dir: &Path, fail_write: bool) -> String {
            let p = dir.join("fake-avrdude");
            let body = format!(
                "#!/bin/sh\necho \"args: $*\"\nfor a in \"$@\"; do case \"$a\" in flash:r:*) f=${{a#flash:r:}}; f=${{f%:i}}; echo ':00000001FF' > \"$f\";; flash:w:*) echo 'writing' >&2; {};; esac; done\nexit 0\n",
                if fail_write { "exit 3" } else { "true" }
            );
            std::fs::write(&p, body).unwrap();
            std::fs::set_permissions(&p, std::fs::Permissions::from_mode(0o755)).unwrap();
            p.to_string_lossy().into_owned()
        }

        fn avr_plan(tool: &str) -> FlashPlan {
            let step = |name: &str, args: &[&str]| Step {
                name: name.into(),
                program: "avrdude".into(),
                program_path: Some(tool.into()),
                args: args.iter().map(|s| s.to_string()).collect(),
                summary: name.into(),
                timeout_s: 10,
            };
            FlashPlan {
                port: "/dev/null".into(),
                family: "avr_uno".into(),
                transport: Transport::Usb,
                tool: "avrdude".into(),
                tool_path: Some(tool.into()),
                args: vec![],
                steps: vec![step("backup", &["-U", "flash:r:{backup}:i"]), step("write", &["-U", "flash:w:/fw.hex:i"])],
                artifact: "/fw.hex".into(),
                artifact_sha256: Some("aa".into()),
                artifact_size: Some(12),
                owned_device: Some("bench".into()),
                owned_device_id: Some("d1".into()),
                backup_method: Some("avrdude".into()),
                remote_backup: None,
                fqbn: None,
                blockers: vec![],
            }
        }

        fn collect() -> (EmitFn, Arc<Mutex<Vec<FlashLine>>>) {
            let lines = Arc::new(Mutex::new(Vec::new()));
            let sink = lines.clone();
            (Arc::new(move |l| sink.lock().unwrap().push(l)), lines)
        }

        #[test]
        fn backup_then_write_and_report() {
            let tmp = tempfile::tempdir().unwrap();
            let tool = fake_tool(tmp.path(), false);
            let (emit, lines) = collect();
            let done = execute(&avr_plan(&tool), "r1", &tmp.path().join("run"), &tmp.path().join("backups"), Arc::new(AtomicBool::new(false)), emit);
            assert!(done.ok, "{done:?}");
            let backup = done.backup_file.as_deref().unwrap();
            assert!(backup.ends_with("r1.hex"));
            assert_eq!(std::fs::read_to_string(backup).unwrap().trim(), ":00000001FF");
            assert_eq!(done.steps.len(), 2);
            assert!(done.steps[0].args[1].starts_with("flash:r:/") && !done.steps[0].args[1].contains("{backup}"));
            let report: serde_json::Value = serde_json::from_slice(&std::fs::read(done.report_file.unwrap()).unwrap()).unwrap();
            assert_eq!(report["ok"], true);
            assert_eq!(report["level"], "flashed");
            let lines = lines.lock().unwrap();
            assert!(lines.iter().any(|l| l.step == "write" && l.stream == "stderr" && l.text == "writing"));
            assert!(std::fs::read_to_string(done.log_file.unwrap()).unwrap().contains("[write] [stderr] writing"));
        }

        #[test]
        fn a_failed_write_stops_the_run() {
            let tmp = tempfile::tempdir().unwrap();
            let tool = fake_tool(tmp.path(), true);
            let (emit, _) = collect();
            let mut plan = avr_plan(&tool);
            plan.steps.push(Step { name: "verify".into(), ..plan.steps[1].clone() });
            let done = execute(&plan, "r2", &tmp.path().join("run"), &tmp.path().join("backups"), Arc::new(AtomicBool::new(false)), emit);
            assert!(!done.ok);
            assert_eq!(done.steps[1].exit, Some(Exit::Exited { code: Some(3) }));
            assert!(done.steps[2].exit.is_none(), "verify must not start after a failed write");
            assert!(done.describe().contains("failed at write"));
        }

        #[test]
        fn a_missing_backup_file_stops_before_the_write() {
            let tmp = tempfile::tempdir().unwrap();
            let (emit, _) = collect();
            // /bin/sh -c true exits 0 and writes no backup file.
            let mut plan = avr_plan("/bin/sh");
            plan.steps[0].args = vec!["-c".into(), "true".into()];
            let done = execute(&plan, "r3", &tmp.path().join("run"), &tmp.path().join("backups"), Arc::new(AtomicBool::new(false)), emit);
            assert!(!done.ok);
            assert!(done.backup_file.is_none());
            assert!(done.steps[1].exit.is_none());
        }
    }
}
