//! Oasis Studio desktop back end (Tauri 2).
//!
//! Every device action goes through this crate. The webview calls the
//! commands below; it has no other path to a port, a tool, or the disk.
//!
//! The commands are thin wrappers. The logic is in `oasis-studio-core`
//! (`desktop/studio-core`), which the MCP server `oasis-studio-mcp` also
//! uses. The app and MCP clients therefore run the same functions.

use oasis_studio_core::registry::{AuditEntry, NewDevice, OwnedDevice};
use oasis_studio_core::{boards, device, flash, ports, sim, tools, Actor, AppInfo, Paths, Studio};
use std::sync::atomic::AtomicBool;
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager, State};

#[tauri::command]
fn app_info(studio: State<'_, Studio>) -> AppInfo {
    studio.app_info()
}

#[tauri::command]
async fn list_ports() -> Result<Vec<ports::DetectedPort>, String> {
    tauri::async_runtime::spawn_blocking(ports::list).await.map_err(|e| e.to_string())?
}

#[tauri::command]
async fn list_tools() -> Result<Vec<tools::ToolStatus>, String> {
    tauri::async_runtime::spawn_blocking(tools::list).await.map_err(|e| e.to_string())
}

#[tauri::command]
fn list_families(studio: State<'_, Studio>) -> Vec<boards::Family> {
    studio.list_families()
}

#[tauri::command]
fn validate_config(yaml: String, studio: State<'_, Studio>) -> device::ValidateResult {
    studio.validate_config(&yaml)
}

#[tauri::command]
async fn generate_firmware(yaml: String, app: AppHandle) -> Result<device::GenerateResult, String> {
    tauri::async_runtime::spawn_blocking(move || app.state::<Studio>().generate_firmware(&yaml, Actor::User))
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
fn registry_list(studio: State<'_, Studio>) -> Result<Vec<OwnedDevice>, String> {
    studio.registry_list()
}

/// Add an owned device. A person calls this from the Owned devices page.
/// The tool catalog (and so the MCP server) has no tool for it.
#[tauri::command]
fn registry_add(device: NewDevice, studio: State<'_, Studio>) -> Result<OwnedDevice, String> {
    studio.registry_add(device)
}

#[tauri::command]
fn registry_remove(id: String, studio: State<'_, Studio>) -> Result<(), String> {
    studio.registry_remove(&id)
}

#[tauri::command]
fn audit_tail(limit: Option<usize>, studio: State<'_, Studio>) -> Vec<AuditEntry> {
    studio.audit_tail(limit.unwrap_or(200))
}

#[tauri::command]
fn flash_plan(request: flash::PlanRequest, studio: State<'_, Studio>) -> flash::FlashPlan {
    studio.flash_plan(&request, Actor::User)
}

#[tauri::command]
async fn sim_plan(request: sim::SimRequest) -> Result<sim::SimPlan, String> {
    tauri::async_runtime::spawn_blocking(move || sim::plan(&request)).await.map_err(|e| e.to_string())
}

/// Start a simulation run. Output arrives as "sim://line" events; the end
/// arrives as one "sim://done" event. Returns the run id.
#[tauri::command]
async fn sim_start(request: sim::SimRequest, app: AppHandle) -> Result<String, String> {
    let handle = app.clone();
    let ticket = tauri::async_runtime::spawn_blocking(move || handle.state::<Studio>().sim_begin(&request, Arc::new(AtomicBool::new(false))))
        .await
        .map_err(|e| e.to_string())??;
    let run_id = ticket.run_id.clone();
    std::thread::spawn(move || {
        let emitter = app.clone();
        let emit = Arc::new(move |line: sim::SimLine| {
            let _ = emitter.emit("sim://line", line);
        });
        let done = app.state::<Studio>().sim_execute(ticket, Actor::User, emit);
        let _ = app.emit("sim://done", done);
    });
    Ok(run_id)
}

#[tauri::command]
fn sim_stop(studio: State<'_, Studio>) -> bool {
    studio.sim_stop()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            let projects_dir = app
                .path()
                .document_dir()
                .map(|d| d.join("Oasis Studio"))
                .unwrap_or_else(|_| data_dir.join("projects"));
            app.manage(Studio::new(Paths { data_dir, projects_dir }));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            app_info,
            list_ports,
            list_tools,
            list_families,
            validate_config,
            generate_firmware,
            registry_list,
            registry_add,
            registry_remove,
            audit_tail,
            flash_plan,
            sim_plan,
            sim_start,
            sim_stop,
        ])
        .run(tauri::generate_context!())
        .expect("error while running Oasis Studio");
}

#[cfg(test)]
mod tests {
    /// The MCP server finds the app data folder by this identifier.
    #[test]
    fn bundle_identifier_matches_the_shared_crate() {
        let conf: serde_json::Value = serde_json::from_str(include_str!("../tauri.conf.json")).unwrap();
        assert_eq!(conf["identifier"], oasis_studio_core::APP_IDENTIFIER);
    }
}
