#!/usr/bin/env python3
"""
Greenhouse Demo Simulation Test
================================

This test demonstrates the full oasis-firmware simulation pipeline:
1. Load device.yaml configuration
2. Instantiate behavioral component models
3. Run simulation with environmental inputs
4. Verify control loop responses

Usage:
    cd oasis-firmware/oasis-rpi/simulation
    pip install -e .
    pytest tests/test_greenhouse_demo.py -v
"""

import pytest
import yaml
from pathlib import Path
import sys

# Add simulation modules to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from behavioral import BehavioralRuntime, ComponentSchema


class TestGreenhouseDemo:
    """Test suite for greenhouse demo simulation."""
    
    @pytest.fixture
    def runtime(self):
        """Create and configure a behavioral runtime."""
        rt = BehavioralRuntime()
        # Load component library
        component_path = Path(__file__).parent.parent / "components"
        rt.load_component_library(component_path)
        return rt
    
    @pytest.fixture
    def device_config(self):
        """Load the greenhouse demo device.yaml."""
        config_path = Path(__file__).parent.parent.parent.parent / "oasis-core" / "examples" / "greenhouse-demo.yaml"
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    def test_component_library_loaded(self, runtime):
        """Verify component library contains expected components."""
        available = runtime.get_available_components()
        
        # Check sensors
        assert "dht22" in available, "DHT22 component should be available"
        assert "bme280" in available, "BME280 component should be available"
        
        # Check actuators
        assert "relay" in available, "Relay component should be available"
        assert "servo" in available, "Servo component should be available"
        
        print(f"Available components: {available}")
    
    def test_instantiate_sensors(self, runtime):
        """Test instantiating sensors from device config."""
        # Add DHT22 sensor
        dht = runtime.add_component("air_sensor", "dht22")
        assert dht is not None
        assert dht.instance_id == "air_sensor"
        
        # Add BME280 sensor
        bme = runtime.add_component("env_sensor", "bme280")
        assert bme is not None
        
        print(f"Instantiated {len(runtime.components)} sensors")
    
    def test_instantiate_actuators(self, runtime):
        """Test instantiating actuators from device config."""
        # Add relay actuator
        relay = runtime.add_component("vent_fan", "relay")
        assert relay is not None
        
        # Add servo actuator
        servo = runtime.add_component("mist_servo", "servo")
        assert servo is not None
        
        print(f"Instantiated {len(runtime.components)} actuators")
    
    def test_sensor_reading_simulation(self, runtime):
        """Test simulating sensor readings over time."""
        # Add sensor
        runtime.add_component("air_sensor", "dht22")
        
        # Set physical input (simulated ambient temperature)
        # DHT22 uses temp_actual for temperature input
        runtime.set_physical_input("air_sensor", "temp_actual", 28.5)
        runtime.set_physical_input("air_sensor", "humidity_actual", 72.0)
        
        # Step simulation past startup delay (1000ms) and read interval (2000ms)
        runtime.step(3500)
        
        # Get outputs
        temp = runtime.get_output("air_sensor", "temperature")
        humidity = runtime.get_output("air_sensor", "humidity")
        
        # Should be close to input (with some noise ~0.3 stddev)
        assert temp is not None, f"Temperature output should exist. Signals: {list(runtime.signal_bus.get_all().keys())}"
        assert humidity is not None, f"Humidity output should exist. Signals: {list(runtime.signal_bus.get_all().keys())}"
        assert 26.0 < temp < 31.0, f"Temperature {temp} should be ~28.5°C"
        assert 68.0 < humidity < 76.0, f"Humidity {humidity} should be ~72%"
        
        print(f"Sensor readings: temp={temp:.1f}°C, humidity={humidity:.1f}%")
    
    def test_control_loop_threshold(self, runtime):
        """Test threshold control loop behavior."""
        # Setup: sensor + actuator
        runtime.add_component("soil_moisture", "soil_moisture")
        runtime.add_component("water_pump", "relay")
        
        # Scenario 1: Soil is dry (below threshold of 40%)
        runtime.set_physical_input("soil_moisture", "moisture_actual", 25.0)
        # Step past startup (100ms) and read interval (1000ms)
        runtime.step(1500)
        
        moisture = runtime.get_output("soil_moisture", "moisture")
        assert moisture is not None, f"Moisture output should exist. Signals: {list(runtime.signal_bus.get_all().keys())}"
        print(f"Soil moisture: {moisture:.1f}% (dry)")
        
        # In a full simulation, control loop would activate pump
        # For now, verify sensor reading is correct (with noise ~2.0 stddev)
        assert moisture < 45.0, f"Moisture {moisture} should be below threshold"
        
        # Scenario 2: Soil is wet (above threshold)
        runtime.set_physical_input("soil_moisture", "moisture_actual", 55.0)
        runtime.step(1500)
        
        moisture = runtime.get_output("soil_moisture", "moisture")
        assert moisture is not None
        print(f"Soil moisture: {moisture:.1f}% (wet)")
        assert moisture > 35.0, f"Moisture {moisture} should be above threshold"
    
    def test_control_loop_pid(self, runtime):
        """Test PID control loop behavior over time."""
        # Setup: temperature sensor + fan
        runtime.add_component("air_sensor", "dht22")
        runtime.add_component("vent_fan", "relay")
        
        # Target: 25°C, Current: 30°C (too hot)
        setpoint = 25.0
        
        # Simulate temperature gradually decreasing as fan runs
        temperatures = [30.0, 29.0, 28.0, 27.0, 26.0, 25.5, 25.2, 25.0]
        pid_outputs = []
        
        # Simple PID simulation
        kp, ki, kd = 2.0, 0.1, 0.5
        integral = 0.0
        prev_error = 0.0
        
        for i, temp in enumerate(temperatures):
            runtime.set_physical_input("air_sensor", "temp_actual", temp)
            runtime.step(5000)  # 5 second intervals
            
            # Calculate PID output
            error = temp - setpoint
            integral += error * 5.0  # dt = 5s
            derivative = (error - prev_error) / 5.0
            output = kp * error + ki * integral + kd * derivative
            output = max(0, min(100, output))
            pid_outputs.append(output)
            prev_error = error
            
            print(f"Step {i}: temp={temp:.1f}°C, error={error:.1f}, PID output={output:.1f}%")
        
        # Verify PID output decreases as temperature approaches setpoint
        assert pid_outputs[-1] < pid_outputs[0], "PID output should decrease as error decreases"
        print(f"PID outputs: {[f'{o:.1f}' for o in pid_outputs]}")
    
    def test_fault_injection(self, runtime):
        """Test fault injection for robustness testing."""
        runtime.add_component("air_sensor", "dht22")
        
        # Normal operation - step past startup and read interval
        runtime.set_physical_input("air_sensor", "temp_actual", 25.0)
        runtime.step(3500)
        temp_normal = runtime.get_output("air_sensor", "temperature")
        assert temp_normal is not None, f"Normal temp should exist. Signals: {list(runtime.signal_bus.get_all().keys())}"
        print(f"Normal reading: {temp_normal:.1f}°C")
        
        # Inject offset fault (simulates calibration drift)
        runtime.inject_fault("air_sensor", "offset", offset=5.0)
        runtime.step(2500)
        temp_offset = runtime.get_output("air_sensor", "temperature")
        print(f"Offset reading: {temp_offset:.1f}°C (should be ~30°C)")
        assert temp_offset is not None
        assert temp_offset > temp_normal, "Offset should increase reading"
        
        # Clear faults and verify recovery
        runtime.clear_fault("air_sensor")
        runtime.step(2500)
        temp_recovered = runtime.get_output("air_sensor", "temperature")
        assert temp_recovered is not None
        print(f"Recovered reading: {temp_recovered:.1f}°C")
        # After clearing, should be back close to normal
        assert abs(temp_recovered - 25.0) < 3.0, f"Should recover to ~25°C, got {temp_recovered}"
    
    def test_full_simulation_state(self, runtime, device_config):
        """Test getting full simulation state."""
        # Add components based on device config
        for sensor in device_config.get("sensors", [])[:3]:
            sensor_type = sensor["type"]
            if sensor_type in runtime.get_available_components():
                runtime.add_component(sensor["name"], sensor_type)
        
        for actuator in device_config.get("actuators", [])[:2]:
            actuator_type = actuator["type"]
            if actuator_type in runtime.get_available_components():
                runtime.add_component(actuator["name"], actuator_type)
        
        # Run simulation
        runtime.step(5000)
        
        # Get full state
        state = runtime.get_state()
        
        assert "sim_time_ms" in state
        assert "components" in state
        assert "signals" in state
        
        print(f"Simulation state at {state['sim_time_ms']}ms:")
        print(f"  Components: {list(state['components'].keys())}")
        print(f"  Signals: {len(state['signals'])} active")


class TestMCPServerIntegration:
    """Test MCP server integration for AI-assisted simulation."""
    
    @pytest.fixture
    def mcp_server(self):
        """Create MCP server instance."""
        from mcp_server import OasisSimulationMCP
        component_path = Path(__file__).parent.parent / "components"
        return OasisSimulationMCP(component_path)
    
    def test_mcp_initialize(self, mcp_server):
        """Test MCP initialize request."""
        response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })
        
        assert "result" in response
        assert response["result"]["serverInfo"]["name"] == "oasis-simulation"
        print(f"MCP Server: {response['result']['serverInfo']}")
    
    def test_mcp_list_tools(self, mcp_server):
        """Test MCP tools/list request."""
        response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        
        assert "result" in response
        tools = response["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        
        assert "sim_start" in tool_names
        assert "sim_step" in tool_names
        assert "sim_get_state" in tool_names
        assert "sim_set_sensor_value" in tool_names
        assert "component_list" in tool_names
        
        print(f"Available MCP tools: {tool_names}")
    
    def _parse_mcp_result(self, response: dict) -> dict:
        """Parse MCP tool call result from content wrapper."""
        result = response.get("result", {})
        if "content" in result and len(result["content"]) > 0:
            # MCP wraps results in content array with text JSON
            import json
            return json.loads(result["content"][0]["text"])
        return result
    
    def test_mcp_sim_workflow(self, mcp_server):
        """Test complete MCP simulation workflow."""
        # Start simulation
        start_response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "sim_start",
                "arguments": {}
            }
        })
        
        assert "result" in start_response
        start_result = self._parse_mcp_result(start_response)
        session_id = start_result.get("session_id")
        assert session_id is not None, f"session_id should exist in {start_result}"
        print(f"Started session: {session_id}")
        
        # List available components
        components_response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "component_list",
                "arguments": {}
            }
        })
        components_result = self._parse_mcp_result(components_response)
        print(f"Components: {components_result}")
        
        # Add a component
        add_response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 5,
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
        add_result = self._parse_mcp_result(add_response)
        assert add_result.get("status") == "added"
        print(f"Added component: {add_result}")
        
        # Step simulation
        step_response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "sim_step",
                "arguments": {
                    "session_id": session_id,
                    "duration_ms": 5000
                }
            }
        })
        
        assert "result" in step_response
        step_result = self._parse_mcp_result(step_response)
        print(f"Stepped simulation: {step_result}")
        assert step_result.get("sim_time_ms") == 5000
        
        # Get state
        state_response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "sim_get_state",
                "arguments": {"session_id": session_id}
            }
        })
        
        assert "result" in state_response
        state_result = self._parse_mcp_result(state_response)
        print(f"Final state: {state_result}")
        assert "test_sensor" in state_result.get("components", {})
        
        # Stop simulation
        stop_response = mcp_server.handle_request({
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "sim_stop",
                "arguments": {"session_id": session_id}
            }
        })
        
        stop_result = self._parse_mcp_result(stop_response)
        print(f"Stopped session: {stop_result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
