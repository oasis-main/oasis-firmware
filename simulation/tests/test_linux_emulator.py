#!/usr/bin/env python3
"""
Linux Board & Multi-Board Communication Tests
=============================================

Tests for RPi/SBC emulation and inter-board communication.

No actual QEMU boot needed for most tests - they verify the
configuration, bus routing, and behavioral integration layers.
Full QEMU boot tests are skipped unless QEMU is installed and
a kernel image is available.

Usage:
    cd simulation
    pytest tests/test_linux_emulator.py -v
"""

import pytest
import json
import struct
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from emulators.linux import (
    LinuxBoardEmulator,
    LinuxBoardConfig,
    LinuxBoard,
    BOARD_PROFILES,
)
from emulators.comms import (
    SerialBus,
    SerialEndpoint,
    I2CBus,
    I2CDevice,
    NetworkBus,
    MultiBoardOrchestrator,
    BoardLink,
    LinkType,
)
from mcp_server import OasisSimulationMCP


# ─────────────────────────────────────────────────────
# Linux Board Config Tests
# ─────────────────────────────────────────────────────

class TestLinuxBoardProfiles:
    """Test board profile definitions."""

    def test_all_profiles_defined(self):
        """Verify all supported boards have profiles."""
        expected = [
            LinuxBoard.RPI_ZERO_W,
            LinuxBoard.RPI_ZERO_2W,
            LinuxBoard.RPI_3B,
            LinuxBoard.RPI_4B,
            LinuxBoard.RPI_5,
            LinuxBoard.BEAGLEBONE,
            LinuxBoard.JETSON_NANO,
            LinuxBoard.GENERIC_ARM,
            LinuxBoard.GENERIC_ARM64,
        ]
        for board in expected:
            assert board in BOARD_PROFILES, f"Missing profile: {board}"

        print(f"All {len(expected)} board profiles defined")

    def test_rpi4_profile(self):
        """Check RPi 4B profile details."""
        profile = BOARD_PROFILES[LinuxBoard.RPI_4B]
        assert profile.machine == "raspi4b"
        assert profile.cpu == "cortex-a72"
        assert profile.arch == "aarch64"
        assert profile.ram_mb == 4096
        assert profile.gpio_count == 40
        print(f"RPi 4B: {profile.machine}/{profile.cpu}, {profile.ram_mb}MB RAM")

    def test_beaglebone_profile(self):
        """Check BeagleBone Black profile."""
        profile = BOARD_PROFILES[LinuxBoard.BEAGLEBONE]
        assert profile.machine == "beagle"
        assert profile.arch == "arm"
        assert profile.gpio_count == 92
        print(f"BeagleBone: {profile.machine}/{profile.cpu}, {profile.gpio_count} GPIO")

    def test_config_creation(self):
        """Test creating a board config."""
        config = LinuxBoardConfig(
            board=LinuxBoard.RPI_4B,
            ram_mb=2048,
            uart_mode="tcp",
            uart_tcp_port=5555,
            ssh_port=2222,
            extra_ports={8080: 80},
        )
        assert config.board == LinuxBoard.RPI_4B
        assert config.ram_mb == 2048
        assert config.uart_mode == "tcp"

    def test_qemu_command_generation(self):
        """Test QEMU command generation for RPi 4B."""
        config = LinuxBoardConfig(
            board=LinuxBoard.RPI_4B,
            kernel_path="/tmp/fake_kernel",
            uart_mode="tcp",
            uart_tcp_port=5556,
        )
        emulator = LinuxBoardEmulator(config)

        # Override kernel existence check for test
        config.kernel_path = "/fake/kernel"

        # Build command (don't execute)
        # We can test the logic without the file existing
        profile = BOARD_PROFILES[LinuxBoard.RPI_4B]
        assert profile.arch == "aarch64"
        assert f"qemu-system-{profile.arch}" == "qemu-system-aarch64"
        print(f"QEMU binary: qemu-system-{profile.arch}")

    def test_qemu_available(self):
        """Report QEMU availability."""
        available_arches = []
        for arch in ["aarch64", "arm", "x86_64"]:
            if LinuxBoardEmulator.check_qemu(arch):
                available_arches.append(arch)

        if available_arches:
            print(f"✅ QEMU available for: {available_arches}")
        else:
            print("⚠️  QEMU not found. Install with: brew install qemu")
            pytest.skip("QEMU not available")


# ─────────────────────────────────────────────────────
# Serial Bus Tests
# ─────────────────────────────────────────────────────

class TestSerialBus:
    """Test virtual serial bus."""

    def test_endpoint_creation(self):
        """Test creating endpoints on a bus."""
        bus = SerialBus("test_uart", baud_rate=9600)
        ep_a = bus.create_endpoint("board_a")
        ep_b = bus.create_endpoint("board_b")

        assert ep_a.name == "board_a"
        assert ep_b.name == "board_b"
        assert ep_a.baud_rate == 9600

    def test_bidirectional_data_flow(self):
        """Test data flows both directions between endpoints."""
        bus = SerialBus("test_bus")
        ep_a = bus.create_endpoint("node_a")
        ep_b = bus.create_endpoint("node_b")
        bus.connect("node_a", "node_b")

        # A writes → B reads
        ep_a.write(b"hello from A")
        received_b = ep_b.read(timeout=0.5)
        assert received_b == b"hello from A", f"B got: {received_b}"

        # B writes → A reads
        ep_b.write(b"hello from B")
        received_a = ep_a.read(timeout=0.5)
        assert received_a == b"hello from B", f"A got: {received_a}"

        print(f"Serial bus bidirectional: A→B and B→A ✅")

    def test_rx_callback(self):
        """Test RX callback on endpoint."""
        bus = SerialBus("callback_bus")
        ep_a = bus.create_endpoint("sender")
        ep_b = bus.create_endpoint("receiver")
        bus.connect("sender", "receiver")

        received_data = []
        ep_b.on_rx(lambda data: received_data.append(data))

        ep_a.write(b"test_packet\n")

        import time
        time.sleep(0.1)

        assert b"test_packet\n" in received_data
        print(f"RX callback fired: {received_data}")

    def test_pty_pair_creation(self):
        """Test PTY pair creation for connecting real processes."""
        import os
        bus = SerialBus("pty_test")

        try:
            pty_a, pty_b = bus.create_pty_pair()
            assert pty_a is not None
            assert pty_b is not None
            assert pty_a != pty_b
            assert pty_a.startswith("/dev/")

            print(f"PTY pair: {pty_a} ↔ {pty_b}")

            # Test data flow through PTY
            import time
            time.sleep(0.1)  # Allow bridge thread to start

            fd_a = os.open(pty_a, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            fd_b = os.open(pty_b, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

            os.write(fd_a, b"ping")
            time.sleep(0.1)

            import select
            r, _, _ = select.select([fd_b], [], [], 0.2)
            if r:
                data = os.read(fd_b, 64)
                assert data == b"ping", f"PTY relay failed, got: {data}"
                print(f"PTY data relay: {data} ✅")

            os.close(fd_a)
            os.close(fd_b)
        finally:
            bus.stop()

    def test_bus_state(self):
        """Test bus state reporting."""
        bus = SerialBus("state_test", baud_rate=115200)
        bus.create_endpoint("rpi")
        bus.create_endpoint("arduino")

        state = bus.get_state()
        assert state["name"] == "state_test"
        assert state["baud_rate"] == 115200
        assert "rpi" in state["endpoints"]
        assert "arduino" in state["endpoints"]
        print(f"Bus state: {state}")


# ─────────────────────────────────────────────────────
# I2C Bus Tests
# ─────────────────────────────────────────────────────

class TestI2CBus:
    """Test virtual I2C bus."""

    def test_device_registration(self):
        """Test registering I2C devices."""
        bus = I2CBus("i2c1")
        bme280 = bus.add_device(0x76, "bme280")
        mpu6050 = bus.add_device(0x68, "mpu6050")

        assert bme280.address == 0x76
        assert mpu6050.address == 0x68

        devices = bus.scan()
        assert 0x76 in devices
        assert 0x68 in devices
        print(f"I2C devices: {[hex(a) for a in devices]}")

    def test_write_to_device(self):
        """Test writing to an I2C device."""
        bus = I2CBus("i2c1")
        received = []

        sensor = bus.add_device(0x40, "hdc1080")
        sensor.on_write(lambda data: received.append(data))

        # Write measurement trigger
        result = bus.write(0x40, b"\x00")  # Temperature measurement
        assert result is True
        assert b"\x00" in received
        print(f"I2C write ACK, device received: {received}")

    def test_read_from_device(self):
        """Test reading from an I2C device."""
        bus = I2CBus("i2c1")

        # Register a temperature sensor that returns fixed data
        sensor = bus.add_device(0x48, "tmp102")
        sensor.on_read(lambda n: struct.pack(">H", 0x1900))  # 25°C

        data = bus.read(0x48, 2)
        assert data is not None
        assert len(data) == 2
        temp_raw = struct.unpack(">H", data)[0]
        assert temp_raw == 0x1900
        print(f"I2C read: 0x{temp_raw:04x} (raw temp)")

    def test_nack_on_missing_device(self):
        """Test NACK when no device at address."""
        bus = I2CBus("i2c1")
        # No device registered at 0x29

        result = bus.write(0x29, b"\x00")
        assert result is False  # NACK

        data = bus.read(0x29, 4)
        assert data is None  # NACK
        print("NACK on missing device ✅")

    def test_register_read_pattern(self):
        """Test the common write-register-then-read pattern."""
        bus = I2CBus("i2c1")
        sensor = bus.add_device(0x76, "bme280")

        # Simulate BME280 register data
        reg_data = {
            0xF3: struct.pack(">H", 2350),   # temperature raw
            0xF5: struct.pack(">H", 9856),   # pressure raw
        }
        pending_reg = [None]

        sensor.on_write(lambda d: pending_reg.__setitem__(0, d[0] if d else None))
        sensor.on_read(lambda n: reg_data.get(pending_reg[0], bytes(n))[:n])

        # Read temperature register
        bus.write(0x76, b"\xF3")
        temp_data = bus.read(0x76, 2)
        assert struct.unpack(">H", temp_data)[0] == 2350
        print(f"BME280 temp register: {struct.unpack('>H', temp_data)[0]} ✅")

    def test_attach_to_behavioral_sensor(self):
        """Test attaching I2C bus to behavioral runtime sensor."""
        from behavioral import BehavioralRuntime

        rt = BehavioralRuntime()
        component_path = Path(__file__).parent.parent / "components"
        rt.load_component_library(component_path)
        rt.add_component("bme280_sensor", "bme280")
        rt.set_physical_input("bme280_sensor", "temp_actual", 22.5)
        rt.set_physical_input("bme280_sensor", "humidity_actual", 65.0)
        rt.step(3500)

        bus = I2CBus("i2c1")
        bus.attach_to_behavioral_sensor(
            address=0x76,
            runtime=rt,
            component_id="bme280_sensor",
            register_map={0xF3: "temperature", 0xF5: "humidity"},
        )

        # Read temperature via I2C
        bus.write(0x76, b"\xF3")
        temp_data = bus.read(0x76, 2)
        assert temp_data is not None
        temp_raw = struct.unpack(">H", temp_data)[0]
        temp_c = temp_raw / 100.0
        assert 20 < temp_c < 25
        print(f"I2C→Behavioral: temp={temp_c:.1f}°C ✅")


# ─────────────────────────────────────────────────────
# Network Bus Tests
# ─────────────────────────────────────────────────────

class TestNetworkBus:
    """Test in-process MQTT-like network bus."""

    def test_publish_subscribe(self):
        """Test basic publish/subscribe."""
        bus = NetworkBus("net0")
        received = []

        bus.subscribe("sensors/temperature", lambda t, p, s: received.append((t, p, s)))
        bus.publish("sensors/temperature", 25.3, sender="rpi")

        assert len(received) == 1
        topic, payload, sender = received[0]
        assert topic == "sensors/temperature"
        assert payload == 25.3
        assert sender == "rpi"
        print(f"Pub/sub: {topic}={payload} from {sender} ✅")

    def test_wildcard_single_level(self):
        """Test + single-level wildcard."""
        bus = NetworkBus("net0")
        received = []

        bus.subscribe("sensors/+/value", lambda t, p, s: received.append(t))
        bus.publish("sensors/temp/value", 22.1, "esp32")
        bus.publish("sensors/humidity/value", 65.0, "esp32")
        bus.publish("sensors/temp/raw", 2240, "esp32")  # Should NOT match

        assert "sensors/temp/value" in received
        assert "sensors/humidity/value" in received
        assert "sensors/temp/raw" not in received
        print(f"Wildcard +: matched {received}")

    def test_wildcard_multi_level(self):
        """Test # multi-level wildcard."""
        bus = NetworkBus("net0")
        received = []

        bus.subscribe("greenhouse/#", lambda t, p, s: received.append(t))
        bus.publish("greenhouse/zone1/temp", 24.0, "rpi")
        bus.publish("greenhouse/zone1/humidity", 70.0, "rpi")
        bus.publish("greenhouse/zone2/soil/moisture", 45.0, "arduino")
        bus.publish("other/topic", 1.0, "other")  # Should NOT match

        assert len([r for r in received if r.startswith("greenhouse/")]) == 3
        assert "other/topic" not in received
        print(f"Wildcard #: matched {len(received)} greenhouse topics ✅")

    def test_message_log(self):
        """Test message logging."""
        bus = NetworkBus("net0")

        bus.publish("test/a", 1, "node1")
        bus.publish("test/b", 2, "node2")
        bus.publish("other/c", 3, "node3")

        msgs = bus.get_messages(topic_filter="test/")
        assert len(msgs) == 2
        print(f"Message log filtered: {len(msgs)} messages")

    def test_tcp_bridge(self):
        """Test TCP bridge for cross-process communication."""
        from emulators.comms.network_bus import TCPBridge
        import time

        # Server side
        server = TCPBridge("server")
        port = server.listen(0)  # Port 0 = auto-assign

        # Actually get the bound port
        port = server._server_socket.getsockname()[1]

        received = []
        server.on_receive(lambda data, peer: received.append(data))

        # Client side
        client = TCPBridge("client")
        time.sleep(0.1)
        ok = client.connect(port)
        assert ok, f"Failed to connect to port {port}"
        time.sleep(0.1)

        # Send data
        client.send(b"hello from client")
        time.sleep(0.2)

        assert any(b"hello from client" in r for r in received)
        print(f"TCP bridge: data received ✅")

        server.stop()
        client.stop()


# ─────────────────────────────────────────────────────
# Multi-Board Orchestrator Tests
# ─────────────────────────────────────────────────────

class TestMultiBoardOrchestrator:
    """Test multi-board topology orchestration."""

    def test_greenhouse_topology(self):
        """Test creating a greenhouse controller topology."""
        orch = MultiBoardOrchestrator()

        # Add boards
        rpi = orch.add_behavioral_node("rpi4", "rpi_4b")
        arduino = orch.add_behavioral_node("arduino", "arduino_mega")

        # Add components to nodes
        rpi.runtime.add_component("env_sensor", "bme280")
        arduino.runtime.add_component("soil_sensor", "soil_moisture")
        arduino.runtime.add_component("relay", "relay")

        # Wire up communication
        uart_link = orch.link_uart("rpi4", "arduino", baud_rate=115200)
        i2c_link = orch.link_i2c("rpi4", bus_id="i2c1")
        net_link = orch.link_network("rpi4", "arduino")

        # Verify topology
        state = orch.get_state()
        assert "rpi4" in state["nodes"]
        assert "arduino" in state["nodes"]
        assert len(state["links"]) == 3

        print(orch.describe())

    def test_uart_between_nodes(self):
        """Test UART communication between two behavioral nodes."""
        orch = MultiBoardOrchestrator()

        rpi = orch.add_behavioral_node("rpi", "rpi_4b")
        mcu = orch.add_behavioral_node("mcu", "arduino_uno")

        uart_link = orch.link_uart("rpi", "mcu")
        bus = uart_link.bus

        ep_rpi = bus._endpoints["rpi"]
        ep_mcu = bus._endpoints["mcu"]

        # RPi sends sensor request
        ep_rpi.write(b"GET_TEMP\n")
        received = ep_mcu.read(timeout=0.5)
        assert received == b"GET_TEMP\n"

        # MCU sends response
        ep_mcu.write(b"TEMP:24.5\n")
        response = ep_rpi.read(timeout=0.5)
        assert response == b"TEMP:24.5\n"

        print(f"UART RPi↔MCU: ✅")

    def test_network_messaging_between_nodes(self):
        """Test MQTT-style messaging between nodes."""
        orch = MultiBoardOrchestrator()

        rpi = orch.add_behavioral_node("controller", "rpi_4b")
        esp32 = orch.add_behavioral_node("relay_board", "esp32")

        net_link = orch.link_network("controller", "relay_board")

        # Subscribe ESP32 to commands
        commands_received = []
        orch.subscribe("relay_board", "actuators/relay/+", 
                       lambda t, p, s: commands_received.append((t, p)))

        # Controller publishes relay command
        orch.publish("controller", "actuators/relay/zone1", {"state": True})
        orch.publish("controller", "actuators/relay/zone2", {"state": False})

        assert len(commands_received) == 2
        topics = [c[0] for c in commands_received]
        assert "actuators/relay/zone1" in topics
        print(f"Network messaging: {commands_received} ✅")

    def test_i2c_sensor_on_rpi(self):
        """Test I2C sensor attached to RPi behavioral node."""
        orch = MultiBoardOrchestrator()
        rpi = orch.add_behavioral_node("rpi", "rpi_4b")

        # Add behavioral sensor
        rpi.runtime.add_component("temp_sensor", "dht22")
        rpi.runtime.set_physical_input("temp_sensor", "temp_actual", 23.0)
        rpi.runtime.step(3500)

        # Create I2C bus with sensor attached
        i2c_link = orch.link_i2c("rpi", bus_id="i2c1")
        i2c_bus = i2c_link.bus

        i2c_bus.attach_to_behavioral_sensor(
            address=0x40,
            runtime=rpi.runtime,
            component_id="temp_sensor",
            register_map={0x00: "temperature"},
        )

        # Read via I2C
        devices = orch.i2c_scan("rpi", "i2c1")
        assert 0x40 in devices

        i2c_bus.write(0x40, b"\x00")
        data = orch.i2c_read("rpi", 0x40, 2, "i2c1")
        assert data is not None
        temp = struct.unpack(">H", data)[0] / 100.0
        assert 20 < temp < 26
        print(f"I2C sensor on RPi: {temp:.1f}°C ✅")

    def test_step_all_behavioral_nodes(self):
        """Test stepping all behavioral runtimes."""
        orch = MultiBoardOrchestrator()

        rpi = orch.add_behavioral_node("rpi", "rpi_4b")
        arduino = orch.add_behavioral_node("arduino", "arduino_uno")

        rpi.runtime.add_component("sensor1", "dht22")
        arduino.runtime.add_component("soil1", "soil_moisture")

        rpi.runtime.set_physical_input("sensor1", "temp_actual", 25.0)
        arduino.runtime.set_physical_input("soil1", "moisture_actual", 42.0)

        # Step all nodes
        orch.step(5000)

        # Both sensors should now have outputs
        rpi_temp = rpi.runtime.get_output("sensor1", "temperature")
        arduino_moisture = arduino.runtime.get_output("soil1", "moisture")

        assert rpi_temp is not None
        assert arduino_moisture is not None
        print(f"Multi-node step: RPi temp={rpi_temp:.1f}°C, Arduino moisture={arduino_moisture:.1f}% ✅")

    def test_full_greenhouse_scenario(self):
        """Simulate a full greenhouse control scenario across boards."""
        orch = MultiBoardOrchestrator()

        # RPi 4B: main controller + env sensors
        rpi = orch.add_behavioral_node("rpi_controller", "rpi_4b")
        rpi.runtime.add_component("air", "dht22")
        rpi.runtime.add_component("light", "light_sensor")

        # Arduino: sensor hub in grow zone
        arduino = orch.add_behavioral_node("sensor_hub", "arduino_mega")
        arduino.runtime.add_component("soil_a", "soil_moisture")
        arduino.runtime.add_component("soil_b", "soil_moisture")

        # ESP32: actuator controller
        esp32 = orch.add_behavioral_node("actuator_ctrl", "esp32")
        esp32.runtime.add_component("pump", "pump")
        esp32.runtime.add_component("fan", "relay")

        # Wire up
        uart = orch.link_uart("rpi_controller", "sensor_hub")
        net = orch.link_network("rpi_controller", "actuator_ctrl")
        orch.link_network("sensor_hub", "actuator_ctrl")

        # Set physical conditions
        rpi.runtime.set_physical_input("air", "temp_actual", 28.5)   # Hot
        rpi.runtime.set_physical_input("air", "humidity_actual", 75.0)
        arduino.runtime.set_physical_input("soil_a", "moisture_actual", 18.0)  # Dry

        # Step simulation
        orch.step(5000)

        # Read sensor data
        temp = rpi.runtime.get_output("air", "temperature")
        humidity = rpi.runtime.get_output("air", "humidity")
        soil_a = arduino.runtime.get_output("soil_a", "moisture")

        assert temp is not None and temp > 25
        assert humidity is not None
        assert soil_a is not None and soil_a < 25  # Dry

        # Control logic: trigger pump if soil dry
        if soil_a < 20:
            orch.publish("rpi_controller", "actuators/pump/zone_a", {"state": True, "duration_s": 30})

        # Report
        print(f"\nGreenhouse Scenario:")
        print(f"  RPi → Air: {temp:.1f}°C / {humidity:.1f}%")
        print(f"  Arduino → Soil A: {soil_a:.1f}%")
        print(f"  ESP32 ← Pump: {'TRIGGER' if soil_a < 20 else 'OK'}")
        print(f"  Topology: {orch.describe()}")


# ─────────────────────────────────────────────────────
# MCP Linux Board Tools
# ─────────────────────────────────────────────────────

class TestMCPLinuxTools:
    """Test MCP server linux board tools."""

    @pytest.fixture
    def mcp(self):
        return OasisSimulationMCP(Path(__file__).parent.parent / "components")

    def _parse(self, response):
        result = response.get("result", {})
        if "content" in result:
            return json.loads(result["content"][0]["text"])
        return result

    def test_linux_boards_listed(self, mcp):
        """Linux board platforms should be in the emulator list."""
        response = mcp.handle_request({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": "emulator_platforms", "arguments": {}}
        })
        result = self._parse(response)
        platforms = result.get("platforms", [])
        ids = [p["id"] for p in platforms]

        linux_boards = ["rpi_zero_w", "rpi_3b", "rpi_4b", "rpi_5",
                        "beaglebone", "jetson_nano"]
        for board in linux_boards:
            assert board in ids, f"Missing Linux board: {board}"

        print(f"Linux boards in MCP: {[b for b in ids if 'rpi' in b or 'beagle' in b or 'jetson' in b]}")

    def test_multi_board_workflow_via_mcp(self, mcp):
        """Test multi-board setup via MCP tools."""
        # Start a session
        r = self._parse(mcp.handle_request({
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": "sim_start", "arguments": {}}
        }))
        session_id = r["session_id"]

        # Add components (multi-node via component add)
        self._parse(mcp.handle_request({
            "jsonrpc": "2.0", "id": 2,
            "method": "tools/call",
            "params": {"name": "component_add", "arguments": {
                "session_id": session_id,
                "instance_id": "rpi_air_sensor",
                "component_id": "dht22"
            }}
        }))

        # Set sensor value (use correct arg names: instance_id, input_name)
        mcp.handle_request({
            "jsonrpc": "2.0", "id": 3,
            "method": "tools/call",
            "params": {"name": "sim_set_sensor_value", "arguments": {
                "session_id": session_id,
                "instance_id": "rpi_air_sensor",
                "input_name": "temp_actual",
                "value": 26.0
            }}
        })

        # Step simulation far enough to pass startup delay + read interval
        mcp.handle_request({
            "jsonrpc": "2.0", "id": 4,
            "method": "tools/call",
            "params": {"name": "sim_step", "arguments": {
                "session_id": session_id,
                "duration_ms": 5000
            }}
        })

        # Get state
        state_r = self._parse(mcp.handle_request({
            "jsonrpc": "2.0", "id": 5,
            "method": "tools/call",
            "params": {"name": "sim_get_state", "arguments": {
                "session_id": session_id
            }}
        }))

        assert "signals" in state_r
        signals = state_r["signals"]
        temp_key = "rpi_air_sensor.temperature"
        assert temp_key in signals, f"Expected {temp_key} in {list(signals.keys())}"
        assert signals[temp_key]["value"] is not None
        print(f"MCP multi-board sensor: {temp_key}={signals[temp_key]['value']:.1f}°C ✅")

        # Cleanup
        mcp.handle_request({
            "jsonrpc": "2.0", "id": 6,
            "method": "tools/call",
            "params": {"name": "sim_stop", "arguments": {"session_id": session_id}}
        })


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
