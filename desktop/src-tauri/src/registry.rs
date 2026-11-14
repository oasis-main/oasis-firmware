//! Owned-device registry and action log.
//!
//! Rule: the app writes to a device (command or flash) only when the device
//! has a row here. The user adds the row and declares ownership. The app
//! never adds a row by itself.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::fs::OpenOptions;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum IdentityKind {
    UsbSerial,
    Mac,
    ProbeId,
    Hostname,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OwnedDevice {
    pub id: String,
    pub name: String,
    pub identity_kind: IdentityKind,
    pub identity: String,
    #[serde(default)]
    pub family: Option<String>,
    #[serde(default)]
    pub notes: String,
    pub declared_owned_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct NewDevice {
    pub name: String,
    pub identity_kind: IdentityKind,
    pub identity: String,
    #[serde(default)]
    pub family: Option<String>,
    #[serde(default)]
    pub notes: String,
    /// The user ticked "I own this device".
    pub owned: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub at: DateTime<Utc>,
    /// "user" or "assistant"
    pub actor: String,
    pub action: String,
    pub target: String,
    pub result: String,
}

pub struct Store {
    dir: PathBuf,
    lock: Mutex<()>,
}

impl Store {
    pub fn new(dir: PathBuf) -> Self {
        Self { dir, lock: Mutex::new(()) }
    }

    pub fn dir(&self) -> &Path {
        &self.dir
    }

    fn devices_path(&self) -> PathBuf {
        self.dir.join("owned-devices.json")
    }

    fn audit_path(&self) -> PathBuf {
        self.dir.join("audit.jsonl")
    }

    pub fn list(&self) -> Result<Vec<OwnedDevice>, String> {
        let _g = self.lock.lock().map_err(|_| "registry lock poisoned")?;
        self.read_devices()
    }

    fn read_devices(&self) -> Result<Vec<OwnedDevice>, String> {
        match std::fs::read_to_string(self.devices_path()) {
            Ok(s) => serde_json::from_str(&s).map_err(|e| format!("owned-devices.json: {e}")),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(vec![]),
            Err(e) => Err(format!("cannot read registry: {e}")),
        }
    }

    fn write_devices(&self, devices: &[OwnedDevice]) -> Result<(), String> {
        std::fs::create_dir_all(&self.dir).map_err(|e| e.to_string())?;
        let tmp = self.devices_path().with_extension("json.tmp");
        let body = serde_json::to_string_pretty(devices).map_err(|e| e.to_string())?;
        std::fs::write(&tmp, body).map_err(|e| e.to_string())?;
        std::fs::rename(&tmp, self.devices_path()).map_err(|e| e.to_string())
    }

    pub fn add(&self, new: NewDevice) -> Result<OwnedDevice, String> {
        if !new.owned {
            return Err("Tick \"I own this device\" to add the device.".into());
        }
        let identity = new.identity.trim().to_string();
        if identity.is_empty() || new.name.trim().is_empty() {
            return Err("A device needs a name and an identity.".into());
        }
        let _g = self.lock.lock().map_err(|_| "registry lock poisoned")?;
        let mut devices = self.read_devices()?;
        if devices.iter().any(|d| d.identity_kind == new.identity_kind && d.identity.eq_ignore_ascii_case(&identity)) {
            return Err(format!("A device with identity {identity} is already in the list."));
        }
        let now = Utc::now();
        let dev = OwnedDevice {
            id: format!("dev-{}", now.timestamp_millis()),
            name: new.name.trim().to_string(),
            identity_kind: new.identity_kind,
            identity,
            family: new.family,
            notes: new.notes,
            declared_owned_at: now,
        };
        devices.push(dev.clone());
        self.write_devices(&devices)?;
        drop(_g);
        self.audit("user", "registry.add", &dev.identity, "ok");
        Ok(dev)
    }

    pub fn remove(&self, id: &str) -> Result<(), String> {
        let _g = self.lock.lock().map_err(|_| "registry lock poisoned")?;
        let mut devices = self.read_devices()?;
        let before = devices.len();
        let removed: Vec<String> = devices.iter().filter(|d| d.id == id).map(|d| d.identity.clone()).collect();
        devices.retain(|d| d.id != id);
        if devices.len() == before {
            return Err(format!("No device with id {id}."));
        }
        self.write_devices(&devices)?;
        drop(_g);
        self.audit("user", "registry.remove", removed.first().map(String::as_str).unwrap_or(id), "ok");
        Ok(())
    }

    pub fn find_by_identity(&self, kind: IdentityKind, identity: &str) -> Option<OwnedDevice> {
        self.list()
            .ok()?
            .into_iter()
            .find(|d| d.identity_kind == kind && d.identity.eq_ignore_ascii_case(identity))
    }

    /// Append one line to the action log. A log failure never stops the app.
    pub fn audit(&self, actor: &str, action: &str, target: &str, result: &str) {
        let entry = AuditEntry {
            at: Utc::now(),
            actor: actor.into(),
            action: action.into(),
            target: target.into(),
            result: result.into(),
        };
        let _ = std::fs::create_dir_all(&self.dir);
        if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(self.audit_path()) {
            if let Ok(line) = serde_json::to_string(&entry) {
                let _ = writeln!(f, "{line}");
            }
        }
    }

    pub fn audit_tail(&self, n: usize) -> Vec<AuditEntry> {
        let Ok(f) = std::fs::File::open(self.audit_path()) else { return vec![] };
        let all: Vec<AuditEntry> = BufReader::new(f)
            .lines()
            .map_while(Result::ok)
            .filter_map(|l| serde_json::from_str(&l).ok())
            .collect();
        let start = all.len().saturating_sub(n);
        let mut tail = all[start..].to_vec();
        tail.reverse();
        tail
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn new_dev(owned: bool) -> NewDevice {
        NewDevice {
            name: "Bench ESP32".into(),
            identity_kind: IdentityKind::UsbSerial,
            identity: "ABC123".into(),
            family: Some("esp32".into()),
            notes: String::new(),
            owned,
        }
    }

    #[test]
    fn add_needs_the_ownership_tick() {
        let tmp = tempfile::tempdir().unwrap();
        let s = Store::new(tmp.path().into());
        assert!(s.add(new_dev(false)).is_err());
        assert!(s.list().unwrap().is_empty());
    }

    #[test]
    fn add_list_remove_and_audit() {
        let tmp = tempfile::tempdir().unwrap();
        let s = Store::new(tmp.path().into());
        let d = s.add(new_dev(true)).unwrap();
        assert!(s.add(new_dev(true)).is_err(), "duplicate identity");
        assert!(s.find_by_identity(IdentityKind::UsbSerial, "abc123").is_some());
        s.remove(&d.id).unwrap();
        assert!(s.list().unwrap().is_empty());
        let log = s.audit_tail(10);
        assert_eq!(log.len(), 2);
        assert_eq!(log[0].action, "registry.remove");
    }
}
