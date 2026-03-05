"""simavr Wrapper - Arduino/AVR emulation integration.

simavr is a lean AVR emulator that can run Arduino firmware.
This wrapper provides a Python interface for:
- Loading compiled .elf/.hex firmware
- GPIO state monitoring and manipulation
- Interrupt injection
- Peripheral simulation bridging

Prerequisites:
    brew install simavr  # macOS
    apt install simavr   # Ubuntu/Debian
"""

import subprocess
import threading
import queue
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from pathlib import Path


class AvrMcu(Enum):
    """Supported AVR microcontrollers."""
    ATMEGA328P = "atmega328p"  # Arduino Uno/Nano
    ATMEGA2560 = "atmega2560"  # Arduino Mega
    ATMEGA32U4 = "atmega32u4"  # Arduino Leonardo
    ATTINY85 = "attiny85"


@dataclass
class GpioState:
    """State of a GPIO pin."""
    pin: int
    port: str  # 'B', 'C', 'D', etc.
    direction: str  # 'input' or 'output'
    value: bool
    pullup: bool = False


@dataclass
class SimavrConfig:
    """Configuration for simavr instance."""
    mcu: AvrMcu = AvrMcu.ATMEGA328P
    frequency: int = 16_000_000  # 16 MHz
    firmware_path: Optional[str] = None
    gdb_port: Optional[int] = None  # For debugging
    vcd_trace: bool = False  # Value Change Dump for waveforms
    trace_file: Optional[str] = None


class SimavrEmulator:
    """Wrapper around simavr for Arduino/AVR emulation."""
    
    def __init__(self, config: SimavrConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self._gpio_state: dict[str, GpioState] = {}
        self._uart_rx_queue: queue.Queue = queue.Queue()
        self._uart_tx_queue: queue.Queue = queue.Queue()
        self._callbacks: dict[str, list[Callable]] = {
            "gpio_change": [],
            "uart_rx": [],
            "interrupt": [],
        }
        self._reader_thread: Optional[threading.Thread] = None
        
    def load_firmware(self, firmware_path: str):
        """Load firmware from .elf or .hex file."""
        path = Path(firmware_path)
        if not path.exists():
            raise FileNotFoundError(f"Firmware not found: {firmware_path}")
        
        if path.suffix not in ['.elf', '.hex']:
            raise ValueError(f"Unsupported firmware format: {path.suffix}")
        
        self.config.firmware_path = str(path.absolute())
    
    def start(self) -> bool:
        """Start the simavr emulator."""
        if not self.config.firmware_path:
            raise ValueError("No firmware loaded")
        
        # Build simavr command
        cmd = [
            "simavr",
            "-m", self.config.mcu.value,
            "-f", str(self.config.frequency),
        ]
        
        if self.config.gdb_port:
            cmd.extend(["-g", "-p", str(self.config.gdb_port)])
        
        if self.config.vcd_trace and self.config.trace_file:
            cmd.extend(["-t", self.config.trace_file])
        
        cmd.append(self.config.firmware_path)
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.running = True
            
            # Start reader thread for output
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()
            
            return True
        except FileNotFoundError:
            raise RuntimeError("simavr not found. Install with: brew install simavr")
        except Exception as e:
            raise RuntimeError(f"Failed to start simavr: {e}")
    
    def stop(self):
        """Stop the emulator."""
        self.running = False
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None
    
    def reset(self):
        """Reset the MCU."""
        if self.process:
            self.stop()
            self.start()
    
    def _read_output(self):
        """Background thread to read simavr output."""
        while self.running and self.process:
            try:
                line = self.process.stdout.readline()
                if line:
                    self._parse_output(line.strip())
            except Exception:
                break
    
    def _parse_output(self, line: str):
        """Parse simavr output for state changes."""
        # simavr outputs various trace information
        # Format depends on trace configuration
        if line.startswith("UART:"):
            # UART output
            data = line[5:].strip()
            self._uart_rx_queue.put(data)
            for cb in self._callbacks["uart_rx"]:
                cb(data)
        elif line.startswith("GPIO:"):
            # GPIO change
            parts = line[5:].strip().split()
            if len(parts) >= 3:
                port, pin, value = parts[0], int(parts[1]), parts[2] == "1"
                state = GpioState(pin=pin, port=port, direction="output", value=value)
                self._gpio_state[f"{port}{pin}"] = state
                for cb in self._callbacks["gpio_change"]:
                    cb(state)
    
    def get_gpio(self, port: str, pin: int) -> Optional[GpioState]:
        """Get the state of a GPIO pin."""
        key = f"{port}{pin}"
        return self._gpio_state.get(key)
    
    def set_gpio(self, port: str, pin: int, value: bool):
        """Set an input GPIO pin value (simulate external input)."""
        if not self.process:
            return
        
        # Send command to simavr via stdin
        # This requires custom simavr build with input handling
        cmd = f"GPIO:{port}{pin}={1 if value else 0}\n"
        try:
            self.process.stdin.write(cmd)
            self.process.stdin.flush()
        except Exception:
            pass
    
    def send_uart(self, data: str):
        """Send data to UART (simulate serial input)."""
        if not self.process:
            return
        
        for char in data:
            self._uart_tx_queue.put(char)
        
        # Send to simavr
        cmd = f"UART:{data}\n"
        try:
            self.process.stdin.write(cmd)
            self.process.stdin.flush()
        except Exception:
            pass
    
    def read_uart(self, timeout: float = 0.1) -> Optional[str]:
        """Read data from UART output."""
        try:
            return self._uart_rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def trigger_interrupt(self, vector: int):
        """Trigger an external interrupt."""
        if not self.process:
            return
        
        cmd = f"INT:{vector}\n"
        try:
            self.process.stdin.write(cmd)
            self.process.stdin.flush()
        except Exception:
            pass
    
    def on_gpio_change(self, callback: Callable[[GpioState], None]):
        """Register callback for GPIO changes."""
        self._callbacks["gpio_change"].append(callback)
    
    def on_uart_rx(self, callback: Callable[[str], None]):
        """Register callback for UART receive."""
        self._callbacks["uart_rx"].append(callback)
    
    def get_state(self) -> dict:
        """Get full emulator state."""
        return {
            "running": self.running,
            "mcu": self.config.mcu.value,
            "frequency": self.config.frequency,
            "firmware": self.config.firmware_path,
            "gpio": {k: {"port": v.port, "pin": v.pin, "value": v.value} 
                     for k, v in self._gpio_state.items()},
        }


class SimavrBuilder:
    """Helper to compile Arduino sketches for simavr."""
    
    @staticmethod
    def compile_sketch(sketch_path: str, board: str = "arduino:avr:uno", 
                       output_dir: str = "./build") -> str:
        """Compile an Arduino sketch to .elf using arduino-cli."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        cmd = [
            "arduino-cli", "compile",
            "--fqbn", board,
            "--output-dir", output_dir,
            "--export-binaries",
            sketch_path,
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Compilation failed: {result.stderr}")
        
        # Find the .elf file
        for f in Path(output_dir).glob("*.elf"):
            return str(f)
        
        raise RuntimeError("No .elf file produced")
    
    @staticmethod
    def check_arduino_cli() -> bool:
        """Check if arduino-cli is installed."""
        try:
            result = subprocess.run(["arduino-cli", "version"], 
                                    capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
