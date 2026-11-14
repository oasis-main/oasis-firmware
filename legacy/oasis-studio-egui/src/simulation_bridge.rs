//! Bridge between desktop app and Python simulation runtime.
//!
//! Communicates with the simulation MCP server via JSON-RPC over stdio.
//! Supports MCU emulators (simavr, Renode, QEMU) and Linux SBCs (RPi, BeagleBone).

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;
use std::time::Duration;

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

// ─────────────────────────────────────────────────────────────────────────────
// Platform & Board Definitions
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum BoardCategory {
    Mcu,
    LinuxSbc,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformInfo {
    pub id: String,
    pub name: String,
    pub mcu: String,
    pub emulator: String,
    pub status: String,
    #[serde(default)]
    pub os: Option<String>,
    #[serde(default)]
    pub arch: Option<String>,
}

impl PlatformInfo {
    pub fn category(&self) -> BoardCategory {
        if self.os.as_deref() == Some("linux") {
            BoardCategory::LinuxSbc
        } else {
            BoardCategory::Mcu
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Multi-Board Topology
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Default)]
pub enum LinkType {
    #[default]
    Uart,
    I2c,
    Spi,
    Network,
    Gpio,
}

impl std::fmt::Display for LinkType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LinkType::Uart => write!(f, "UART"),
            LinkType::I2c => write!(f, "I2C"),
            LinkType::Spi => write!(f, "SPI"),
            LinkType::Network => write!(f, "Network"),
            LinkType::Gpio => write!(f, "GPIO"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoardNode {
    pub node_id: String,
    pub board_type: String,
    pub x: f32,
    pub y: f32,
    pub is_behavioral: bool,
    pub components: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoardLink {
    pub link_id: String,
    pub node_a: String,
    pub node_b: String,
    pub link_type: LinkType,
    pub config: HashMap<String, Value>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Topology {
    pub nodes: Vec<BoardNode>,
    pub links: Vec<BoardLink>,
}

// ─────────────────────────────────────────────────────────────────────────────
// Test Runner
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TestResult {
    pub name: String,
    pub passed: bool,
    pub duration_ms: u64,
    pub output: String,
}

#[derive(Debug, Clone, Default)]
pub struct TestRunnerState {
    pub available_tests: Vec<String>,
    pub results: Vec<TestResult>,
    pub running: bool,
    pub current_test: Option<String>,
}

pub struct SimulationBridge {
    process: Option<Child>,
    request_id: u64,
    tx: Option<Sender<String>>,
    rx: Option<Receiver<String>>,
    pub session_id: Option<String>,
    pub state: Option<SimulationState>,
    pub available_components: Vec<String>,
    pub available_platforms: Vec<PlatformInfo>,
    pub topology: Topology,
    pub test_runner: TestRunnerState,
    pub error: Option<String>,
    simulation_path: Option<String>,
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
            available_platforms: Vec::new(),
            topology: Topology::default(),
            test_runner: TestRunnerState::default(),
            error: None,
            simulation_path: None,
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
        self.simulation_path = Some(simulation_path.to_string());

        // Initialize the MCP connection
        self.send_request("initialize", json!({}))?;

        // Load available platforms
        self.refresh_platforms()?;

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

    // ─────────────────────────────────────────────────────────────────────────────
    // Platform & Board Management
    // ─────────────────────────────────────────────────────────────────────────────

    /// Refresh available platforms (MCU + Linux SBCs).
    pub fn refresh_platforms(&mut self) -> Result<(), String> {
        let result = self.call_tool("emulator_platforms", json!({}))?;
        
        if let Some(platforms) = result.get("platforms").and_then(|v| v.as_array()) {
            self.available_platforms = platforms
                .iter()
                .filter_map(|v| serde_json::from_value(v.clone()).ok())
                .collect();
        }
        Ok(())
    }

    /// Get MCU platforms only.
    pub fn mcu_platforms(&self) -> Vec<&PlatformInfo> {
        self.available_platforms
            .iter()
            .filter(|p| p.category() == BoardCategory::Mcu)
            .collect()
    }

    /// Get Linux SBC platforms only.
    pub fn linux_platforms(&self) -> Vec<&PlatformInfo> {
        self.available_platforms
            .iter()
            .filter(|p| p.category() == BoardCategory::LinuxSbc)
            .collect()
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // Multi-Board Topology
    // ─────────────────────────────────────────────────────────────────────────────

    /// Add a board node to the topology.
    pub fn add_board_node(&mut self, node_id: &str, board_type: &str, x: f32, y: f32) {
        let node = BoardNode {
            node_id: node_id.to_string(),
            board_type: board_type.to_string(),
            x,
            y,
            is_behavioral: true,
            components: Vec::new(),
        };
        self.topology.nodes.push(node);
    }

    /// Remove a board node from the topology.
    pub fn remove_board_node(&mut self, node_id: &str) {
        self.topology.nodes.retain(|n| n.node_id != node_id);
        self.topology.links.retain(|l| l.node_a != node_id && l.node_b != node_id);
    }

    /// Add a communication link between two nodes.
    pub fn add_link(&mut self, node_a: &str, node_b: &str, link_type: LinkType) {
        let link_id = format!("{}_{:?}_{}", node_a, link_type, node_b).to_lowercase();
        let link = BoardLink {
            link_id,
            node_a: node_a.to_string(),
            node_b: node_b.to_string(),
            link_type,
            config: HashMap::new(),
        };
        self.topology.links.push(link);
    }

    /// Remove a link from the topology.
    pub fn remove_link(&mut self, link_id: &str) {
        self.topology.links.retain(|l| l.link_id != link_id);
    }

    /// Add a component to a board node.
    pub fn add_component_to_node(&mut self, node_id: &str, component_id: &str) -> Result<(), String> {
        // First add to simulation
        let instance_id = format!("{}_{}", node_id, component_id);
        self.add_component(&instance_id, component_id)?;

        // Then track in topology
        if let Some(node) = self.topology.nodes.iter_mut().find(|n| n.node_id == node_id) {
            node.components.push(instance_id);
        }
        Ok(())
    }

    /// Get topology description.
    pub fn topology_description(&self) -> String {
        let mut desc = String::from("Multi-Board Topology:\n");
        desc.push_str(&format!("  Nodes ({}):\n", self.topology.nodes.len()));
        for node in &self.topology.nodes {
            let mode = if node.is_behavioral { "behavioral" } else { "emulated" };
            desc.push_str(&format!("    [{}] {} ({})\n", mode, node.node_id, node.board_type));
        }
        desc.push_str(&format!("  Links ({}):\n", self.topology.links.len()));
        for link in &self.topology.links {
            desc.push_str(&format!("    {} ←{}→ {}\n", link.node_a, link.link_type, link.node_b));
        }
        desc
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // Test Runner
    // ─────────────────────────────────────────────────────────────────────────────

    /// Discover available tests in the simulation directory.
    pub fn discover_tests(&mut self) -> Result<(), String> {
        let sim_path = self.simulation_path.as_ref().ok_or("No simulation path")?;
        
        // Run pytest --collect-only to discover tests
        let output = Command::new("python")
            .args(["-m", "pytest", "--collect-only", "-q", "tests/"])
            .current_dir(sim_path)
            .output()
            .map_err(|e| format!("Failed to discover tests: {}", e))?;

        let stdout = String::from_utf8_lossy(&output.stdout);
        self.test_runner.available_tests = stdout
            .lines()
            .filter(|l| l.contains("::test_"))
            .map(|l| l.trim().to_string())
            .collect();

        Ok(())
    }

    /// Run a specific test.
    pub fn run_test(&mut self, test_name: &str) -> Result<TestResult, String> {
        let sim_path = self.simulation_path.as_ref().ok_or("No simulation path")?;
        
        self.test_runner.running = true;
        self.test_runner.current_test = Some(test_name.to_string());

        let start = std::time::Instant::now();
        
        let output = Command::new("python")
            .args(["-m", "pytest", test_name, "-v", "--tb=short"])
            .current_dir(sim_path)
            .output()
            .map_err(|e| format!("Failed to run test: {}", e))?;

        let duration_ms = start.elapsed().as_millis() as u64;
        let stdout = String::from_utf8_lossy(&output.stdout);
        let stderr = String::from_utf8_lossy(&output.stderr);
        
        let result = TestResult {
            name: test_name.to_string(),
            passed: output.status.success(),
            duration_ms,
            output: format!("{}\n{}", stdout, stderr),
        };

        self.test_runner.results.push(result.clone());
        self.test_runner.running = false;
        self.test_runner.current_test = None;

        Ok(result)
    }

    /// Run all tests.
    pub fn run_all_tests(&mut self) -> Result<Vec<TestResult>, String> {
        let sim_path = self.simulation_path.as_ref().ok_or("No simulation path")?;
        
        self.test_runner.running = true;
        self.test_runner.results.clear();

        let start = std::time::Instant::now();
        
        let output = Command::new("python")
            .args(["-m", "pytest", "tests/", "-v", "--tb=short"])
            .current_dir(sim_path)
            .output()
            .map_err(|e| format!("Failed to run tests: {}", e))?;

        let duration_ms = start.elapsed().as_millis() as u64;
        let stdout = String::from_utf8_lossy(&output.stdout);
        
        // Parse pytest output for individual test results
        for line in stdout.lines() {
            if line.contains("PASSED") || line.contains("FAILED") {
                let passed = line.contains("PASSED");
                let name = line.split_whitespace().next().unwrap_or("unknown").to_string();
                self.test_runner.results.push(TestResult {
                    name,
                    passed,
                    duration_ms: 0, // Individual timing not available in summary
                    output: String::new(),
                });
            }
        }

        self.test_runner.running = false;
        Ok(self.test_runner.results.clone())
    }

    /// Clear test results.
    pub fn clear_test_results(&mut self) {
        self.test_runner.results.clear();
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
