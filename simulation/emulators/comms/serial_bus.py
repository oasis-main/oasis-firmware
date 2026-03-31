"""Serial/UART Bus - Virtual point-to-point and multi-drop serial communication.

Simulates UART connections between:
- MCU emulator (simavr/Renode/QEMU-ESP32) UART output
- Linux board emulator PTY/TCP UART
- Behavioral runtime signal bus

Modes:
- PTY pair: Two PTY file descriptors linked together (like a null-modem cable)
- TCP loopback: One side listens, other connects (for cross-process)
- In-process pipe: threading.Pipe for same-process simulation
"""

import os
import pty
import threading
import socket
import select
import queue
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class SerialEndpoint:
    """One end of a serial connection."""
    name: str
    baud_rate: int = 115200
    _rx_queue: queue.Queue = field(default_factory=queue.Queue)
    _tx_callbacks: list[Callable] = field(default_factory=list)

    def write(self, data: bytes):
        """Write data to this endpoint (injected into the bus)."""
        # Data written here flows to the other side's read
        pass  # Implemented by SerialBus

    def read(self, timeout: float = 0.1) -> Optional[bytes]:
        """Read data received on this endpoint."""
        try:
            return self._rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def read_text(self, timeout: float = 0.1) -> Optional[str]:
        """Read data as text."""
        data = self.read(timeout)
        return data.decode("utf-8", errors="replace") if data else None

    def on_rx(self, callback: Callable[[bytes], None]):
        """Register callback invoked when data arrives."""
        self._tx_callbacks.append(callback)


class SerialBus:
    """Virtual serial bus connecting two endpoints.

    Acts like a null-modem cable: data written to endpoint A
    appears at endpoint B and vice versa.
    """

    def __init__(self, name: str = "serial0", baud_rate: int = 115200):
        self.name = name
        self.baud_rate = baud_rate
        self._endpoints: dict[str, SerialEndpoint] = {}
        self._running = False
        self._lock = threading.Lock()

        # PTY pair for connecting to real processes
        self._pty_a_master: Optional[int] = None
        self._pty_a_slave: Optional[str] = None
        self._pty_b_master: Optional[int] = None
        self._pty_b_slave: Optional[str] = None
        self._pty_bridge_thread: Optional[threading.Thread] = None

    def create_endpoint(self, name: str) -> SerialEndpoint:
        """Create a named endpoint on this bus."""
        ep = SerialEndpoint(name=name, baud_rate=self.baud_rate)
        self._endpoints[name] = ep
        return ep

    def connect(self, ep_a_name: str, ep_b_name: str):
        """Connect two endpoints so data flows bidirectionally."""
        ep_a = self._endpoints.get(ep_a_name)
        ep_b = self._endpoints.get(ep_b_name)

        if not ep_a or not ep_b:
            raise ValueError(f"Endpoint not found: {ep_a_name} or {ep_b_name}")

        # Monkey-patch write to route to other side
        def write_a(data: bytes):
            ep_b._rx_queue.put(data)
            for cb in ep_b._tx_callbacks:
                cb(data)

        def write_b(data: bytes):
            ep_a._rx_queue.put(data)
            for cb in ep_a._tx_callbacks:
                cb(data)

        ep_a.write = write_a
        ep_b.write = write_b

    def create_pty_pair(self) -> tuple[str, str]:
        """Create a PTY pair for connecting real processes.

        Returns (pty_a_path, pty_b_path) - pass each path to a process
        as its serial port. Data written to A appears at B and vice versa.
        """
        # Create master/slave PTY pair A
        master_a, slave_a = pty.openpty()
        self._pty_a_master = master_a
        self._pty_a_slave = os.ttyname(slave_a)
        os.close(slave_a)

        # Create master/slave PTY pair B
        master_b, slave_b = pty.openpty()
        self._pty_b_master = master_b
        self._pty_b_slave = os.ttyname(slave_b)
        os.close(slave_b)

        # Start bridge thread
        self._running = True
        self._pty_bridge_thread = threading.Thread(
            target=self._bridge_pty_pair,
            daemon=True,
            name=f"serial-bridge-{self.name}"
        )
        self._pty_bridge_thread.start()

        return self._pty_a_slave, self._pty_b_slave

    def _bridge_pty_pair(self):
        """Bridge data between PTY master A and PTY master B."""
        while self._running:
            try:
                readable = []
                if self._pty_a_master is not None:
                    readable.append(self._pty_a_master)
                if self._pty_b_master is not None:
                    readable.append(self._pty_b_master)

                if not readable:
                    break

                r, _, _ = select.select(readable, [], [], 0.1)

                for fd in r:
                    try:
                        data = os.read(fd, 4096)
                        if data:
                            # Route to the other master
                            if fd == self._pty_a_master and self._pty_b_master:
                                os.write(self._pty_b_master, data)
                                # Also deliver to in-process endpoints
                                for name, ep in self._endpoints.items():
                                    if "b" in name.lower() or name.endswith("1"):
                                        ep._rx_queue.put(data)
                            elif fd == self._pty_b_master and self._pty_a_master:
                                os.write(self._pty_a_master, data)
                                for name, ep in self._endpoints.items():
                                    if "a" in name.lower() or name.endswith("0"):
                                        ep._rx_queue.put(data)
                    except OSError:
                        pass

            except (select.error, OSError):
                break

    def get_pty_paths(self) -> tuple[Optional[str], Optional[str]]:
        """Get the PTY slave paths for both sides."""
        return self._pty_a_slave, self._pty_b_slave

    def stop(self):
        """Stop the bus."""
        self._running = False
        for fd in [self._pty_a_master, self._pty_b_master]:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._pty_a_master = None
        self._pty_b_master = None

    def get_state(self) -> dict:
        """Get bus state."""
        return {
            "name": self.name,
            "baud_rate": self.baud_rate,
            "endpoints": list(self._endpoints.keys()),
            "pty_a": self._pty_a_slave,
            "pty_b": self._pty_b_slave,
            "running": self._running,
        }
