"""Multi-Board Orchestrator - Manage multiple emulated boards communicating.

Supports topologies like:
  RPi 4 (Linux) ←UART→ Arduino Mega (MCU)
  RPi 4 (Linux) ←I2C→ [BME280, MPU6050]  (behavioral sensors)
  RPi 4 ←MQTT→ ESP32 ←Serial→ Arduino

Each board is a 'node', connections between boards are 'links'.
The behavioral runtime provides virtual component models for sensors
and actuators that don't need full firmware.
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class LinkType(Enum):
    """Inter-board communication protocols."""
    UART    = "uart"     # Serial UART (point-to-point)
    I2C     = "i2c"      # I2C bus (multi-device)
    SPI     = "spi"      # SPI bus
    NETWORK = "network"  # TCP/MQTT (Ethernet/WiFi)
    GPIO    = "gpio"     # Direct GPIO pin connection


@dataclass
class BoardNode:
    """A board in the multi-board simulation."""
    node_id: str
    board_type: str        # "rpi_4b", "arduino_uno", "esp32", "behavioral", etc.
    emulator: Any = None   # LinuxBoardEmulator, EmulatorOrchestrator, or None
    runtime: Any = None    # BehavioralRuntime if behavioral-only
    metadata: dict = field(default_factory=dict)

    @property
    def is_running(self) -> bool:
        if self.emulator:
            return getattr(self.emulator, "running", False)
        return self.runtime is not None


@dataclass
class BoardLink:
    """A communication link between two board nodes."""
    link_id: str
    node_a: str
    node_b: str
    link_type: LinkType
    bus: Any = None        # SerialBus, I2CBus, NetworkBus, etc.
    config: dict = field(default_factory=dict)

    @property
    def description(self) -> str:
        return f"{self.node_a} ←{self.link_type.value.upper()}→ {self.node_b}"


class MultiBoardOrchestrator:
    """Orchestrate multiple emulated boards with inter-board communication.

    Example topology (Oasis greenhouse controller):
        RPi 4 (main controller, Linux)
          ├── UART → Arduino Mega (sensor hub)
          │          ├── Behavioral: DHT22 (temp/humidity)
          │          ├── Behavioral: Soil moisture
          │          └── Behavioral: Light sensor
          ├── I2C  → Behavioral: BME280 (air quality)
          └── MQTT → ESP32 (WiFi relay controller)
                     └── Behavioral: Relay bank
    """

    def __init__(self):
        self._nodes: dict[str, BoardNode] = {}
        self._links: dict[str, BoardLink] = {}
        self._message_log: list[dict] = []
        self._running = False
        self._step_callbacks: list[Callable] = []
        self._lock = threading.Lock()

        # Lazy imports to avoid circular dependency
        self._serial_bus_cls = None
        self._i2c_bus_cls = None
        self._network_bus_cls = None

    def _get_serial_bus_cls(self):
        if not self._serial_bus_cls:
            from .serial_bus import SerialBus
            self._serial_bus_cls = SerialBus
        return self._serial_bus_cls

    def _get_i2c_bus_cls(self):
        if not self._i2c_bus_cls:
            from .i2c_bus import I2CBus
            self._i2c_bus_cls = I2CBus
        return self._i2c_bus_cls

    def _get_network_bus_cls(self):
        if not self._network_bus_cls:
            from .network_bus import NetworkBus
            self._network_bus_cls = NetworkBus
        return self._network_bus_cls

    def add_node(self, node_id: str, board_type: str,
                 emulator=None, runtime=None, **metadata) -> BoardNode:
        """Add a board node to the simulation."""
        node = BoardNode(
            node_id=node_id,
            board_type=board_type,
            emulator=emulator,
            runtime=runtime,
            metadata=metadata,
        )
        self._nodes[node_id] = node
        return node

    def add_behavioral_node(self, node_id: str, board_type: str,
                             component_library_path: Optional[str] = None) -> BoardNode:
        """Add a behavioral-only node (no actual firmware emulation).
        Useful for modeling a board at the sensor/actuator abstraction level.
        """
        from behavioral import BehavioralRuntime

        runtime = BehavioralRuntime()
        if component_library_path:
            runtime.load_component_library(Path(component_library_path))
        else:
            # Auto-discover
            default_path = Path(__file__).parent.parent.parent / "components"
            if default_path.exists():
                runtime.load_component_library(default_path)

        return self.add_node(node_id, board_type, runtime=runtime)

    def link_uart(self, node_a_id: str, node_b_id: str,
                  baud_rate: int = 115200, link_id: Optional[str] = None) -> BoardLink:
        """Create a UART link between two nodes."""
        SerialBus = self._get_serial_bus_cls()
        link_id = link_id or f"{node_a_id}_uart_{node_b_id}"

        bus = SerialBus(name=link_id, baud_rate=baud_rate)
        ep_a = bus.create_endpoint(node_a_id)
        ep_b = bus.create_endpoint(node_b_id)
        bus.connect(node_a_id, node_b_id)

        # Attach to emulators if running
        node_a = self._nodes.get(node_a_id)
        node_b = self._nodes.get(node_b_id)

        if node_a and node_a.emulator and hasattr(node_a.emulator, "on_uart_rx"):
            node_a.emulator.on_uart_rx(lambda data: ep_b.write(
                data.encode() if isinstance(data, str) else data
            ))

        if node_b and node_b.emulator and hasattr(node_b.emulator, "on_uart_rx"):
            node_b.emulator.on_uart_rx(lambda data: ep_a.write(
                data.encode() if isinstance(data, str) else data
            ))

        link = BoardLink(
            link_id=link_id,
            node_a=node_a_id,
            node_b=node_b_id,
            link_type=LinkType.UART,
            bus=bus,
            config={"baud_rate": baud_rate},
        )
        self._links[link_id] = link
        return link

    def link_i2c(self, master_node_id: str, bus_id: str = "i2c1",
                 link_id: Optional[str] = None) -> BoardLink:
        """Create an I2C bus attached to a master node."""
        I2CBus = self._get_i2c_bus_cls()
        link_id = link_id or f"{master_node_id}_i2c_{bus_id}"

        bus = I2CBus(bus_id=bus_id)

        link = BoardLink(
            link_id=link_id,
            node_a=master_node_id,
            node_b="i2c_bus",
            link_type=LinkType.I2C,
            bus=bus,
            config={"bus_id": bus_id},
        )
        self._links[link_id] = link
        return link

    def link_network(self, node_a_id: str, node_b_id: str,
                     link_id: Optional[str] = None) -> BoardLink:
        """Create a network (MQTT-style) link between nodes."""
        NetworkBus = self._get_network_bus_cls()
        link_id = link_id or f"{node_a_id}_net_{node_b_id}"

        bus = NetworkBus(name=link_id)

        link = BoardLink(
            link_id=link_id,
            node_a=node_a_id,
            node_b=node_b_id,
            link_type=LinkType.NETWORK,
            bus=bus,
        )
        self._links[link_id] = link
        return link

    def get_link(self, link_id: str) -> Optional[BoardLink]:
        """Get a link by ID."""
        return self._links.get(link_id)

    def get_node(self, node_id: str) -> Optional[BoardNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def start_all(self) -> dict[str, bool]:
        """Start all board emulators."""
        results = {}
        for node_id, node in self._nodes.items():
            if node.emulator:
                try:
                    ok = node.emulator.start()
                    results[node_id] = ok
                except Exception as e:
                    results[node_id] = False
                    print(f"Failed to start {node_id}: {e}")
            else:
                results[node_id] = True  # Behavioral nodes are always "started"

        self._running = True
        return results

    def stop_all(self):
        """Stop all board emulators."""
        self._running = False
        for node in self._nodes.values():
            if node.emulator:
                try:
                    node.emulator.stop()
                except Exception:
                    pass
        for link in self._links.values():
            if link.bus and hasattr(link.bus, "stop"):
                try:
                    link.bus.stop()
                except Exception:
                    pass

    def step(self, delta_ms: int = 100):
        """Step all behavioral runtimes forward by delta_ms.

        Linux board emulators run asynchronously (they have real QEMU
        processes), so only behavioral nodes are stepped here.
        """
        for node in self._nodes.values():
            if node.runtime:
                node.runtime.step(delta_ms)

        for cb in self._step_callbacks:
            cb(delta_ms)

    def on_step(self, callback: Callable[[int], None]):
        """Register callback called on each step."""
        self._step_callbacks.append(callback)

    def send_uart(self, from_node: str, to_node: str, data: str):
        """Send UART data from one node to another."""
        # Find the UART link between these nodes
        for link in self._links.values():
            if link.link_type == LinkType.UART:
                if (link.node_a == from_node and link.node_b == to_node) or \
                   (link.node_b == from_node and link.node_a == to_node):
                    # Route via endpoint
                    bus = link.bus
                    sender_ep = bus._endpoints.get(from_node)
                    if sender_ep:
                        sender_ep.write(data.encode() if isinstance(data, str) else data)
                    return True
        return False

    def publish(self, from_node: str, topic: str, payload: Any):
        """Publish on the network bus from a node."""
        for link in self._links.values():
            if link.link_type == LinkType.NETWORK:
                if link.node_a == from_node or link.node_b == from_node:
                    link.bus.publish(topic, payload, sender=from_node)

    def subscribe(self, node_id: str, topic_pattern: str,
                  callback: Callable[[str, Any, str], None]):
        """Subscribe a node to a network bus topic."""
        for link in self._links.values():
            if link.link_type == LinkType.NETWORK:
                if link.node_a == node_id or link.node_b == node_id:
                    link.bus.subscribe(topic_pattern, callback)

    def i2c_write(self, master_node_id: str, address: int, data: bytes,
                  bus_id: str = "i2c1") -> bool:
        """Perform an I2C write from a master node."""
        for link in self._links.values():
            if link.link_type == LinkType.I2C and link.node_a == master_node_id:
                if link.config.get("bus_id") == bus_id:
                    return link.bus.write(address, data)
        return False

    def i2c_read(self, master_node_id: str, address: int, length: int,
                 bus_id: str = "i2c1") -> Optional[bytes]:
        """Perform an I2C read from a master node."""
        for link in self._links.values():
            if link.link_type == LinkType.I2C and link.node_a == master_node_id:
                if link.config.get("bus_id") == bus_id:
                    return link.bus.read(address, length)
        return None

    def i2c_scan(self, master_node_id: str, bus_id: str = "i2c1") -> list[int]:
        """Scan I2C bus from a master node."""
        for link in self._links.values():
            if link.link_type == LinkType.I2C and link.node_a == master_node_id:
                if link.config.get("bus_id") == bus_id:
                    return link.bus.scan()
        return []

    def get_state(self) -> dict:
        """Get full orchestrator state."""
        return {
            "running": self._running,
            "nodes": {
                node_id: {
                    "board_type": node.board_type,
                    "is_running": node.is_running,
                    "has_emulator": node.emulator is not None,
                    "has_runtime": node.runtime is not None,
                }
                for node_id, node in self._nodes.items()
            },
            "links": {
                link_id: {
                    "type": link.link_type.value,
                    "a": link.node_a,
                    "b": link.node_b,
                    "description": link.description,
                }
                for link_id, link in self._links.items()
            },
        }

    def describe(self) -> str:
        """Human-readable topology description."""
        lines = ["Multi-Board Topology:"]
        lines.append(f"  Nodes ({len(self._nodes)}):")
        for nid, node in self._nodes.items():
            mode = "behavioral" if not node.emulator else "emulated"
            lines.append(f"    [{mode}] {nid} ({node.board_type})")
        lines.append(f"  Links ({len(self._links)}):")
        for link in self._links.values():
            lines.append(f"    {link.description}")
        return "\n".join(lines)
