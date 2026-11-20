//! device.yaml validation and firmware generation through `oasis-core`.

use oasis_core::codegen::{self, TargetInfo};
use oasis_core::config::{validate_config, DeviceConfig};
use serde::Serialize;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize)]
pub struct ConfigSummary {
    pub id: String,
    pub name: String,
    pub platform: String,
    pub model: String,
    pub rust_target: String,
    pub sensors: usize,
    pub actuators: usize,
    pub control_loops: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct ValidateResult {
    pub ok: bool,
    pub summary: Option<ConfigSummary>,
    pub errors: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct GenerateResult {
    pub output_dir: String,
    pub files: Vec<String>,
}

fn summary(cfg: &DeviceConfig) -> ConfigSummary {
    let target = TargetInfo::from_config(cfg);
    ConfigSummary {
        id: cfg.device.id.clone(),
        name: cfg.device.name.clone(),
        platform: format!("{:?}", cfg.device.board.platform).to_lowercase(),
        model: cfg.device.board.model.clone(),
        rust_target: target.rust_target,
        sensors: cfg.sensors.len(),
        actuators: cfg.actuators.len(),
        control_loops: cfg.control_loops.len(),
    }
}

pub fn parse(yaml: &str) -> Result<DeviceConfig, String> {
    serde_yaml::from_str::<DeviceConfig>(yaml).map_err(|e| format!("YAML: {e}"))
}

pub fn validate(yaml: &str) -> ValidateResult {
    match parse(yaml) {
        Err(e) => ValidateResult { ok: false, summary: None, errors: vec![e] },
        Ok(cfg) => match validate_config(&cfg) {
            Ok(()) => ValidateResult { ok: true, summary: Some(summary(&cfg)), errors: vec![] },
            Err(e) => ValidateResult { ok: false, summary: Some(summary(&cfg)), errors: vec![e.to_string()] },
        },
    }
}

/// Device ids become folder names. Keep only safe characters.
pub fn safe_id(id: &str) -> String {
    let s: String = id
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c } else { '_' })
        .collect();
    if s.is_empty() { "device".into() } else { s }
}

pub fn generate(yaml: &str, projects_dir: &Path) -> Result<GenerateResult, String> {
    let cfg = parse(yaml)?;
    validate_config(&cfg).map_err(|e| e.to_string())?;
    let out: PathBuf = projects_dir.join(safe_id(&cfg.device.id)).join("firmware");
    std::fs::create_dir_all(&out).map_err(|e| format!("cannot create {}: {e}", out.display()))?;
    codegen::generate(&cfg, &out).map_err(|e| e.to_string())?;
    let mut files = Vec::new();
    collect(&out, &out, &mut files);
    files.sort();
    Ok(GenerateResult { output_dir: out.to_string_lossy().into_owned(), files })
}

fn collect(root: &Path, dir: &Path, out: &mut Vec<String>) {
    if let Ok(entries) = std::fs::read_dir(dir) {
        for e in entries.flatten() {
            let p = e.path();
            if p.is_dir() {
                collect(root, &p, out);
            } else if let Ok(rel) = p.strip_prefix(root) {
                out.push(rel.to_string_lossy().into_owned());
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const EXAMPLE: &str = include_str!("../../../examples/greenhouse-demo.yaml");

    #[test]
    fn example_validates() {
        let r = validate(EXAMPLE);
        assert!(r.ok, "{:?}", r.errors);
        let s = r.summary.unwrap();
        assert_eq!(s.model, "esp32_devkit");
        assert_eq!(s.platform, "mcu");
    }

    #[test]
    fn ui_starter_validates() {
        let r = validate(include_str!("../../src/starter-device.yaml"));
        assert!(r.ok, "{:?}", r.errors);
    }

    #[test]
    fn bad_yaml_reports_an_error() {
        let r = validate("device: [");
        assert!(!r.ok);
        assert!(r.errors[0].starts_with("YAML"));
    }

    #[test]
    fn generate_writes_files_inside_the_projects_dir() {
        let tmp = tempfile::tempdir().unwrap();
        let r = generate(EXAMPLE, tmp.path()).unwrap();
        assert!(r.output_dir.starts_with(tmp.path().to_str().unwrap()));
        assert!(!r.files.is_empty());
    }

    #[test]
    fn safe_id_blocks_path_traversal() {
        assert_eq!(safe_id("../../etc"), "______etc");
        assert_eq!(safe_id(""), "device");
    }
}
