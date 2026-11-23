//! MCP (Model Context Protocol) server logic, without the transport.
//!
//! The binary `oasis-studio-mcp` reads one JSON-RPC 2.0 message from each
//! line of stdin and gives the line to [`Server::handle_line`]. The server
//! writes each response and notification through the `out` function, one
//! JSON object for each line of stdout.
//!
//! Supported methods:
//! - `initialize`, `ping`, `tools/list`, `tools/call`
//! - notifications: `notifications/initialized`, `notifications/cancelled`
//!
//! `tools/call` runs on its own thread, so a long `sim_run` does not block
//! `ping` or a cancel. A `notifications/cancelled` for a running call sets
//! the call's stop flag. If the request has `_meta.progressToken`, the
//! server sends `notifications/progress` while `sim_run` gets UART lines.

use crate::catalog::{self, CallContext, CallError, ToolClass};
use crate::{Actor, Studio};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

/// Protocol versions that this server accepts, newest first.
pub const PROTOCOL_VERSIONS: &[&str] = &["2025-06-18", "2025-03-26", "2024-11-05"];
pub const SERVER_NAME: &str = "oasis-studio";

pub const INSTRUCTIONS: &str = "Oasis Studio tools for device.yaml design, firmware generation, board detection, flash planning, and local simulation (simavr for Arduino Uno, Renode for STM32F103). \
Class observe: the tool reads only. Class propose: the tool prepares a change (generated files in the projects folder, a flash plan, or a local simulator run) and writes one action-log line with actor \"mcp\". \
No tool writes to a device or runs a flash. No tool adds an owned device. A person does both in the Oasis Studio app.";

pub type Out = Arc<dyn Fn(Value) + Send + Sync>;

const PARSE_ERROR: i64 = -32700;
const INVALID_REQUEST: i64 = -32600;
const METHOD_NOT_FOUND: i64 = -32601;
const INVALID_PARAMS: i64 = -32602;

pub struct Server {
    studio: Arc<Studio>,
    out: Out,
    /// Stop flags of running `tools/call` requests, by request id (JSON text).
    running: Arc<Mutex<HashMap<String, Arc<AtomicBool>>>>,
    threads: Mutex<Vec<JoinHandle<()>>>,
}

fn response(id: &Value, result: Value) -> Value {
    json!({ "jsonrpc": "2.0", "id": id, "result": result })
}

fn error(id: &Value, code: i64, message: impl Into<String>) -> Value {
    json!({ "jsonrpc": "2.0", "id": id, "error": { "code": code, "message": message.into() } })
}

/// The `tools/list` entry for one catalog tool.
pub fn tool_entry(def: &catalog::ToolDef) -> Value {
    let class = match def.class {
        ToolClass::Observe => "Class: observe (reads only, changes nothing).",
        ToolClass::Propose => "Class: propose (prepares a change; never writes to a device).",
    };
    json!({
        "name": def.name,
        "title": def.title,
        "description": format!("{} {class}", def.description),
        "inputSchema": def.input_schema(),
        "annotations": {
            "title": def.title,
            "readOnlyHint": def.class == ToolClass::Observe,
            "destructiveHint": false,
            "idempotentHint": def.class == ToolClass::Observe,
            "openWorldHint": false
        }
    })
}

/// Pick the protocol version: the client's version if this server knows it,
/// else the newest version that this server knows.
pub fn negotiate(requested: Option<&str>) -> &'static str {
    requested
        .and_then(|r| PROTOCOL_VERSIONS.iter().copied().find(|v| *v == r))
        .unwrap_or(PROTOCOL_VERSIONS[0])
}

impl Server {
    pub fn new(studio: Arc<Studio>, out: Out) -> Self {
        Server { studio, out, running: Arc::default(), threads: Mutex::new(Vec::new()) }
    }

    /// Handle one line of input. Responses go to `out`.
    pub fn handle_line(&self, line: &str) {
        let line = line.trim();
        if line.is_empty() {
            return;
        }
        match serde_json::from_str::<Value>(line) {
            Err(e) => (self.out)(error(&Value::Null, PARSE_ERROR, format!("Parse error: {e}"))),
            Ok(Value::Object(msg)) => self.handle(Value::Object(msg)),
            Ok(Value::Array(_)) => (self.out)(error(&Value::Null, INVALID_REQUEST, "JSON-RPC batches are not supported")),
            Ok(_) => (self.out)(error(&Value::Null, INVALID_REQUEST, "a message must be a JSON object")),
        }
    }

    fn handle(&self, msg: Value) {
        let method = msg.get("method").and_then(Value::as_str);
        let id = msg.get("id").cloned();
        let params = msg.get("params").cloned().unwrap_or(Value::Null);
        match (method, id) {
            // A response from the client. This server sends no requests.
            (None, Some(_)) if msg.get("result").is_some() || msg.get("error").is_some() => {}
            (None, id) => (self.out)(error(&id.unwrap_or(Value::Null), INVALID_REQUEST, "no method")),
            // Notifications get no response.
            (Some(m), None) => self.notification(m, &params),
            (Some(m), Some(id)) => self.request(m, id, params),
        }
    }

    fn notification(&self, method: &str, params: &Value) {
        if method == "notifications/cancelled" {
            if let Some(id) = params.get("requestId") {
                if let Some(stop) = self.running.lock().ok().and_then(|r| r.get(&id.to_string()).cloned()) {
                    stop.store(true, Ordering::SeqCst);
                }
            }
        }
        // notifications/initialized and unknown notifications: nothing to do.
    }

    fn request(&self, method: &str, id: Value, params: Value) {
        let reply = match method {
            "initialize" => {
                let version = negotiate(params.get("protocolVersion").and_then(Value::as_str));
                response(
                    &id,
                    json!({
                        "protocolVersion": version,
                        "capabilities": { "tools": { "listChanged": false } },
                        "serverInfo": { "name": SERVER_NAME, "title": "Oasis Studio", "version": env!("CARGO_PKG_VERSION") },
                        "instructions": INSTRUCTIONS
                    }),
                )
            }
            "ping" => response(&id, json!({})),
            "tools/list" => response(&id, json!({ "tools": catalog::tools().iter().map(tool_entry).collect::<Vec<_>>() })),
            "tools/call" => return self.tools_call(id, params),
            other => error(&id, METHOD_NOT_FOUND, format!("Method not found: {other}")),
        };
        (self.out)(reply);
    }

    fn tools_call(&self, id: Value, params: Value) {
        let Some(name) = params.get("name").and_then(Value::as_str).map(str::to_string) else {
            return (self.out)(error(&id, INVALID_PARAMS, "tools/call needs params.name"));
        };
        if catalog::find(&name).is_none() {
            return (self.out)(error(&id, INVALID_PARAMS, format!("Unknown tool: {name}")));
        }
        let args = params.get("arguments").cloned().unwrap_or(Value::Null);
        let token = params.get("_meta").and_then(|m| m.get("progressToken")).cloned();
        let key = id.to_string();
        let stop = Arc::new(AtomicBool::new(false));
        if let Ok(mut r) = self.running.lock() {
            r.insert(key.clone(), stop.clone());
        }
        let (studio, out, running) = (self.studio.clone(), self.out.clone(), self.running.clone());
        let handle = std::thread::spawn(move || {
            let progress_out = out.clone();
            let progress = move |p: f64, message: Option<String>| {
                if let Some(t) = &token {
                    let mut params = json!({ "progressToken": t, "progress": p });
                    if let Some(m) = message {
                        params["message"] = Value::String(m);
                    }
                    progress_out(json!({ "jsonrpc": "2.0", "method": "notifications/progress", "params": params }));
                }
            };
            let ctx = CallContext { actor: Actor::Mcp, cancel: stop, progress: Some(&progress) };
            let reply = match catalog::call(&studio, &name, &args, &ctx) {
                Ok(v) => response(&id, tool_result(v)),
                Err(CallError::UnknownTool(n)) => error(&id, INVALID_PARAMS, format!("Unknown tool: {n}")),
                Err(e) => response(&id, json!({ "content": [{ "type": "text", "text": e.to_string() }], "isError": true })),
            };
            if let Ok(mut r) = running.lock() {
                r.remove(&key);
            }
            out(reply);
        });
        if let Ok(mut t) = self.threads.lock() {
            t.retain(|h| !h.is_finished());
            t.push(handle);
        }
    }

    /// Stop every running call and wait for each one to send its response.
    /// The binary calls this at the end of stdin.
    pub fn shutdown(&self) {
        if let Ok(r) = self.running.lock() {
            for stop in r.values() {
                stop.store(true, Ordering::SeqCst);
            }
        }
        let threads = std::mem::take(&mut *self.threads.lock().unwrap_or_else(|p| p.into_inner()));
        for t in threads {
            let _ = t.join();
        }
    }
}

/// A successful tool result: the JSON as text, and as structured content
/// when the JSON is an object.
fn tool_result(v: Value) -> Value {
    let text = serde_json::to_string_pretty(&v).unwrap_or_default();
    let mut r = json!({ "content": [{ "type": "text", "text": text }], "isError": false });
    if v.is_object() {
        r["structuredContent"] = v;
    }
    r
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Paths;

    fn server() -> (tempfile::TempDir, Server, Arc<Mutex<Vec<Value>>>) {
        let tmp = tempfile::tempdir().unwrap();
        let studio = Arc::new(Studio::new(Paths { data_dir: tmp.path().join("data"), projects_dir: tmp.path().join("projects") }));
        let sent = Arc::new(Mutex::new(Vec::new()));
        let sink = sent.clone();
        let s = Server::new(studio, Arc::new(move |v| sink.lock().unwrap().push(v)));
        (tmp, s, sent)
    }

    fn send(s: &Server, v: Value) {
        s.handle_line(&v.to_string());
        s.shutdown();
    }

    #[test]
    fn initialize_negotiates_the_version() {
        let (_t, s, sent) = server();
        send(&s, json!({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}));
        send(&s, json!({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}}));
        let sent = sent.lock().unwrap();
        assert_eq!(sent[0]["result"]["protocolVersion"], "2025-03-26");
        assert_eq!(sent[0]["result"]["serverInfo"]["name"], SERVER_NAME);
        assert!(sent[0]["result"]["capabilities"]["tools"].is_object());
        assert_eq!(sent[1]["result"]["protocolVersion"], PROTOCOL_VERSIONS[0]);
    }

    #[test]
    fn notifications_get_no_response() {
        let (_t, s, sent) = server();
        send(&s, json!({"jsonrpc": "2.0", "method": "notifications/initialized"}));
        send(&s, json!({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 9}}));
        send(&s, json!({"jsonrpc": "2.0", "method": "something/else"}));
        assert!(sent.lock().unwrap().is_empty());
    }

    #[test]
    fn errors_for_bad_input() {
        let (_t, s, sent) = server();
        s.handle_line("{not json");
        s.handle_line("[1, 2]");
        send(&s, json!({"jsonrpc": "2.0", "id": 3, "method": "resources/list"}));
        send(&s, json!({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "flash_now"}}));
        let sent = sent.lock().unwrap();
        assert_eq!(sent[0]["error"]["code"], PARSE_ERROR);
        assert_eq!(sent[1]["error"]["code"], INVALID_REQUEST);
        assert_eq!(sent[2]["error"]["code"], METHOD_NOT_FOUND);
        assert_eq!(sent[3]["error"]["code"], INVALID_PARAMS);
    }

    #[test]
    fn tools_list_has_classes_as_annotations() {
        let (_t, s, sent) = server();
        send(&s, json!({"jsonrpc": "2.0", "id": "a", "method": "tools/list"}));
        let sent = sent.lock().unwrap();
        let tools = sent[0]["result"]["tools"].as_array().unwrap();
        assert_eq!(tools.len(), catalog::tools().len());
        let get = |n: &str| tools.iter().find(|t| t["name"] == n).unwrap().clone();
        assert_eq!(get("validate_config")["annotations"]["readOnlyHint"], true);
        assert_eq!(get("sim_run")["annotations"]["readOnlyHint"], false);
        assert!(get("flash_plan")["description"].as_str().unwrap().contains("No tool runs a flash"));
    }

    #[test]
    fn tool_errors_are_results_with_is_error() {
        let (_t, s, sent) = server();
        send(&s, json!({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "validate_config", "arguments": {}}}));
        send(&s, json!({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "validate_config", "arguments": {"yaml": "device: ["}}}));
        let sent = sent.lock().unwrap();
        assert_eq!(sent[0]["result"]["isError"], true);
        assert_eq!(sent[1]["result"]["isError"], false);
        assert_eq!(sent[1]["result"]["structuredContent"]["ok"], false);
    }
}
