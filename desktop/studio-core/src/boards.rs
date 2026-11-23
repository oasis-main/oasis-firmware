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

/// How the app reaches the board to write firmware.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum Transport {
    /// A serial or USB port on this computer (`{port}`).
    #[default]
    Usb,
    /// A debug probe on USB (probe-rs). The owned identity is the probe.
    Probe,
    /// A Linux computer on the network (Raspberry Pi), over SSH with key login.
    Ssh,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Family {
    pub family: String,
    pub label: String,
    pub tool: String,
    #[serde(default = "default_baud")]
    pub baud: u32,
    #[serde(default)]
    pub chip: Option<String>,
    /// Write arguments. Placeholders: {port} {baud} {artifact} {chip}.
    /// Empty for `ssh`: the app builds the SSH steps itself.
    #[serde(default)]
    pub args: Vec<String>,
    #[serde(default)]
    pub transport: Transport,
    /// Read the current firmware into a file before the write. None: the
    /// family has no backup method yet.
    #[serde(default)]
    pub backup: Option<Backup>,
    /// Probe selection argument (probe-rs `--probe`). The app adds
    /// `<flag> VID:PID:SERIAL` so that the tool writes only to the owned probe.
    #[serde(default)]
    pub probe_arg: Option<String>,
    /// Time limit for each step, in seconds.
    #[serde(default = "default_timeout")]
    pub timeout_s: u64,
    /// How to run firmware for this family in a simulator. None: no simulator yet.
    #[serde(default)]
    pub simulate: Option<Simulate>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Backup {
    /// Read arguments for `tool`. Placeholders as for `args`, plus {backup}
    /// (the backup file that the app chooses).
    pub args: Vec<String>,
    /// File extension of the backup file: hex, bin, uf2, py.
    pub ext: String,
}

fn default_baud() -> u32 {
    115200
}

fn default_timeout() -> u64 {
    180
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
    fn every_family_has_a_write_method() {
        for f in &table().families {
            match f.transport {
                Transport::Ssh => assert!(f.args.is_empty(), "{}: ssh steps come from code", f.family),
                _ => assert!(f.args.iter().any(|a| a.contains("{artifact}")), "{}: args must name {{artifact}}", f.family),
            }
            if let Some(b) = &f.backup {
                assert!(b.args.iter().any(|a| a.contains("{backup}")), "{}: backup args must name {{backup}}", f.family);
            }
            if f.transport == Transport::Probe {
                assert!(f.probe_arg.is_some(), "{}: a probe family must select the probe", f.family);
            }
        }
        // The four platforms of the project.
        for name in ["esp32", "rpi", "avr_uno", "stm32"] {
            assert!(family(name).is_some(), "missing family {name}");
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
