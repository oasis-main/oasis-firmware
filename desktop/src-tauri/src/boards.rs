//! Board table: USB ids to board families, and one flash recipe per family.
//! The data lives in `boards.yaml` next to `Cargo.toml`.

use serde::{Deserialize, Serialize};
use std::sync::OnceLock;

const BOARDS_YAML: &str = include_str!("../boards.yaml");

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Confidence {
    Exact,
    Bridge,
    Unknown,
}

#[derive(Debug, Clone, Deserialize)]
pub struct UsbRow {
    pub vid: u16,
    pub pid: Option<u16>,
    pub family: Option<String>,
    pub confidence: Confidence,
    pub label: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Family {
    pub family: String,
    pub label: String,
    pub tool: String,
    pub baud: u32,
    #[serde(default)]
    pub chip: Option<String>,
    pub args: Vec<String>,
    /// How to run firmware for this family in a simulator. None: no simulator yet.
    #[serde(default)]
    pub simulate: Option<Simulate>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Simulate {
    /// Program name: "simavr" or "renode".
    pub engine: String,
    /// simavr: argument list ({artifact} is replaced).
    #[serde(default)]
    pub args: Vec<String>,
    /// Renode: platform description, relative to the Renode install.
    #[serde(default)]
    pub platform: Option<String>,
    /// Renode: UART peripheral to capture.
    #[serde(default)]
    pub uart: Option<String>,
    /// Accepted firmware kinds: elf, hex, bin.
    pub accepts: Vec<String>,
    /// Required ELF machine (40 = ARM, 83 = AVR).
    #[serde(default)]
    pub elf_machine: Option<u16>,
}

#[derive(Debug, Deserialize)]
pub struct BoardTable {
    pub usb: Vec<UsbRow>,
    pub families: Vec<Family>,
}

pub fn table() -> &'static BoardTable {
    static TABLE: OnceLock<BoardTable> = OnceLock::new();
    TABLE.get_or_init(|| serde_yaml::from_str(BOARDS_YAML).expect("boards.yaml is valid"))
}

/// Find the best row for a USB id. A row with an exact pid wins over a
/// vendor-only row.
pub fn match_usb(vid: u16, pid: u16) -> Option<&'static UsbRow> {
    let t = table();
    t.usb
        .iter()
        .find(|r| r.vid == vid && r.pid == Some(pid))
        .or_else(|| t.usb.iter().find(|r| r.vid == vid && r.pid.is_none()))
}

pub fn family(name: &str) -> Option<&'static Family> {
    table().families.iter().find(|f| f.family == name)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn table_parses_and_every_family_reference_exists() {
        let t = table();
        assert!(!t.usb.is_empty());
        for row in &t.usb {
            if let Some(f) = &row.family {
                assert!(family(f).is_some(), "row {} names unknown family {f}", row.label);
            }
            if row.confidence == Confidence::Bridge {
                assert!(row.family.is_none(), "bridge row {} must not name a family", row.label);
            }
        }
    }

    #[test]
    fn exact_pid_wins_over_vendor_row() {
        let uno = match_usb(0x2341, 0x0043).unwrap();
        assert_eq!(uno.family.as_deref(), Some("avr_uno"));
        let other = match_usb(0x2341, 0x9999).unwrap();
        assert_eq!(other.confidence, Confidence::Bridge);
        assert!(match_usb(0xFFFF, 0x0001).is_none());
    }
}
