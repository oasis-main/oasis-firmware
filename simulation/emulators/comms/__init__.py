"""Inter-board communication simulation.

Provides virtual buses connecting emulated MCUs and Linux SBCs:
- SerialBus: UART/serial point-to-point
- I2CBus: Multi-device I2C bus
- SPIBus: SPI master/slave
- NetworkBus: TCP/MQTT-based communication
"""

from .serial_bus import SerialBus, SerialEndpoint
from .i2c_bus import I2CBus, I2CDevice
from .network_bus import NetworkBus, MQTTBridge
from .multi_board import MultiBoardOrchestrator, BoardNode, BoardLink, LinkType

__all__ = [
    "SerialBus",
    "SerialEndpoint",
    "I2CBus",
    "I2CDevice",
    "NetworkBus",
    "MQTTBridge",
    "MultiBoardOrchestrator",
    "BoardNode",
    "BoardLink",
    "LinkType",
]
