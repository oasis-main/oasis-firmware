//! Serial port listing and board detection (observe class: no writes).

use crate::boards::{self, Confidence};
use serde::Serialize;
use serialport::SerialPortType;

#[derive(Debug, Clone, Serialize)]
pub struct DetectedPort {
    pub port: String,
    pub kind: String,
    pub vid: Option<u16>,
    pub pid: Option<u16>,
    pub serial_number: Option<String>,
    pub manufacturer: Option<String>,
    pub product: Option<String>,
    pub family: Option<String>,
    pub confidence: Confidence,
    pub label: Option<String>,
}

pub fn list() -> Result<Vec<DetectedPort>, String> {
    let ports = serialport::available_ports().map_err(|e| format!("cannot list serial ports: {e}"))?;
    let mut out: Vec<DetectedPort> = ports
        .into_iter()
        // macOS lists each device twice (/dev/tty.* and /dev/cu.*). Keep cu.*,
        // which does not wait for a carrier signal.
        .filter(|p| !p.port_name.starts_with("/dev/tty.") )
        .map(|p| match p.port_type {
            SerialPortType::UsbPort(info) => {
                let row = boards::match_usb(info.vid, info.pid);
                DetectedPort {
                    port: p.port_name,
                    kind: "usb".into(),
                    vid: Some(info.vid),
                    pid: Some(info.pid),
                    serial_number: info.serial_number,
                    manufacturer: info.manufacturer,
                    product: info.product,
                    family: row.and_then(|r| r.family.clone()),
                    confidence: row.map(|r| r.confidence).unwrap_or(Confidence::Unknown),
                    label: row.map(|r| r.label.clone()),
                }
            }
            other => DetectedPort {
                port: p.port_name,
                kind: match other {
                    SerialPortType::BluetoothPort => "bluetooth",
                    // macOS reports built-in, Bluetooth-audio and debug-console
                    // ports as PCI. None of them is a board.
                    SerialPortType::PciPort => "system",
                    _ => "other",
                }
                .into(),
                vid: None,
                pid: None,
                serial_number: None,
                manufacturer: None,
                product: None,
                family: None,
                confidence: Confidence::Unknown,
                label: None,
            },
        })
        .collect();
    out.sort_by(|a, b| (a.kind != "usb", &a.port).cmp(&(b.kind != "usb", &b.port)));
    Ok(out)
}
