"""ESP32 Emulation Wrapper - QEMU and Wokwi integration.

Supports two backends:
1. QEMU ESP32 (espressif/qemu) - Full system emulation
2. Wokwi API - Cloud-based simulation with visual diagram

Prerequisites:
    # QEMU ESP32
    git clone https://github.com/espressif/qemu.git
    cd qemu && ./configure --target-list=xtensa-softmmu && make
    
    # Wokwi CLI (optional)
    npm install -g wokwi-cli
"""

import subprocess
import threading
import socket
import json
import time
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from pathlib import Path


class Esp32Variant(Enum):
    """ESP32 chip variants."""
    ESP32 = "esp32"
    ESP32_S2 = "esp32s2"
    ESP32_S3 = "esp32s3"
    ESP32_C3 = "esp32c3"  # RISC-V


class EmulationBackend(Enum):
    """Emulation backend selection."""
    QEMU = "qemu"
    WOKWI = "wokwi"


@dataclass
class Esp32Config:
    """Configuration for ESP32 emulation."""
    variant: Esp32Variant = Esp32Variant.ESP32
    backend: EmulationBackend = EmulationBackend.QEMU
    firmware_path: Optional[str] = None
    flash_size: str = "4MB"
    gdb_port: int = 1234
    uart_port: int = 3333
    wokwi_diagram: Optional[str] = None  # For Wokwi backend


class QemuEsp32Emulator:
    """QEMU-based ESP32 emulator."""
    
    def __init__(self, config: Esp32Config):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self._uart_socket: Optional[socket.socket] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._callbacks: dict[str, list[Callable]] = {
            "uart_rx": [],
            "gpio_change": [],
        }
        self._gpio_state: dict[int, bool] = {}
        
    def load_firmware(self, firmware_path: str):
        """Load firmware from .bin or .elf file."""
        path = Path(firmware_path)
        if not path.exists():
            raise FileNotFoundError(f"Firmware not found: {firmware_path}")
        
        self.config.firmware_path = str(path.absolute())
    
    def start(self) -> bool:
        """Start the QEMU ESP32 emulator."""
        if not self.config.firmware_path:
            raise ValueError("No firmware loaded")
        
        # Determine QEMU binary name
        qemu_bin = "qemu-system-xtensa"
        if self.config.variant == Esp32Variant.ESP32_C3:
            qemu_bin = "qemu-system-riscv32"
        
        # Build command
        cmd = [
            qemu_bin,
            "-nographic",
            "-machine", f"{self.config.variant.value}",
            "-drive", f"file={self.config.firmware_path},if=mtd,format=raw",
            "-serial", f"tcp::{self.config.uart_port},server,nowait",
            "-gdb", f"tcp::{self.config.gdb_port}",
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.running = True
            
            # Wait for QEMU to start
            time.sleep(2)
            
            # Connect to UART
            self._connect_uart()
            
            return True
        except FileNotFoundError:
            raise RuntimeError(f"{qemu_bin} not found. Install ESP32 QEMU.")
        except Exception as e:
            raise RuntimeError(f"Failed to start QEMU: {e}")
    
    def _connect_uart(self):
        """Connect to UART serial port."""
        try:
            self._uart_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._uart_socket.connect(("127.0.0.1", self.config.uart_port))
            self._uart_socket.settimeout(0.1)
            
            self._reader_thread = threading.Thread(target=self._read_uart, daemon=True)
            self._reader_thread.start()
        except Exception as e:
            print(f"Warning: Could not connect to UART: {e}")
    
    def _read_uart(self):
        """Background thread to read UART output."""
        while self.running and self._uart_socket:
            try:
                data = self._uart_socket.recv(1024)
                if data:
                    text = data.decode('utf-8', errors='ignore')
                    for cb in self._callbacks["uart_rx"]:
                        cb(text)
            except socket.timeout:
                continue
            except Exception:
                break
    
    def stop(self):
        """Stop the emulator."""
        self.running = False
        
        if self._uart_socket:
            self._uart_socket.close()
            self._uart_socket = None
        
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None
    
    def send_uart(self, data: str):
        """Send data to UART."""
        if self._uart_socket:
            self._uart_socket.send(data.encode())
    
    def set_gpio(self, pin: int, value: bool):
        """Set GPIO input value."""
        self._gpio_state[pin] = value
        # QEMU GPIO manipulation requires monitor commands
        # This is a placeholder - real implementation needs QEMU monitor
    
    def get_gpio(self, pin: int) -> bool:
        """Get GPIO state."""
        return self._gpio_state.get(pin, False)
    
    def on_uart_rx(self, callback: Callable[[str], None]):
        """Register callback for UART receive."""
        self._callbacks["uart_rx"].append(callback)
    
    def get_state(self) -> dict:
        """Get emulator state."""
        return {
            "running": self.running,
            "variant": self.config.variant.value,
            "backend": "qemu",
            "firmware": self.config.firmware_path,
            "gdb_port": self.config.gdb_port,
            "gpio": dict(self._gpio_state),
        }


class WokwiEmulator:
    """Wokwi-based ESP32 simulation (cloud API)."""
    
    def __init__(self, config: Esp32Config):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self._callbacks: dict[str, list[Callable]] = {
            "uart_rx": [],
            "gpio_change": [],
        }
    
    def load_firmware(self, firmware_path: str):
        """Load firmware .elf file."""
        self.config.firmware_path = firmware_path
    
    def load_diagram(self, diagram_path: str):
        """Load Wokwi diagram.json."""
        self.config.wokwi_diagram = diagram_path
    
    def generate_wokwi_config(self, output_dir: str) -> tuple[str, str]:
        """Generate wokwi.toml and diagram.json for simulation."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # wokwi.toml
        wokwi_toml = f"""[wokwi]
version = 1
firmware = "{self.config.firmware_path}"
elf = "{self.config.firmware_path}"

[[chip]]
name = "{self.config.variant.value}"
"""
        toml_path = output_path / "wokwi.toml"
        toml_path.write_text(wokwi_toml)
        
        # diagram.json (basic)
        diagram = {
            "version": 1,
            "author": "Oasis",
            "editor": "wokwi",
            "parts": [
                {
                    "type": f"wokwi-{self.config.variant.value}-devkit-v1",
                    "id": "esp",
                    "top": 0,
                    "left": 0,
                    "attrs": {}
                }
            ],
            "connections": []
        }
        
        if self.config.wokwi_diagram:
            # Use existing diagram
            diagram_path = output_path / "diagram.json"
            import shutil
            shutil.copy(self.config.wokwi_diagram, diagram_path)
        else:
            diagram_path = output_path / "diagram.json"
            diagram_path.write_text(json.dumps(diagram, indent=2))
        
        return str(toml_path), str(diagram_path)
    
    def start(self) -> bool:
        """Start Wokwi CLI simulation."""
        if not self.config.firmware_path:
            raise ValueError("No firmware loaded")
        
        # Generate config files
        toml_path, _ = self.generate_wokwi_config("/tmp/oasis_wokwi")
        
        cmd = [
            "wokwi-cli",
            "--scenario", toml_path,
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.running = True
            
            # Start reader thread
            threading.Thread(target=self._read_output, daemon=True).start()
            
            return True
        except FileNotFoundError:
            raise RuntimeError("wokwi-cli not found. Install with: npm install -g wokwi-cli")
    
    def _read_output(self):
        """Read Wokwi output."""
        while self.running and self.process:
            try:
                line = self.process.stdout.readline()
                if line:
                    for cb in self._callbacks["uart_rx"]:
                        cb(line.strip())
            except Exception:
                break
    
    def stop(self):
        """Stop the simulation."""
        self.running = False
        if self.process:
            self.process.terminate()
            self.process = None
    
    def on_uart_rx(self, callback: Callable[[str], None]):
        """Register callback for output."""
        self._callbacks["uart_rx"].append(callback)
    
    def get_state(self) -> dict:
        """Get emulator state."""
        return {
            "running": self.running,
            "variant": self.config.variant.value,
            "backend": "wokwi",
            "firmware": self.config.firmware_path,
        }


class Esp32Emulator:
    """Unified ESP32 emulator with backend selection."""
    
    def __init__(self, config: Esp32Config):
        self.config = config
        
        if config.backend == EmulationBackend.QEMU:
            self._impl = QemuEsp32Emulator(config)
        else:
            self._impl = WokwiEmulator(config)
    
    def load_firmware(self, path: str):
        self._impl.load_firmware(path)
    
    def start(self) -> bool:
        return self._impl.start()
    
    def stop(self):
        self._impl.stop()
    
    def send_uart(self, data: str):
        if hasattr(self._impl, 'send_uart'):
            self._impl.send_uart(data)
    
    def on_uart_rx(self, callback: Callable[[str], None]):
        self._impl.on_uart_rx(callback)
    
    def get_state(self) -> dict:
        return self._impl.get_state()


class Esp32Builder:
    """Helper to compile ESP32 firmware."""
    
    @staticmethod
    def compile_idf(project_path: str, target: str = "esp32") -> str:
        """Compile ESP-IDF project."""
        env = os.environ.copy()
        
        cmd = ["idf.py", "set-target", target]
        subprocess.run(cmd, cwd=project_path, env=env, check=True)
        
        cmd = ["idf.py", "build"]
        subprocess.run(cmd, cwd=project_path, env=env, check=True)
        
        # Find firmware
        build_dir = Path(project_path) / "build"
        for f in build_dir.glob("*.elf"):
            return str(f)
        
        raise RuntimeError("No .elf file produced")
    
    @staticmethod
    def check_esp_idf() -> bool:
        """Check if ESP-IDF is installed."""
        try:
            result = subprocess.run(["idf.py", "--version"], 
                                    capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
