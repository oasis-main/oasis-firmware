//! Oasis Studio desktop back end (Tauri 2).
//!
//! Every device action goes through this crate. The webview calls the
//! commands below; it has no other path to a port, a tool, or the disk.

mod boards;
mod device;
mod flash;
mod ports;
mod registry;
mod tools;

use registry::{AuditEntry, NewDevice, OwnedDevice, Store};
use serde::Serialize;
use std::path::PathBuf;
use tauri::{Manager, State};

pub struct AppState {
    store: Store,
    projects_dir: PathBuf,
}

#[derive(Serialize)]
struct AppInfo {
    version: &'static str,
    os: &'static str,
    arch: &'static str,
    data_dir: String,
    projects_dir: String,
}

#[tauri::command]
fn app_info(state: State<'_, AppState>) -> AppInfo {
    AppInfo {
        version: env!("CARGO_PKG_VERSION"),
        os: std::env::consts::OS,
        arch: std::env::consts::ARCH,
        data_dir: state.store.dir().to_string_lossy().into_owned(),
        projects_dir: state.projects_dir.to_string_lossy().into_owned(),
    }
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
fn list_families() -> Vec<boards::Family> {
    boards::table().families.clone()
}

#[tauri::command]
fn validate_config(yaml: String) -> device::ValidateResult {
    device::validate(&yaml)
}

#[tauri::command]
async fn generate_firmware(yaml: String, state: State<'_, AppState>) -> Result<device::GenerateResult, String> {
    let dir = state.projects_dir.clone();
    let result = tauri::async_runtime::spawn_blocking(move || device::generate(&yaml, &dir))
        .await
        .map_err(|e| e.to_string())?;
    let target = result.as_ref().map(|r| r.output_dir.clone()).unwrap_or_default();
    state.store.audit("user", "firmware.generate", &target, if result.is_ok() { "ok" } else { "error" });
    result
}

#[tauri::command]
fn registry_list(state: State<'_, AppState>) -> Result<Vec<OwnedDevice>, String> {
    state.store.list()
}

#[tauri::command]
fn registry_add(device: NewDevice, state: State<'_, AppState>) -> Result<OwnedDevice, String> {
    state.store.add(device)
}

#[tauri::command]
fn registry_remove(id: String, state: State<'_, AppState>) -> Result<(), String> {
    state.store.remove(&id)
}

#[tauri::command]
fn audit_tail(limit: Option<usize>, state: State<'_, AppState>) -> Vec<AuditEntry> {
    state.store.audit_tail(limit.unwrap_or(200))
}

#[tauri::command]
fn flash_plan(request: flash::PlanRequest, state: State<'_, AppState>) -> flash::FlashPlan {
    flash::plan(&request, &state.store)
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
            app.manage(AppState { store: Store::new(data_dir), projects_dir });
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
        ])
        .run(tauri::generate_context!())
        .expect("error while running Oasis Studio");
}
