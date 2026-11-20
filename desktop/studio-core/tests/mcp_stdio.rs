//! End-to-end test: start `oasis-studio-mcp`, send JSON-RPC over stdio, and
//! read the responses, as an MCP client does.

use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};

struct Client {
    child: Child,
    stdin: Option<ChildStdin>,
    stdout: BufReader<ChildStdout>,
}

impl Client {
    fn start(data: &Path, projects: &Path) -> Client {
        let mut child = Command::new(env!("CARGO_BIN_EXE_oasis-studio-mcp"))
            .args(["--data-dir".as_ref(), data.as_os_str(), "--projects-dir".as_ref(), projects.as_os_str()])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .expect("start oasis-studio-mcp");
        let stdin = child.stdin.take();
        let stdout = BufReader::new(child.stdout.take().unwrap());
        Client { child, stdin, stdout }
    }

    fn send(&mut self, msg: Value) {
        let s = self.stdin.as_mut().unwrap();
        writeln!(s, "{msg}").unwrap();
        s.flush().unwrap();
    }

    fn recv(&mut self) -> Value {
        let mut line = String::new();
        assert!(self.stdout.read_line(&mut line).unwrap() > 0, "server closed stdout");
        serde_json::from_str(&line).unwrap_or_else(|e| panic!("stdout line is not JSON ({e}): {line}"))
    }

    fn request(&mut self, id: u64, method: &str, params: Value) -> Value {
        self.send(json!({ "jsonrpc": "2.0", "id": id, "method": method, "params": params }));
        loop {
            let msg = self.recv();
            if msg["id"] == id {
                return msg;
            }
        }
    }
}

#[test]
fn initialize_list_and_call_over_stdio() {
    let tmp = tempfile::tempdir().unwrap();
    let (data, projects) = (tmp.path().join("data"), tmp.path().join("projects"));
    let mut c = Client::start(&data, &projects);

    let init = c.request(1, "initialize", json!({
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": { "name": "e2e-test", "version": "1" }
    }));
    assert_eq!(init["result"]["protocolVersion"], "2025-06-18", "{init}");
    assert_eq!(init["result"]["serverInfo"]["name"], "oasis-studio");
    c.send(json!({ "jsonrpc": "2.0", "method": "notifications/initialized" }));

    let list = c.request(2, "tools/list", json!({}));
    let names: Vec<&str> = list["result"]["tools"].as_array().unwrap().iter().filter_map(|t| t["name"].as_str()).collect();
    for want in ["validate_config", "generate_firmware", "list_ports", "list_tools", "list_families", "flash_plan", "sim_plan", "sim_run", "audit_tail"] {
        assert!(names.contains(&want), "{want} missing from {names:?}");
    }
    assert!(!names.iter().any(|n| n.contains("registry_add") || n.contains("flash_run")), "{names:?}");

    let example = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../examples/greenhouse-demo.yaml");
    let v = c.request(3, "tools/call", json!({ "name": "validate_config", "arguments": { "path": example } }));
    assert_eq!(v["result"]["isError"], false, "{v}");
    assert_eq!(v["result"]["structuredContent"]["ok"], true, "{v}");
    let text: Value = serde_json::from_str(v["result"]["content"][0]["text"].as_str().unwrap()).unwrap();
    assert_eq!(text["summary"]["model"], "esp32_devkit");

    let g = c.request(4, "tools/call", json!({ "name": "generate_firmware", "arguments": { "path": example } }));
    assert_eq!(g["result"]["isError"], false, "{g}");
    assert!(g["result"]["structuredContent"]["output_dir"].as_str().unwrap().starts_with(projects.to_str().unwrap()));

    let log = c.request(5, "tools/call", json!({ "name": "audit_tail", "arguments": { "limit": 1 } }));
    let entry = &log["result"]["structuredContent"];
    // audit_tail returns an array, so the result has text content only.
    assert!(entry.is_null());
    let entries: Value = serde_json::from_str(log["result"]["content"][0]["text"].as_str().unwrap()).unwrap();
    assert_eq!(entries[0]["actor"], "mcp");
    assert_eq!(entries[0]["action"], "firmware.generate");

    let ping = c.request(6, "ping", json!({}));
    assert_eq!(ping["result"], json!({}));

    // End of stdin ends the server.
    drop(c.stdin.take());
    let status = c.child.wait().unwrap();
    assert!(status.success(), "{status}");
}

#[test]
fn list_tools_flag_prints_classes() {
    let out = Command::new(env!("CARGO_BIN_EXE_oasis-studio-mcp")).arg("--list-tools").output().unwrap();
    let text = String::from_utf8(out.stdout).unwrap();
    assert!(text.lines().any(|l| l.starts_with("sim_run") && l.contains("propose")), "{text}");
    assert!(text.lines().any(|l| l.starts_with("validate_config") && l.contains("observe")), "{text}");
}

/// Runs only when the fixture ELF files are set (see the sim-ci workflow):
/// a Renode run to the end, and a simavr run that the client cancels.
#[test]
fn sim_run_over_stdio_with_progress_and_cancel() {
    let (Ok(stm32), Ok(avr)) = (std::env::var("OASIS_SIM_STM32_ELF"), std::env::var("OASIS_SIM_AVR_ELF")) else {
        eprintln!("skip: OASIS_SIM_STM32_ELF and OASIS_SIM_AVR_ELF not set");
        return;
    };
    let tmp = tempfile::tempdir().unwrap();
    let mut c = Client::start(&tmp.path().join("data"), &tmp.path().join("projects"));
    c.request(1, "initialize", json!({ "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": { "name": "e2e", "version": "1" } }));

    let r = c.request(2, "tools/call", json!({ "name": "sim_run", "arguments": { "family": "stm32", "artifact": stm32, "seconds": 0.2 } }));
    let s = &r["result"]["structuredContent"];
    assert_eq!(r["result"]["isError"], false, "{r}");
    assert!(s["uart"].as_array().unwrap().iter().any(|l| l == "oasis f103 hello"), "{r}");
    assert_eq!(s["exit"]["reason"], "exited", "{r}");

    // A long simavr run with a progress token. Cancel it after the first
    // progress notification.
    c.send(json!({ "jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "sim_run", "arguments": { "family": "avr_uno", "artifact": avr, "seconds": 30 },
        "_meta": { "progressToken": "p1" } } }));
    let first = c.recv();
    assert_eq!(first["method"], "notifications/progress", "{first}");
    assert_eq!(first["params"]["progressToken"], "p1");
    c.send(json!({ "jsonrpc": "2.0", "method": "notifications/cancelled", "params": { "requestId": 3, "reason": "test" } }));
    let r = loop {
        let m = c.recv();
        if m["id"] == 3 {
            break m;
        }
    };
    let s = &r["result"]["structuredContent"];
    assert_eq!(s["exit"]["reason"], "stopped", "{r}");
    assert!(s["uart"].as_array().unwrap().iter().any(|l| l == "tick 0"), "{r}");

    let log = c.request(4, "tools/call", json!({ "name": "audit_tail", "arguments": { "limit": 2 } }));
    let entries: Value = serde_json::from_str(log["result"]["content"][0]["text"].as_str().unwrap()).unwrap();
    assert_eq!(entries[0]["actor"], "mcp");
    assert_eq!(entries[0]["action"], "sim.run");
    assert!(entries[0]["result"].as_str().unwrap().starts_with("stopped"), "{entries}");
    drop(c.stdin.take());
    assert!(c.child.wait().unwrap().success());
}
