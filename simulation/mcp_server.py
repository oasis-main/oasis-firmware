"""MCP Server for Oasis Simulation - Exposes simulation control via Model Context Protocol."""

import json
import sys
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

from behavioral import BehavioralRuntime, ComponentSchema


@dataclass
class SimulationSession:
    """A running simulation session."""
    session_id: str
    runtime: BehavioralRuntime
    device_yaml_path: Optional[str] = None


class OasisSimulationMCP:
    """MCP Server implementation for simulation control."""
    
    def __init__(self, component_library_path: Path):
        self.sessions: dict[str, SimulationSession] = {}
        self.component_library_path = component_library_path
        
    def handle_request(self, request: dict) -> dict:
        """Handle a JSON-RPC 2.0 request."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")
        
        try:
            if method == "initialize":
                result = self._initialize(params)
            elif method == "tools/list":
                result = self._list_tools()
            elif method == "tools/call":
                result = self._call_tool(params)
            else:
                return self._error_response(request_id, -32601, f"Method not found: {method}")
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }
        except Exception as e:
            return self._error_response(request_id, -32000, str(e))
    
    def _error_response(self, request_id: Any, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
    
    def _initialize(self, params: dict) -> dict:
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": "oasis-simulation",
                "version": "0.1.0",
            },
        }
    
    def _list_tools(self) -> dict:
        return {
            "tools": [
                {
                    "name": "sim_start",
                    "description": "Start a new simulation session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "device_yaml": {"type": "string", "description": "Path to device.yaml"},
                        },
                    },
                },
                {
                    "name": "sim_stop",
                    "description": "Stop a simulation session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                        },
                        "required": ["session_id"],
                    },
                },
                {
                    "name": "sim_step",
                    "description": "Advance simulation by specified milliseconds",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "duration_ms": {"type": "integer", "default": 1000},
                        },
                        "required": ["session_id"],
                    },
                },
                {
                    "name": "sim_get_state",
                    "description": "Get current simulation state",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                        },
                        "required": ["session_id"],
                    },
                },
                {
                    "name": "sim_set_sensor_value",
                    "description": "Set a physical input value for a sensor",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "instance_id": {"type": "string"},
                            "input_name": {"type": "string"},
                            "value": {"type": "number"},
                        },
                        "required": ["session_id", "instance_id", "input_name", "value"],
                    },
                },
                {
                    "name": "sim_inject_fault",
                    "description": "Inject a fault into a component",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "instance_id": {"type": "string"},
                            "fault_type": {
                                "type": "string",
                                "enum": ["disconnect", "stuck", "offset", "noise_increase"],
                            },
                            "params": {"type": "object"},
                        },
                        "required": ["session_id", "instance_id", "fault_type"],
                    },
                },
                {
                    "name": "component_list",
                    "description": "List available component types",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "component_describe",
                    "description": "Get details about a component type",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "component_id": {"type": "string"},
                        },
                        "required": ["component_id"],
                    },
                },
                {
                    "name": "component_add",
                    "description": "Add a component instance to simulation",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "instance_id": {"type": "string"},
                            "component_id": {"type": "string"},
                            "parameters": {"type": "object"},
                        },
                        "required": ["session_id", "instance_id", "component_id"],
                    },
                },
                # Datasheet ingestion tools
                {
                    "name": "datasheet_parse",
                    "description": "Parse a PDF datasheet and extract component specifications",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "pdf_path": {"type": "string", "description": "Path to PDF datasheet"},
                        },
                        "required": ["pdf_path"],
                    },
                },
                {
                    "name": "datasheet_generate",
                    "description": "Generate component YAML from a parsed datasheet",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "pdf_path": {"type": "string", "description": "Path to PDF datasheet"},
                            "output_path": {"type": "string", "description": "Output YAML path (optional)"},
                            "category": {"type": "string", "description": "Component category (sensors, actuators)"},
                        },
                        "required": ["pdf_path"],
                    },
                },
                # Emulator tools
                {
                    "name": "emulator_platforms",
                    "description": "List supported MCU platforms for emulation",
                    "inputSchema": {"type": "object", "properties": {}},
                },
            ]
        }
    
    def _call_tool(self, params: dict) -> dict:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        handlers = {
            "sim_start": self._tool_sim_start,
            "sim_stop": self._tool_sim_stop,
            "sim_step": self._tool_sim_step,
            "sim_get_state": self._tool_sim_get_state,
            "sim_set_sensor_value": self._tool_sim_set_sensor_value,
            "sim_inject_fault": self._tool_sim_inject_fault,
            "component_list": self._tool_component_list,
            "component_describe": self._tool_component_describe,
            "component_add": self._tool_component_add,
            "datasheet_parse": self._tool_datasheet_parse,
            "datasheet_generate": self._tool_datasheet_generate,
            "emulator_platforms": self._tool_emulator_platforms,
        }
        
        if tool_name not in handlers:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        result = handlers[tool_name](arguments)
        
        return {
            "content": [
                {"type": "text", "text": json.dumps(result, indent=2)}
            ]
        }
    
    def _get_session(self, session_id: str) -> SimulationSession:
        if session_id not in self.sessions:
            raise ValueError(f"Unknown session: {session_id}")
        return self.sessions[session_id]
    
    def _tool_sim_start(self, args: dict) -> dict:
        session_id = str(uuid.uuid4())[:8]
        runtime = BehavioralRuntime()
        runtime.load_component_library(self.component_library_path)
        
        session = SimulationSession(
            session_id=session_id,
            runtime=runtime,
            device_yaml_path=args.get("device_yaml"),
        )
        self.sessions[session_id] = session
        session.runtime.running = True
        
        return {
            "session_id": session_id,
            "status": "started",
            "available_components": runtime.get_available_components(),
        }
    
    def _tool_sim_stop(self, args: dict) -> dict:
        session = self._get_session(args["session_id"])
        session.runtime.running = False
        del self.sessions[args["session_id"]]
        return {"status": "stopped"}
    
    def _tool_sim_step(self, args: dict) -> dict:
        session = self._get_session(args["session_id"])
        duration_ms = args.get("duration_ms", 1000)
        
        session.runtime.step(duration_ms)
        
        return {
            "sim_time_ms": session.runtime.sim_time_ms,
            "components_active": len(session.runtime.components),
        }
    
    def _tool_sim_get_state(self, args: dict) -> dict:
        session = self._get_session(args["session_id"])
        return session.runtime.get_state()
    
    def _tool_sim_set_sensor_value(self, args: dict) -> dict:
        session = self._get_session(args["session_id"])
        session.runtime.set_physical_input(
            args["instance_id"],
            args["input_name"],
            args["value"],
        )
        return {"status": "set", "instance_id": args["instance_id"]}
    
    def _tool_sim_inject_fault(self, args: dict) -> dict:
        session = self._get_session(args["session_id"])
        session.runtime.inject_fault(
            args["instance_id"],
            args["fault_type"],
            **args.get("params", {}),
        )
        return {
            "status": "fault_injected",
            "instance_id": args["instance_id"],
            "fault_type": args["fault_type"],
        }
    
    def _tool_component_list(self, args: dict) -> dict:
        # Load all components from library
        runtime = BehavioralRuntime()
        runtime.load_component_library(self.component_library_path)
        return {"components": runtime.get_available_components()}
    
    def _tool_component_describe(self, args: dict) -> dict:
        component_id = args["component_id"]
        yaml_path = self.component_library_path / "sensors" / f"{component_id}.yaml"
        
        if not yaml_path.exists():
            yaml_path = self.component_library_path / "actuators" / f"{component_id}.yaml"
        if not yaml_path.exists():
            yaml_path = self.component_library_path / "mcu" / f"{component_id}.yaml"
        if not yaml_path.exists():
            raise ValueError(f"Component not found: {component_id}")
        
        schema = ComponentSchema.from_yaml(str(yaml_path))
        return schema.to_dict()
    
    def _tool_component_add(self, args: dict) -> dict:
        session = self._get_session(args["session_id"])
        instance = session.runtime.add_component(
            args["instance_id"],
            args["component_id"],
            **args.get("parameters", {}),
        )
        return {
            "status": "added",
            "instance_id": args["instance_id"],
            "component_id": args["component_id"],
        }
    
    def _tool_datasheet_parse(self, args: dict) -> dict:
        """Parse a PDF datasheet and extract specifications."""
        try:
            from datasheet_ingestion import DatasheetParser
            
            parser = DatasheetParser()
            result = parser.parse_pdf(args["pdf_path"])
            
            return {
                "component_name": result.component_name,
                "manufacturer": result.manufacturer,
                "part_number": result.part_number,
                "component_type": result.component_type,
                "category": result.category,
                "interfaces": result.interfaces,
                "i2c_address": f"0x{result.i2c_address:02X}" if result.i2c_address else None,
                "supply_voltage": {
                    "min": result.supply_voltage_min,
                    "max": result.supply_voltage_max,
                },
                "accuracy": result.accuracy,
                "resolution": result.resolution,
                "confidence": result.extraction_confidence,
            }
        except ImportError:
            return {"error": "Datasheet ingestion requires: pip install oasis-simulation[pdf]"}
        except Exception as e:
            return {"error": str(e)}
    
    def _tool_datasheet_generate(self, args: dict) -> dict:
        """Generate component YAML from a datasheet."""
        try:
            from datasheet_ingestion import DatasheetParser, generate_component_yaml
            
            parser = DatasheetParser()
            extracted = parser.parse_pdf(args["pdf_path"])
            
            output_path = args.get("output_path")
            yaml_content = generate_component_yaml(extracted, output_path)
            
            return {
                "status": "generated",
                "component_id": extracted.component_name.lower().replace(" ", "_"),
                "confidence": extracted.extraction_confidence,
                "yaml": yaml_content if not output_path else None,
                "output_path": output_path,
            }
        except ImportError:
            return {"error": "Datasheet ingestion requires: pip install oasis-simulation[pdf]"}
        except Exception as e:
            return {"error": str(e)}
    
    def _tool_emulator_platforms(self, args: dict) -> dict:
        """List supported MCU platforms."""
        return {
            "platforms": [
                {
                    "id": "arduino_uno",
                    "name": "Arduino Uno",
                    "mcu": "ATmega328P",
                    "emulator": "simavr",
                    "status": "supported",
                },
                {
                    "id": "arduino_mega",
                    "name": "Arduino Mega",
                    "mcu": "ATmega2560",
                    "emulator": "simavr",
                    "status": "supported",
                },
                {
                    "id": "stm32f103",
                    "name": "STM32F103 (Blue Pill)",
                    "mcu": "STM32F103C8T6",
                    "emulator": "renode",
                    "status": "supported",
                },
                {
                    "id": "stm32f401",
                    "name": "STM32F401 (Nucleo)",
                    "mcu": "STM32F401RE",
                    "emulator": "renode",
                    "status": "supported",
                },
                {
                    "id": "stm32f407",
                    "name": "STM32F407 (Discovery)",
                    "mcu": "STM32F407VG",
                    "emulator": "renode",
                    "status": "supported",
                },
                {
                    "id": "esp32",
                    "name": "ESP32 DevKit",
                    "mcu": "ESP32",
                    "emulator": "qemu/wokwi",
                    "status": "supported",
                },
                {
                    "id": "esp32s3",
                    "name": "ESP32-S3",
                    "mcu": "ESP32-S3",
                    "emulator": "qemu/wokwi",
                    "status": "supported",
                },
                {
                    "id": "esp32c3",
                    "name": "ESP32-C3 (RISC-V)",
                    "mcu": "ESP32-C3",
                    "emulator": "qemu",
                    "status": "supported",
                },
            ]
        }


def run_stdio_server():
    """Run the MCP server over stdio."""
    component_library = Path(__file__).parent / "components"
    server = OasisSimulationMCP(component_library)
    
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = server.handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }), flush=True)


if __name__ == "__main__":
    run_stdio_server()
