"""I2C Bus Simulation - Virtual I2C bus with device address routing.

Simulates an I2C bus where:
- A master (MCU or RPi) initiates transactions by address
- Multiple slave devices respond based on their 7-bit address
- Transactions are routed to the correct behavioral component

In simulation, I2C is abstracted as:
  master.write(addr, data) → slave_at_addr.on_write(data)
  master.read(addr, n)     → slave_at_addr.on_read() → data

Real emulator integration:
  - Renode: Uses its I2C peripheral model and custom C# plugin
  - QEMU RPi: Uses the Linux i2c-dev interface via sysfs
  - For behavioral tests: Pure Python bus routing
"""

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# Common I2C addresses for sensors
KNOWN_ADDRESSES = {
    0x40: "DHT20 / SHT20 / HDC1080",
    0x44: "SHT31",
    0x48: "ADS1115 / TMP102",
    0x3C: "SSD1306 OLED",
    0x68: "MPU6050 / DS3231 RTC",
    0x76: "BME280 (SDO=GND)",
    0x77: "BME280 (SDO=VCC) / BMP180",
    0x23: "BH1750",
    0x29: "VL53L0X / TSL2591",
    0x10: "VEML7700",
    0x60: "MCP4725 DAC",
}


@dataclass
class I2CTransaction:
    """An I2C transaction (read or write)."""
    address: int       # 7-bit slave address
    direction: str     # "write" or "read"
    data: bytes        # Data written (write) or requested length (read)
    timestamp_ms: int = 0


@dataclass
class I2CDevice:
    """An I2C slave device on the bus."""
    address: int
    name: str
    _write_handler: Optional[Callable[[bytes], None]] = field(default=None, repr=False)
    _read_handler: Optional[Callable[[int], bytes]] = field(default=None, repr=False)
    _transaction_log: list = field(default_factory=list, repr=False)

    def on_write(self, handler: Callable[[bytes], None]):
        """Register handler called when master writes to this device."""
        self._write_handler = handler
        return self

    def on_read(self, handler: Callable[[int], bytes]):
        """Register handler called when master reads from this device.
        Handler receives number of bytes requested, returns bytes.
        """
        self._read_handler = handler
        return self

    def handle_write(self, data: bytes):
        """Process a write transaction."""
        self._transaction_log.append(I2CTransaction(
            address=self.address, direction="write", data=data
        ))
        if self._write_handler:
            self._write_handler(data)

    def handle_read(self, length: int) -> bytes:
        """Process a read transaction."""
        self._transaction_log.append(I2CTransaction(
            address=self.address, direction="read", data=bytes(length)
        ))
        if self._read_handler:
            return self._read_handler(length)
        return bytes(length)  # Return zeros if no handler


class I2CBus:
    """Virtual I2C bus with device address routing.

    Usage:
        bus = I2CBus("i2c1")

        # Register a sensor device
        bme280 = bus.add_device(0x76, "bme280")
        bme280.on_read(lambda n: struct.pack(">HH", 2350, 9856))  # temp, pressure

        # Master write (from MCU or RPi simulation)
        bus.write(0x76, b"\\xF3")  # Send measurement command

        # Master read
        data = bus.read(0x76, 6)  # Read 6 bytes from BME280
    """

    def __init__(self, bus_id: str = "i2c1"):
        self.bus_id = bus_id
        self._devices: dict[int, I2CDevice] = {}
        self._transaction_log: list[I2CTransaction] = []
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[I2CTransaction], None]] = []

    def add_device(self, address: int, name: str = "") -> I2CDevice:
        """Register an I2C slave device."""
        if not name:
            name = KNOWN_ADDRESSES.get(address, f"device_0x{address:02x}")

        if address in self._devices:
            raise ValueError(f"Address 0x{address:02x} already registered on {self.bus_id}")

        device = I2CDevice(address=address, name=name)
        self._devices[address] = device
        return device

    def remove_device(self, address: int):
        """Remove a device from the bus."""
        self._devices.pop(address, None)

    def write(self, address: int, data: bytes) -> bool:
        """Master write transaction.
        Returns True if device ACKed (exists), False if NACK.
        """
        with self._lock:
            txn = I2CTransaction(address=address, direction="write", data=data)
            self._transaction_log.append(txn)
            for cb in self._callbacks:
                cb(txn)

            device = self._devices.get(address)
            if device:
                device.handle_write(data)
                return True
            return False  # NACK - no device at this address

    def read(self, address: int, length: int) -> Optional[bytes]:
        """Master read transaction.
        Returns bytes from device, or None if no device (NACK).
        """
        with self._lock:
            txn = I2CTransaction(address=address, direction="read",
                                 data=bytes(length))
            self._transaction_log.append(txn)
            for cb in self._callbacks:
                cb(txn)

            device = self._devices.get(address)
            if device:
                return device.handle_read(length)
            return None  # NACK

    def write_read(self, address: int, write_data: bytes, read_length: int) -> Optional[bytes]:
        """Combined write then read (register read pattern)."""
        if not self.write(address, write_data):
            return None
        return self.read(address, read_length)

    def scan(self) -> list[int]:
        """Scan for devices on the bus (like i2cdetect)."""
        return sorted(self._devices.keys())

    def on_transaction(self, callback: Callable[[I2CTransaction], None]):
        """Register callback for all transactions (for monitoring)."""
        self._callbacks.append(callback)

    def get_state(self) -> dict:
        """Get bus state."""
        return {
            "bus_id": self.bus_id,
            "devices": [
                {"address": f"0x{addr:02x}", "name": dev.name}
                for addr, dev in self._devices.items()
            ],
            "transaction_count": len(self._transaction_log),
        }

    def attach_to_behavioral_sensor(self, address: int, runtime, component_id: str,
                                     register_map: dict[int, str]):
        """Bridge I2C reads to behavioral component outputs.

        register_map: {register_address: output_signal_name}
        e.g., {0xF3: "temperature", 0xF5: "humidity"}
        """
        import struct

        device = self._devices.get(address)
        if not device:
            device = self.add_device(address, component_id)

        _pending_register = [None]

        def on_write(data: bytes):
            if data:
                _pending_register[0] = data[0]

        def on_read(length: int) -> bytes:
            reg = _pending_register[0]
            signal_name = register_map.get(reg, "")
            if signal_name:
                value = runtime.get_output(component_id, signal_name)
                if value is not None:
                    # Pack as 16-bit fixed point (value * 100)
                    raw = int(value * 100) & 0xFFFF
                    return struct.pack(">H", raw)[:length]
            return bytes(length)

        device.on_write(on_write)
        device.on_read(on_read)
