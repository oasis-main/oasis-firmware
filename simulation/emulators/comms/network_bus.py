"""Network Bus - TCP/MQTT-based inter-board communication.

Simulates network communication between emulated boards:
- TCP sockets (raw, for direct board-to-board data)
- MQTT broker (mosquitto in-process or external)
- HTTP endpoints (REST-style inter-board calls)

This is the primary communication channel for RPi ↔ MCU ↔ RPi
scenarios where boards share data over Ethernet/WiFi.
"""

import socket
import threading
import json
import queue
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class NetworkMessage:
    """A message on the network bus."""
    topic: str
    payload: Any
    sender: str
    timestamp_ms: float = field(default_factory=lambda: time.time() * 1000)


class TCPBridge:
    """Direct TCP socket bridge between two processes/boards.

    One side acts as server, the other connects as client.
    Useful for direct board-to-board byte streams.
    """

    def __init__(self, name: str = "tcp_bridge"):
        self.name = name
        self._server_socket: Optional[socket.socket] = None
        self._client_socket: Optional[socket.socket] = None
        self._connections: list[socket.socket] = []
        self._rx_queue: queue.Queue = queue.Queue()
        self._callbacks: list[Callable[[bytes, str], None]] = []
        self._running = False
        self._port: Optional[int] = None

    def listen(self, port: int, host: str = "127.0.0.1"):
        """Start listening (server side)."""
        self._port = port
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((host, port))
        self._server_socket.listen(5)
        self._running = True

        threading.Thread(target=self._accept_loop, daemon=True).start()
        return port

    def connect(self, port: int, host: str = "127.0.0.1") -> bool:
        """Connect to a server (client side)."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            self._client_socket = sock
            self._connections.append(sock)
            self._running = True
            threading.Thread(target=self._read_loop, args=(sock, f"{host}:{port}"),
                             daemon=True).start()
            return True
        except ConnectionRefusedError:
            return False

    def _accept_loop(self):
        """Accept incoming connections."""
        while self._running and self._server_socket:
            try:
                self._server_socket.settimeout(1.0)
                conn, addr = self._server_socket.accept()
                self._connections.append(conn)
                threading.Thread(target=self._read_loop,
                                 args=(conn, f"{addr[0]}:{addr[1]}"),
                                 daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _read_loop(self, sock: socket.socket, peer: str):
        """Read from a connection."""
        while self._running:
            try:
                sock.settimeout(0.1)
                data = sock.recv(4096)
                if not data:
                    break
                self._rx_queue.put((data, peer))
                for cb in self._callbacks:
                    cb(data, peer)
            except socket.timeout:
                continue
            except OSError:
                break

    def send(self, data: bytes):
        """Broadcast to all connected peers."""
        dead = []
        for conn in self._connections:
            try:
                conn.send(data)
            except OSError:
                dead.append(conn)
        for conn in dead:
            self._connections.remove(conn)

    def recv(self, timeout: float = 0.1) -> Optional[tuple[bytes, str]]:
        """Receive data. Returns (data, peer_addr) or None."""
        try:
            return self._rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def on_receive(self, callback: Callable[[bytes, str], None]):
        """Register callback for received data."""
        self._callbacks.append(callback)

    def stop(self):
        """Stop the bridge."""
        self._running = False
        for conn in self._connections:
            try:
                conn.close()
            except OSError:
                pass
        if self._server_socket:
            self._server_socket.close()

    @property
    def port(self) -> Optional[int]:
        return self._port


class NetworkBus:
    """In-process MQTT-like publish/subscribe message bus.

    Provides topic-based routing between board emulators without
    requiring an actual MQTT broker. For tests with a real broker,
    use MQTTBridge instead.

    Topic syntax: device/sensor/reading  (supports wildcards: +, #)
    """

    def __init__(self, name: str = "network"):
        self.name = name
        self._subscriptions: dict[str, list[Callable]] = {}  # topic -> callbacks
        self._message_log: list[NetworkMessage] = []
        self._lock = threading.Lock()

    def publish(self, topic: str, payload: Any, sender: str = "unknown"):
        """Publish a message on a topic."""
        msg = NetworkMessage(topic=topic, payload=payload, sender=sender)

        with self._lock:
            self._message_log.append(msg)
            matched = self._route(topic)
            for callback in matched:
                try:
                    callback(topic, payload, sender)
                except Exception as e:
                    print(f"NetworkBus callback error on {topic}: {e}")

    def subscribe(self, topic_pattern: str, callback: Callable[[str, Any, str], None]):
        """Subscribe to a topic pattern.

        Supports:
          +  single-level wildcard  (e.g., "sensors/+/temperature")
          #  multi-level wildcard   (e.g., "greenhouse/#")
        """
        with self._lock:
            if topic_pattern not in self._subscriptions:
                self._subscriptions[topic_pattern] = []
            self._subscriptions[topic_pattern].append(callback)

    def unsubscribe(self, topic_pattern: str, callback: Optional[Callable] = None):
        """Unsubscribe from a topic."""
        with self._lock:
            if topic_pattern in self._subscriptions:
                if callback:
                    self._subscriptions[topic_pattern].remove(callback)
                else:
                    del self._subscriptions[topic_pattern]

    def _route(self, topic: str) -> list[Callable]:
        """Find all callbacks matching a published topic."""
        matched = []
        topic_parts = topic.split("/")

        for pattern, callbacks in self._subscriptions.items():
            if self._topic_matches(pattern, topic_parts):
                matched.extend(callbacks)

        return matched

    def _topic_matches(self, pattern: str, topic_parts: list[str]) -> bool:
        """Check if a topic matches a subscription pattern."""
        pattern_parts = pattern.split("/")

        for i, part in enumerate(pattern_parts):
            if part == "#":
                return True  # Match rest of topic
            if i >= len(topic_parts):
                return False
            if part != "+" and part != topic_parts[i]:
                return False

        return len(pattern_parts) == len(topic_parts)

    def get_messages(self, topic_filter: Optional[str] = None,
                     limit: int = 100) -> list[NetworkMessage]:
        """Get recent messages, optionally filtered by topic prefix."""
        with self._lock:
            msgs = self._message_log[-limit:]
            if topic_filter:
                msgs = [m for m in msgs if m.topic.startswith(topic_filter)]
            return msgs

    def clear_log(self):
        """Clear message log."""
        with self._lock:
            self._message_log.clear()

    def get_state(self) -> dict:
        """Get bus state."""
        return {
            "name": self.name,
            "subscriptions": list(self._subscriptions.keys()),
            "message_count": len(self._message_log),
        }


class MQTTBridge:
    """Bridge between in-process NetworkBus and an external MQTT broker.

    When mosquitto or another broker is available, this class
    connects to it and forwards messages bidirectionally.
    """

    def __init__(self, network_bus: NetworkBus, broker_host: str = "localhost",
                 broker_port: int = 1883, topic_prefix: str = "oasis/sim"):
        self.network_bus = network_bus
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic_prefix = topic_prefix
        self._client = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to MQTT broker."""
        try:
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client(client_id="oasis-sim-bridge")
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message

            self._client.connect(self.broker_host, self.broker_port, keepalive=60)
            self._client.loop_start()

            # Bridge outgoing: subscribe to all local topics and forward
            self.network_bus.subscribe("#", self._forward_to_mqtt)
            return True

        except ImportError:
            print("Warning: paho-mqtt not installed. External broker unavailable.")
            return False
        except Exception as e:
            print(f"Warning: MQTT broker connection failed: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        """Called when connected to broker."""
        if rc == 0:
            self._connected = True
            client.subscribe(f"{self.topic_prefix}/#")

    def _on_message(self, client, userdata, msg):
        """Forward MQTT message to internal bus."""
        try:
            topic = msg.topic
            # Strip prefix for internal routing
            if topic.startswith(self.topic_prefix + "/"):
                topic = topic[len(self.topic_prefix) + 1:]

            try:
                payload = json.loads(msg.payload.decode())
            except Exception:
                payload = msg.payload.decode()

            self.network_bus.publish(topic, payload, sender="mqtt")
        except Exception as e:
            print(f"MQTT message processing error: {e}")

    def _forward_to_mqtt(self, topic: str, payload: Any, sender: str):
        """Forward internal bus message to MQTT broker."""
        if not self._connected or sender == "mqtt":
            return
        try:
            full_topic = f"{self.topic_prefix}/{topic}"
            self._client.publish(full_topic, json.dumps(payload))
        except Exception:
            pass

    def disconnect(self):
        """Disconnect from broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
