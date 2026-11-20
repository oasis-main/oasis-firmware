//! Flash plan (FW-015 sections 3 and 4).
//!
//! v0.1 builds and shows the plan only: tool, exact argument list, artifact
//! hash, and every reason the flash cannot run. The supervised flash run
//! (confirm dialog, streamed output, verify) is the next FW-015 step.
//!
//! A plan never runs the flash tool. The MCP server exposes this plan; it
//! has no tool that runs a flash.

use crate::boards;
use crate::registry::{IdentityKind, Store};
use crate::tools;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::path::Path;

#[derive(Debug, Clone, Deserialize)]
pub struct PlanRequest {
    pub port: String,
    pub family: String,
    pub artifact: String,
    /// USB serial number of the board, from the port list.
    pub usb_serial: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct FlashPlan {
    pub port: String,
    pub family: String,
    pub tool: String,
    pub tool_path: Option<String>,
    /// One entry for each argument. The app passes the list to the program
    /// as is; there is no shell.
    pub args: Vec<String>,
    pub artifact: String,
    pub artifact_sha256: Option<String>,
    pub owned_device: Option<String>,
    /// Empty means the plan can run (after the user confirms).
    pub blockers: Vec<String>,
}

pub fn substitute(template: &[String], port: &str, baud: u32, artifact: &str, chip: Option<&str>) -> Vec<String> {
    template
        .iter()
        .map(|a| {
            a.replace("{port}", port)
                .replace("{baud}", &baud.to_string())
                .replace("{artifact}", artifact)
                .replace("{chip}", chip.unwrap_or(""))
        })
        .collect()
}

pub(crate) fn sha256_file(p: &Path) -> Option<String> {
    let bytes = std::fs::read(p).ok()?;
    let digest = Sha256::digest(&bytes);
    Some(digest.iter().map(|b| format!("{b:02x}")).collect())
}

pub fn plan(req: &PlanRequest, store: &Store, actor: &str) -> FlashPlan {
    let mut blockers = Vec::new();
    let Some(fam) = boards::family(&req.family) else {
        return FlashPlan {
            port: req.port.clone(),
            family: req.family.clone(),
            tool: String::new(),
            tool_path: None,
            args: vec![],
            artifact: req.artifact.clone(),
            artifact_sha256: None,
            owned_device: None,
            blockers: vec![format!("Unknown board family \"{}\". Pick a family from the list.", req.family)],
        };
    };

    let tool_path = tools::find(&fam.tool);
    if tool_path.is_none() {
        blockers.push(format!("{} is not installed or not on PATH.", fam.tool));
    }

    let artifact = Path::new(&req.artifact);
    let artifact_sha256 = if artifact.is_file() { sha256_file(artifact) } else { None };
    if artifact_sha256.is_none() {
        blockers.push(format!("Firmware file not found: {}", req.artifact));
    }

    let owned = req
        .usb_serial
        .as_deref()
        .filter(|s| !s.is_empty())
        .and_then(|s| store.find_by_identity(IdentityKind::UsbSerial, s));
    if owned.is_none() {
        blockers.push(match &req.usb_serial {
            Some(s) if !s.is_empty() => format!("USB serial {s} is not in the owned-device list. Add the board on the Devices page first."),
            _ => "The board reports no USB serial number, so the app cannot match it to the owned-device list.".into(),
        });
    }

    let args = substitute(&fam.args, &req.port, fam.baud, &req.artifact, fam.chip.as_deref());
    store.audit(
        actor,
        "flash.plan",
        &req.port,
        if blockers.is_empty() { "ready" } else { "blocked" },
    );

    FlashPlan {
        port: req.port.clone(),
        family: fam.family.clone(),
        tool: fam.tool.clone(),
        tool_path: tool_path.map(|p| p.to_string_lossy().into_owned()),
        args,
        artifact: req.artifact.clone(),
        artifact_sha256,
        owned_device: owned.map(|d| d.name),
        blockers,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn substitution_keeps_each_argument_separate() {
        let t = vec!["-P".to_string(), "{port}".to_string(), "flash:w:{artifact}:i".to_string()];
        let out = substitute(&t, "/dev/cu.usb 1; rm -rf ~", 115200, "/tmp/a b.hex", None);
        assert_eq!(out, vec!["-P", "/dev/cu.usb 1; rm -rf ~", "flash:w:/tmp/a b.hex:i"]);
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
            },
            &store,
            "user",
        );
        assert!(p.blockers.iter().any(|b| b.contains("not in the owned-device list")));
        assert!(p.blockers.iter().any(|b| b.contains("Firmware file not found")));
    }
}
