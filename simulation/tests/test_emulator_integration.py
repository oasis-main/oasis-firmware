#!/usr/bin/env python3
"""
Emulator Integration Tests
==========================

Tests for MCU emulation with behavioral models integration.
These tests verify the full firmware-in-loop simulation pipeline.

Note: Some tests require emulator tools to be installed:
- simavr (Arduino): brew install simavr
- Renode (STM32): brew install renode
- QEMU ESP32: See espressif/qemu

Usage:
    cd simulation
    pytest tests/test_emulator_integration.py -v
"""

import pytest
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from behavioral import BehavioralRuntime
from emulators import (
    EmulatorOrchestrator,
    OrchestratorConfig,
    Platform,
    GpioMapping,
    create_orchestrator_from_device_yaml,
)
from mcp_server import OasisSimulationMCP


class TestEmulatorOrchestrator:
    """Test the EmulatorOrchestrator without actual firmware."""
    
    @pytest.fixture
    def behavioral_runtime(self):
        """Create behavioral runtime with components."""
        rt = BehavioralRuntime()
        component_path = Path(__file__).parent.parent / "components"
        rt.load_component_library(component_path)
        return rt
    
    def test_orchestrator_config(self):
        """Test creating orchestrator configuration."""
        config = OrchestratorConfig(
            platform=Platform.ESP32,
            firmware_path="/path/to/firmware.elf",
            gpio_mappings=[
                GpioMapping(
                    mcu_port="D",
                    mcu_pin=4,
                    component_id="air_sensor",
                    signal_name="data",
                    direction="input",
                ),
            ],
        )
        
        assert config.platform == Platform.ESP32
        assert len(config.gpio_mappings) == 1
        assert config.step_size_us == 1000
        print(f"Config: {config}")
    
    def test_gpio_mapping_creation(self):
        """Test GPIO mapping structure."""
        mapping = GpioMapping(
            mcu_port="GPIOA",
            mcu_pin=5,
            component_id="relay",
            signal_name="control",
            direction="output",
        )
        
        assert mapping.mcu_port == "GPIOA"
        assert mapping.mcu_pin == 5
        assert mapping.component_id == "relay"
        assert mapping.direction == "output"
    
    def test_create_from_device_yaml(self):
        """Test creating orchestrator from device.yaml."""
        device_yaml = {
            "device": {
                "id": "test-device",
                "board": {"model": "esp32_devkit"},
            },
            "sensors": [
                {
                    "name": "temp_sensor",
                    "type": "dht22",
                    "pins": {"data": 4},
                }
            ],
            "actuators": [
                {
                    "name": "fan",
                    "type": "relay",
                    "pins": {"output": 25},
                }
            ],
        }
        
        orchestrator = create_orchestrator_from_device_yaml(device_yaml)
        
        assert orchestrator.config.platform == Platform.ESP32
        assert len(orchestrator.config.gpio_mappings) == 2
        print(f"Created orchestrator for {orchestrator.config.platform.value}")
        print(f"GPIO mappings: {len(orchestrator.config.gpio_mappings)}")
    
    def test_behavioral_runtime_integration(self, behavioral_runtime):
        """Test connecting behavioral runtime to orchestrator."""
        config = OrchestratorConfig(
            platform=Platform.ESP32,
            firmware_path="",  # Empty for test
        )
        
        # Can't create orchestrator without firmware, but test the config
        assert config.platform == Platform.ESP32
        
        # Add components to behavioral runtime
        behavioral_runtime.add_component("temp_sensor", "dht22")
        behavioral_runtime.add_component("relay_out", "relay")
        
        # Verify components are added
        assert "temp_sensor" in behavioral_runtime.components
        assert "relay_out" in behavioral_runtime.components
        
        print(f"Components: {list(behavioral_runtime.components.keys())}")


class TestMCPEmulatorTools:
    """Test MCP server emulator tools."""
    
    @pytest.fixture
    def mcp_server(self):
        """Create MCP server instance."""
        component_path = Path(__file__).parent.parent / "components"
        return OasisSimulationMCP(component_path)
    
    def _parse_mcp_result(self, response: dict) -> dict:
        """Parse MCP tool call result from content wrapper."""
        result = response.get("result", {})
        if "content" in result and len(result["content"]) > 0:
            return json.loads(result["content"][0]["text"])
        return result
    
    def test_emulator_platforms_list(self, mcp_server):
        """Test listing available emulator platforms."""
        response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "emulator_platforms",
                "arguments": {}
            }
        })
        
        result = self._parse_mcp_result(response)
        platforms = result.get("platforms", [])
        
        assert len(platforms) >= 7  # At least 7 platforms
        platform_ids = [p["id"] for p in platforms]
        
        assert "arduino_uno" in platform_ids
        assert "stm32f103" in platform_ids
        assert "esp32" in platform_ids
        
        print(f"Available platforms: {platform_ids}")
    
    def test_emulator_tools_in_list(self, mcp_server):
        """Test that emulator tools are listed."""
        response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        
        tools = response["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        
        emulator_tools = [
            "emulator_platforms",
            "emulator_start",
            "emulator_stop",
            "emulator_gpio_set",
            "emulator_gpio_get",
            "emulator_uart_send",
            "emulator_step",
            "emulator_add_gpio_mapping",
        ]
        
        for tool in emulator_tools:
            assert tool in tool_names, f"Missing tool: {tool}"
        
        print(f"Emulator tools available: {len(emulator_tools)}")
    
    def test_emulator_step_behavioral_fallback(self, mcp_server):
        """Test emulator_step falls back to behavioral-only mode."""
        # Start a session
        start_response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "sim_start",
                "arguments": {}
            }
        })
        
        start_result = self._parse_mcp_result(start_response)
        session_id = start_result.get("session_id")
        assert session_id is not None
        
        # Add a component
        mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "component_add",
                "arguments": {
                    "session_id": session_id,
                    "instance_id": "test_sensor",
                    "component_id": "dht22"
                }
            }
        })
        
        # Step without emulator - should fall back to behavioral
        step_response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "emulator_step",
                "arguments": {
                    "session_id": session_id,
                    "duration_us": 5000
                }
            }
        })
        
        step_result = self._parse_mcp_result(step_response)
        assert step_result.get("mode") == "behavioral_only"
        assert step_result.get("sim_time_ms") > 0
        
        print(f"Behavioral fallback: {step_result}")
        
        # Cleanup
        mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "sim_stop",
                "arguments": {"session_id": session_id}
            }
        })


class TestPlatformSpecific:
    """Platform-specific tests that require emulator tools."""
    
    @pytest.fixture
    def check_simavr(self):
        """Check if simavr is available."""
        import subprocess
        try:
            result = subprocess.run(["simavr", "--help"], capture_output=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    @pytest.fixture
    def check_renode(self):
        """Check if Renode is available."""
        import subprocess
        try:
            result = subprocess.run(["renode", "--version"], capture_output=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def test_simavr_available(self, check_simavr):
        """Report simavr availability."""
        if check_simavr:
            print("✅ simavr is available for Arduino emulation")
        else:
            print("⚠️ simavr not installed. Install with: brew install simavr")
            pytest.skip("simavr not available")
    
    def test_renode_available(self, check_renode):
        """Report Renode availability."""
        if check_renode:
            print("✅ Renode is available for STM32 emulation")
        else:
            print("⚠️ Renode not installed. Install with: brew install renode")
            pytest.skip("Renode not available")


class TestSignalBusIntegration:
    """Test signal bus integration between MCU and behavioral models."""
    
    @pytest.fixture
    def runtime_with_components(self):
        """Create runtime with test components."""
        rt = BehavioralRuntime()
        component_path = Path(__file__).parent.parent / "components"
        rt.load_component_library(component_path)
        
        # Add sensor and actuator
        rt.add_component("air_sensor", "dht22")
        rt.add_component("vent_fan", "relay")
        
        return rt
    
    def test_signal_flow_sensor_to_mcu(self, runtime_with_components):
        """Test signal flow from behavioral sensor to MCU input."""
        rt = runtime_with_components
        
        # Set physical input on sensor
        rt.set_physical_input("air_sensor", "temp_actual", 28.5)
        
        # Step to produce output
        rt.step(3500)
        
        # Verify sensor output is on signal bus
        temp = rt.get_output("air_sensor", "temperature")
        assert temp is not None
        assert 26 < temp < 31
        
        # In full integration, this would be read by MCU via GPIO mapping
        print(f"Sensor output on bus: temperature={temp:.1f}°C")
    
    def test_signal_flow_mcu_to_actuator(self, runtime_with_components):
        """Test signal flow from MCU output to behavioral actuator."""
        rt = runtime_with_components
        
        # Simulate MCU setting actuator signal
        from behavioral.runtime import SignalType
        rt.signal_bus.set(
            "vent_fan.control",
            1.0,  # ON
            SignalType.DIGITAL,
            rt.sim_time_ms
        )
        
        # Step to process
        rt.step(200)
        
        # Verify actuator received the signal
        control_signal = rt.signal_bus.get("vent_fan.control")
        assert control_signal is not None
        assert control_signal.value == 1.0
        
        print(f"MCU → Actuator signal: control={control_signal.value}")
    
    def test_full_control_loop_simulation(self, runtime_with_components):
        """Test a complete control loop without actual MCU."""
        rt = runtime_with_components
        
        # Simulate temperature rising
        for temp in [22.0, 24.0, 26.0, 28.0, 30.0]:
            rt.set_physical_input("air_sensor", "temp_actual", temp)
            rt.step(2500)  # Step past read interval
            
            measured = rt.get_output("air_sensor", "temperature")
            
            # Simple threshold control (normally done by MCU)
            fan_on = measured > 27.0 if measured else False
            
            from behavioral.runtime import SignalType
            rt.signal_bus.set(
                "vent_fan.control",
                1.0 if fan_on else 0.0,
                SignalType.DIGITAL,
                rt.sim_time_ms
            )
            
            print(f"T={temp:.1f}°C, Measured={measured:.1f}°C, Fan={'ON' if fan_on else 'OFF'}")
        
        # Final state
        final_temp = rt.get_output("air_sensor", "temperature")
        assert final_temp is not None
        assert final_temp > 25


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
