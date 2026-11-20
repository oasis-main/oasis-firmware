//! Oasis Studio tool registry.
//!
//! This crate holds every function behind the Oasis Studio desktop app
//! (`desktop/src-tauri`) and the MCP server (`oasis-studio-mcp`). The two
//! front ends call the same functions:
//!
//! - The Tauri commands in `desktop/src-tauri/src/lib.rs` call [`Studio`].
//! - The MCP server calls [`catalog::call`], which calls [`Studio`].
//!
//! Rules that hold for every caller:
//!
//! 1. A write to a device (flash or command) needs a row in the owned-device
//!    list. Only a person adds a row, on the Owned devices page of the app.
//! 2. External programs run with an argument list. No shell reads the
//!    arguments (`tools.rs`, `runner.rs`).
//! 3. Each change writes one line to the action log (`audit.jsonl`), with
//!    the actor that asked for the change.

pub mod boards;
pub mod catalog;
pub mod device;
pub mod flash;
pub mod mcp;
pub mod ports;
pub mod registry;
pub mod runner;
pub mod sim;
pub mod tools;

use registry::{AuditEntry, NewDevice, OwnedDevice, Store};
use serde::Serialize;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

/// The Tauri bundle identifier (`desktop/src-tauri/tauri.conf.json`). The
/// app data folder has this name. A test in `src-tauri` checks the value.
pub const APP_IDENTIFIER: &str = "io.oasis-x.studio";

/// Who asked for an action. The value goes into each action-log line.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Actor {
    /// A person, through a button in the app.
    User,
    /// The in-app assistant chat.
    Assistant,
    /// An MCP client, through `oasis-studio-mcp`.
    Mcp,
}

impl Actor {
    pub fn as_str(self) -> &'static str {
        match self {
            Actor::User => "user",
            Actor::Assistant => "assistant",
            Actor::Mcp => "mcp",
        }
    }
}

/// The two folders that the tools use.
#[derive(Debug, Clone)]
pub struct Paths {
    /// Owned-device list, action log, simulation run folders.
    pub data_dir: PathBuf,
    /// Generated firmware: `<projects_dir>/<device id>/firmware`.
    pub projects_dir: PathBuf,
}

impl Paths {
    /// The same folders that the desktop app uses:
    /// - data: `<OS data folder>/io.oasis-x.studio`
    /// - projects: `<Documents>/Oasis Studio`
    ///
    /// The environment variables `OASIS_STUDIO_DATA_DIR` and
    /// `OASIS_STUDIO_PROJECTS_DIR` replace the defaults.
    pub fn from_env() -> Result<Paths, String> {
        let data_dir = match std::env::var_os("OASIS_STUDIO_DATA_DIR") {
            Some(d) if !d.is_empty() => PathBuf::from(d),
            _ => dirs::data_dir().ok_or("cannot find the data folder for this OS")?.join(APP_IDENTIFIER),
        };
        let projects_dir = match std::env::var_os("OASIS_STUDIO_PROJECTS_DIR") {
            Some(d) if !d.is_empty() => PathBuf::from(d),
            _ => dirs::document_dir().map(|d| d.join("Oasis Studio")).unwrap_or_else(|| data_dir.join("projects")),
        };
        Ok(Paths { data_dir, projects_dir })
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct AppInfo {
    pub version: &'static str,
    pub os: &'static str,
    pub arch: &'static str,
    pub data_dir: String,
    pub projects_dir: String,
}

/// A simulation run that has a slot. Give it to [`Studio::sim_execute`].
pub struct SimTicket {
    pub run_id: String,
    pub plan: sim::SimPlan,
    pub run_dir: PathBuf,
    pub stop: Arc<AtomicBool>,
}

pub struct Studio {
    store: Store,
    projects_dir: PathBuf,
    /// The active simulation run: run id and its stop flag. One run at a time.
    sim_run: Mutex<Option<(String, Arc<AtomicBool>)>>,
}

impl Studio {
    pub fn new(paths: Paths) -> Self {
        Self { store: Store::new(paths.data_dir), projects_dir: paths.projects_dir, sim_run: Mutex::new(None) }
    }

    pub fn store(&self) -> &Store {
        &self.store
    }

    pub fn projects_dir(&self) -> &Path {
        &self.projects_dir
    }

    // ------------------------------------------------------------- observe

    pub fn app_info(&self) -> AppInfo {
        AppInfo {
            version: env!("CARGO_PKG_VERSION"),
            os: std::env::consts::OS,
            arch: std::env::consts::ARCH,
            data_dir: self.store.dir().to_string_lossy().into_owned(),
            projects_dir: self.projects_dir.to_string_lossy().into_owned(),
        }
    }

    pub fn list_ports(&self) -> Result<Vec<ports::DetectedPort>, String> {
        ports::list()
    }

    pub fn list_tools(&self) -> Vec<tools::ToolStatus> {
        tools::list()
    }

    pub fn list_families(&self) -> Vec<boards::Family> {
        boards::table().families.clone()
    }

    pub fn validate_config(&self, yaml: &str) -> device::ValidateResult {
        device::validate(yaml)
    }

    pub fn registry_list(&self) -> Result<Vec<OwnedDevice>, String> {
        self.store.list()
    }

    pub fn audit_tail(&self, limit: usize) -> Vec<AuditEntry> {
        self.store.audit_tail(limit)
    }

    pub fn sim_plan(&self, req: &sim::SimRequest) -> sim::SimPlan {
        sim::plan(req)
    }

    // ------------------------------------------------------------- propose

    /// Write generated firmware into the projects folder. Writes one
    /// action-log line.
    pub fn generate_firmware(&self, yaml: &str, actor: Actor) -> Result<device::GenerateResult, String> {
        let result = device::generate(yaml, &self.projects_dir);
        let target = result.as_ref().map(|r| r.output_dir.clone()).unwrap_or_default();
        self.store.audit(actor.as_str(), "firmware.generate", &target, if result.is_ok() { "ok" } else { "error" });
        result
    }

    /// Build a flash plan. The plan never runs the flash tool. Writes one
    /// action-log line.
    pub fn flash_plan(&self, req: &flash::PlanRequest, actor: Actor) -> flash::FlashPlan {
        flash::plan(req, &self.store, actor.as_str())
    }

    /// Plan a run and take the run slot. Fails if the plan has a blocker or
    /// another run is active. Setting `stop` (or calling [`Studio::sim_stop`])
    /// stops the run.
    pub fn sim_begin(&self, req: &sim::SimRequest, stop: Arc<AtomicBool>) -> Result<SimTicket, String> {
        let plan = sim::plan(req);
        if !plan.blockers.is_empty() {
            return Err(plan.blockers.join(" "));
        }
        let run_id = chrono::Local::now().format("%Y%m%d-%H%M%S-%3f").to_string();
        {
            let mut active = self.sim_run.lock().map_err(|e| e.to_string())?;
            if let Some((id, _)) = active.as_ref() {
                return Err(format!("Simulation {id} is still running. Stop it first."));
            }
            *active = Some((run_id.clone(), stop.clone()));
        }
        let run_dir = self.store.dir().join("sim-runs").join(&run_id);
        Ok(SimTicket { run_id, plan, run_dir, stop })
    }

    /// Run a ticket to the end (exit, time limit, or stop). Writes one
    /// action-log line and frees the run slot. Blocks the caller.
    pub fn sim_execute(&self, ticket: SimTicket, actor: Actor, emit: Arc<dyn Fn(sim::SimLine) + Send + Sync>) -> sim::SimDone {
        struct Release<'a>(&'a Mutex<Option<(String, Arc<AtomicBool>)>>);
        impl Drop for Release<'_> {
            fn drop(&mut self) {
                if let Ok(mut active) = self.0.lock() {
                    *active = None;
                }
            }
        }
        let _release = Release(&self.sim_run);
        let SimTicket { run_id, plan, run_dir, stop } = ticket;
        let done = sim::execute(&plan, &run_id, &run_dir, stop, emit);
        let sha = plan.artifact_sha256.as_deref().unwrap_or("-");
        let target = format!("{} {} sha256:{}", plan.family, plan.engine.as_deref().unwrap_or("-"), &sha[..sha.len().min(16)]);
        let result = match &done.error {
            Some(e) => format!("error: {e}"),
            None => format!("{}; {} UART lines", done.exit.describe(), done.uart_lines),
        };
        self.store.audit(actor.as_str(), "sim.run", &target, &result);
        done
    }

    /// Set the stop flag of the active run. False if no run is active.
    pub fn sim_stop(&self) -> bool {
        match self.sim_run.lock().ok().and_then(|a| a.as_ref().map(|(_, s)| s.clone())) {
            Some(stop) => {
                stop.store(true, Ordering::SeqCst);
                true
            }
            None => false,
        }
    }

    // ------------------------------------------------- app only (a person)

    /// Add an owned device. Only the Owned devices page of the app calls
    /// this function. The tool catalog has no tool for it.
    pub fn registry_add(&self, device: NewDevice) -> Result<OwnedDevice, String> {
        self.store.add(device)
    }

    pub fn registry_remove(&self, id: &str) -> Result<(), String> {
        self.store.remove(id)
    }
}
