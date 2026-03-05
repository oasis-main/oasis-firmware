//! Bridge between desktop app and Python simulation runtime.
//! 
//! Communicates with the simulation MCP server via JSON-RPC over stdio.

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimulationState {
    pub sim_time_ms: i64,
    pub running: bool,
    pub components: HashMap<String, ComponentState>,
    pub signals: HashMap<String, SignalValue>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentState {
    pub schema_id: String,
    pub state: HashMap<String, Value>,
    pub started: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignalValue {
    pub value: f64,
    pub timestamp_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentInfo {
    pub id: String,
    pub name: String,
    pub component_type: String,
    pub description: String,
    pub inputs: Vec<PortInfo>,
    pub outputs: Vec<PortInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortInfo {
    pub name: String,
    pub signal_type: String,
    pub unit: String,
}

pub struct SimulationBridge {
    process: Option<Child>,
    request_id: u64,
    tx: Option<Sender<String>>,
    rx: Option<Receiver<String>>,
    pub session_id: Option<String>,
    pub state: Option<SimulationState>,
    pub available_components: Vec<String>,
    pub error: Option<String>,
}

impl SimulationBridge {
    pub fn new() -> Self {
        Self {
            process: None,
            request_id: 0,
            tx: None,
            rx: None,
            session_id: None,
            state: None,
            available_components: Vec::new(),
            error: None,
        }
    }

    /// Start the Python simulation server.
    pub fn start_server(&mut self, simulation_path: &str) -> Result<(), String> {
        let mut child = Command::new("python")
            .args(["-m", "mcp_server"])
            .current_dir(simulation_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start simulation server: {}", e))?;

        let stdin = child.stdin.take().ok_or("Failed to get stdin")?;
        let stdout = child.stdout.take().ok_or("Failed to get stdout")?;

        let (tx, rx_internal) = mpsc::channel();
        let (tx_internal, rx) = mpsc::channel();

        // Reader thread
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                if let Ok(line) = line {
                    let _ = tx_internal.send(line);
                }
            }
        });

        // Writer thread
        let mut stdin = stdin;
        thread::spawn(move || {
            while let Ok(msg) = rx_internal.recv() {
                if writeln!(stdin, "{}", msg).is_err() {
                    break;
                }
                let _ = stdin.flush();
            }
        });

        self.process = Some(child);
        self.tx = Some(tx);
        self.rx = Some(rx);

        // Initialize the MCP connection
        self.send_request("initialize", json!({}))?;

        Ok(())
    }

    /// Stop the simulation server.
    pub fn stop_server(&mut self) {
        if let Some(mut process) = self.process.take() {
            let _ = process.kill();
        }
        self.tx = None;
        self.rx = None;
        self.session_id = None;
    }

    fn send_request(&mut self, method: &str, params: Value) -> Result<Value, String> {
        let tx = self.tx.as_ref().ok_or("Server not running")?;
        let rx = self.rx.as_ref().ok_or("Server not running")?;

        self.request_id += 1;
        let request = json!({
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params,
        });

        tx.send(request.to_string())
            .map_err(|e| format!("Send error: {}", e))?;

        // Wait for response (with timeout in real impl)
        let response = rx
            .recv()
            .map_err(|e| format!("Receive error: {}", e))?;

        let response: Value = serde_json::from_str(&response)
            .map_err(|e| format!("Parse error: {}", e))?;

        if let Some(error) = response.get("error") {
            return Err(error["message"].as_str().unwrap_or("Unknown error").to_string());
        }

        Ok(response["result"].clone())
    }

    fn call_tool(&mut self, name: &str, arguments: Value) -> Result<Value, String> {
        let result = self.send_request("tools/call", json!({
            "name": name,
            "arguments": arguments,
        }))?;

        // Extract the text content from MCP response
        if let Some(content) = result.get("content") {
            if let Some(first) = content.as_array().and_then(|a| a.first()) {
                if let Some(text) = first.get("text").and_then(|t| t.as_str()) {
                    return serde_json::from_str(text)
                        .map_err(|e| format!("Parse tool result: {}", e));
                }
            }
        }

        Ok(result)
    }

    /// Start a new simulation session.
    pub fn start_simulation(&mut self, device_yaml: Option<&str>) -> Result<(), String> {
        let args = match device_yaml {
            Some(path) => json!({"device_yaml": path}),
            None => json!({}),
        };

        let result = self.call_tool("sim_start", args)?;
        
        self.session_id = result.get("session_id")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        if let Some(components) = result.get("available_components").and_then(|v| v.as_array()) {
            self.available_components = components
                .iter()
                .filter_map(|v| v.as_str().map(|s| s.to_string()))
                .collect();
        }

        Ok(())
    }

    /// Stop the current simulation session.
    pub fn stop_simulation(&mut self) -> Result<(), String> {
        let session_id = self.session_id.as_ref().ok_or("No active session")?;
        self.call_tool("sim_stop", json!({"session_id": session_id}))?;
        self.session_id = None;
        self.state = None;
        Ok(())
    }

    /// Advance simulation by specified milliseconds.
    pub fn step(&mut self, duration_ms: i64) -> Result<(), String> {
        let session_id = self.session_id.as_ref().ok_or("No active session")?;
        self.call_tool("sim_step", json!({
            "session_id": session_id,
            "duration_ms": duration_ms,
        }))?;
        self.refresh_state()?;
        Ok(())
    }

    /// Refresh the simulation state.
    pub fn refresh_state(&mut self) -> Result<(), String> {
        let session_id = self.session_id.as_ref().ok_or("No active session")?;
        let result = self.call_tool("sim_get_state", json!({"session_id": session_id}))?;
        
        self.state = serde_json::from_value(result).ok();
        Ok(())
    }

    /// Add a component to the simulation.
    pub fn add_component(&mut self, instance_id: &str, component_id: &str) -> Result<(), String> {
        let session_id = self.session_id.as_ref().ok_or("No active session")?;
        self.call_tool("component_add", json!({
            "session_id": session_id,
            "instance_id": instance_id,
            "component_id": component_id,
        }))?;
        self.refresh_state()?;
        Ok(())
    }

    /// Set a sensor's physical input value.
    pub fn set_sensor_value(&mut self, instance_id: &str, input_name: &str, value: f64) -> Result<(), String> {
        let session_id = self.session_id.as_ref().ok_or("No active session")?;
        self.call_tool("sim_set_sensor_value", json!({
            "session_id": session_id,
            "instance_id": instance_id,
            "input_name": input_name,
            "value": value,
        }))?;
        Ok(())
    }

    /// Inject a fault into a component.
    pub fn inject_fault(&mut self, instance_id: &str, fault_type: &str) -> Result<(), String> {
        let session_id = self.session_id.as_ref().ok_or("No active session")?;
        self.call_tool("sim_inject_fault", json!({
            "session_id": session_id,
            "instance_id": instance_id,
            "fault_type": fault_type,
        }))?;
        Ok(())
    }

    /// Get details about a component type.
    pub fn describe_component(&mut self, component_id: &str) -> Result<Value, String> {
        self.call_tool("component_describe", json!({"component_id": component_id}))
    }
}

impl Default for SimulationBridge {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for SimulationBridge {
    fn drop(&mut self) {
        self.stop_server();
    }
}
