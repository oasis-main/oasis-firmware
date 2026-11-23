//! Board names from arduino-cli (`arduino-cli board list --format json`).
//!
//! The Flash page and the assistant use this list to fill the board name
//! (FQBN) of the `arduino` family. The command only reads the ports. The app
//! runs arduino-cli with an argument list and a time limit (`tools.rs`).

use crate::tools;
use serde::Serialize;
use serde_json::Value;
use std::time::Duration;

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct BoardMatch {
    pub name: String,
    pub fqbn: String,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct ArduinoPort {
    pub port: String,
    pub vid: Option<u16>,
    pub pid: Option<u16>,
    pub serial: Option<String>,
    /// Boards of the installed cores that match the USB id. Empty: the core
    /// is not installed, or the USB id does not name a model (a USB-UART
    /// bridge on a clone board).
    pub matches: Vec<BoardMatch>,
}

fn hex_u16(v: Option<&Value>) -> Option<u16> {
    let s = v?.as_str()?;
    u16::from_str_radix(s.trim_start_matches("0x").trim_start_matches("0X"), 16).ok()
}

/// Read the JSON of `arduino-cli board list --format json`. Version 0.x
/// prints an array of ports. Version 1.x prints `{"detected_ports": [...]}`.
/// Only serial ports with a USB vendor id are kept.
pub fn parse_board_list(json: &str) -> Result<Vec<ArduinoPort>, String> {
    let v: Value = serde_json::from_str(json).map_err(|e| format!("arduino-cli gave output that is not JSON: {e}"))?;
    let items = match &v {
        Value::Array(a) => a.as_slice(),
        Value::Object(o) => o.get("detected_ports").and_then(Value::as_array).map(Vec::as_slice).unwrap_or(&[]),
        _ => &[],
    };
    let mut out = Vec::new();
    for item in items {
        let Some(port) = item.get("port") else { continue };
        if port.get("protocol").and_then(Value::as_str) != Some("serial") {
            continue;
        }
        let Some(address) = port.get("address").and_then(Value::as_str) else { continue };
        let props = port.get("properties");
        let vid = hex_u16(props.and_then(|p| p.get("vid")));
        if vid.is_none() {
            continue;
        }
        let matches = item
            .get("matching_boards")
            .and_then(Value::as_array)
            .map(|a| {
                a.iter()
                    .filter_map(|b| Some(BoardMatch { name: b.get("name")?.as_str()?.into(), fqbn: b.get("fqbn")?.as_str()?.into() }))
                    .filter(|b| crate::flash::valid_fqbn(&b.fqbn))
                    .collect()
            })
            .unwrap_or_default();
        out.push(ArduinoPort {
            port: address.into(),
            vid,
            pid: hex_u16(props.and_then(|p| p.get("pid"))),
            serial: props.and_then(|p| p.get("serialNumber")).and_then(Value::as_str).filter(|s| !s.is_empty()).map(Into::into),
            matches,
        });
    }
    Ok(out)
}

/// Run `arduino-cli board list --format json` (time limit 20 s).
pub fn board_list() -> Result<Vec<ArduinoPort>, String> {
    let exe = tools::find("arduino-cli").ok_or("arduino-cli is not installed or not on PATH.")?;
    let out = tools::run_with_timeout(&exe, &["board", "list", "--format", "json"], Duration::from_secs(20))
        .map_err(|e| format!("Cannot start arduino-cli: {e}"))?;
    if out.timed_out {
        return Err("arduino-cli board list gave no answer in 20 s.".into());
    }
    if out.status != Some(0) {
        let msg = out.stderr.lines().find(|l| !l.trim().is_empty()).unwrap_or("no message");
        return Err(format!("arduino-cli board list failed: {msg}"));
    }
    parse_board_list(&out.stdout)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_version_0_and_version_1_output() {
        let v0 = r#"[
          {"port":{"address":"/dev/cu.Bluetooth","protocol":"serial"}},
          {"port":{"address":"/dev/cu.usbmodem1101","protocol":"serial","properties":{"pid":"0x0042","serialNumber":"95735","vid":"0x2341"}},
           "matching_boards":[{"name":"Arduino Mega or Mega 2560","fqbn":"arduino:avr:mega"}]},
          {"port":{"address":"/dev/cu.wchusbserial10","protocol":"serial","properties":{"pid":"0x7523","vid":"0x1A86"}}},
          {"port":{"address":"192.168.1.9","protocol":"network","properties":{"vid":"0x2341"}}}
        ]"#;
        let ports = parse_board_list(v0).unwrap();
        assert_eq!(ports.len(), 2);
        assert_eq!(ports[0].port, "/dev/cu.usbmodem1101");
        assert_eq!((ports[0].vid, ports[0].pid), (Some(0x2341), Some(0x0042)));
        assert_eq!(ports[0].serial.as_deref(), Some("95735"));
        assert_eq!(ports[0].matches, [BoardMatch { name: "Arduino Mega or Mega 2560".into(), fqbn: "arduino:avr:mega".into() }]);
        assert!(ports[1].matches.is_empty());

        let v1 = r#"{"detected_ports":[{"port":{"address":"COM4","protocol":"serial","properties":{"vid":"0x2341","pid":"0x1002"}},
          "matching_boards":[{"name":"Arduino UNO R4 WiFi","fqbn":"arduino:renesas_uno:unor4wifi"},{"name":"bad","fqbn":"-x"}]}]}"#;
        let ports = parse_board_list(v1).unwrap();
        assert_eq!(ports.len(), 1);
        assert_eq!(ports[0].matches.len(), 1, "an invalid FQBN is dropped");
        assert!(parse_board_list("not json").is_err());
    }
}
