"""Renode Wrapper - STM32/ARM emulation integration.

Renode is a development framework for embedded systems that enables
multi-node simulation with full peripheral modeling.

This wrapper provides:
- Loading compiled .elf firmware for STM32
- GPIO, UART, SPI, I2C peripheral access
- GDB integration for debugging
- Robot Framework test integration
- Multi-node simulation support

Prerequisites:
    # macOS
    brew install renode
    
    # Linux
    wget https://github.com/renode/renode/releases/download/v1.14.0/renode-1.14.0.linux-portable.tar.gz
"""

import subprocess
import threading
import socket
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from pathlib import Path


class Stm32Mcu(Enum):
    """Supported STM32 platforms in Renode."""
    STM32F103 = "stm32f103"  # Blue Pill
    STM32F401 = "stm32f401"  # Nucleo-F401RE
    STM32F407 = "stm32f407"  # Discovery
    STM32F429 = "stm32f429"  # Discovery
    STM32L476 = "stm32l476"  # Nucleo-L476RG
    STM32H743 = "stm32h743"  # Nucleo-H743ZI


@dataclass
class RenodeConfig:
    """Configuration for Renode instance."""
    platform: Stm32Mcu = Stm32Mcu.STM32F103
    firmware_path: Optional[str] = None
    telnet_port: int = 1234
    gdb_port: int = 3333
    uart_port: int = 4444
    headless: bool = True
    repl_script: Optional[str] = None  # Custom .resc script


# Platform definition scripts for Renode
PLATFORM_SCRIPTS = {
    Stm32Mcu.STM32F103: """
using sysbus
mach create "stm32f103"
machine LoadPlatformDescription @platforms/cpus/stm32f103.repl
machine LoadPlatformDescriptionFromString "gpioPortA: GPIO.STM32F1GPIOPort @ sysbus 0x40010800"
machine LoadPlatformDescriptionFromString "gpioPortB: GPIO.STM32F1GPIOPort @ sysbus 0x40010C00"
machine LoadPlatformDescriptionFromString "gpioPortC: GPIO.STM32F1GPIOPort @ sysbus 0x40011000"
""",
    Stm32Mcu.STM32F401: """
using sysbus
mach create "stm32f401"
machine LoadPlatformDescription @platforms/cpus/stm32f4.repl
""",
    Stm32Mcu.STM32F407: """
using sysbus
mach create "stm32f407"
machine LoadPlatformDescription @platforms/boards/stm32f4_discovery.repl
""",
}


class RenodeEmulator:
    """Wrapper around Renode for STM32/ARM emulation."""
    
    def __init__(self, config: RenodeConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self._telnet_socket: Optional[socket.socket] = None
        self._uart_socket: Optional[socket.socket] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._gpio_state: dict[str, bool] = {}
        self._callbacks: dict[str, list[Callable]] = {
            "gpio_change": [],
            "uart_rx": [],
        }
        
    def load_firmware(self, firmware_path: str):
        """Load firmware from .elf file."""
        path = Path(firmware_path)
        if not path.exists():
            raise FileNotFoundError(f"Firmware not found: {firmware_path}")
        
        if path.suffix != '.elf':
            raise ValueError(f"Renode requires .elf format, got: {path.suffix}")
        
        self.config.firmware_path = str(path.absolute())
    
    def _generate_script(self) -> str:
        """Generate Renode script for the configuration."""
        script_lines = []
        
        # Platform setup
        if self.config.platform in PLATFORM_SCRIPTS:
            script_lines.append(PLATFORM_SCRIPTS[self.config.platform])
        else:
            script_lines.append(f'include @platforms/cpus/{self.config.platform.value}.repl')
        
        # Load firmware
        if self.config.firmware_path:
            script_lines.append(f'sysbus LoadELF @{self.config.firmware_path}')
        
        # UART terminal
        script_lines.append(f'emulation CreateServerSocketTerminal {self.config.uart_port} "uart_term"')
        script_lines.append('connector Connect sysbus.usart1 uart_term')
        
        # GDB server
        script_lines.append(f'machine StartGdbServer {self.config.gdb_port}')
        
        # Start
        script_lines.append('start')
        
        return '\n'.join(script_lines)
    
    def start(self) -> bool:
        """Start the Renode emulator."""
        if not self.config.firmware_path:
            raise ValueError("No firmware loaded")
        
        # Write temporary script
        script_path = Path("/tmp/oasis_renode.resc")
        script_path.write_text(self._generate_script())
        
        # Build Renode command
        cmd = ["renode", "--disable-xwt"]  # Headless
        
        if self.config.headless:
            cmd.append("--console")
        
        cmd.extend(["--port", str(self.config.telnet_port)])
        cmd.append(str(script_path))
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.running = True
            
            # Wait for Renode to start
            time.sleep(2)
            
            # Connect to telnet for commands
            self._connect_telnet()
            
            # Connect to UART
            self._connect_uart()
            
            return True
        except FileNotFoundError:
            raise RuntimeError("Renode not found. Install from https://renode.io/")
        except Exception as e:
            raise RuntimeError(f"Failed to start Renode: {e}")
    
    def _connect_telnet(self):
        """Connect to Renode telnet interface."""
        try:
            self._telnet_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._telnet_socket.connect(("127.0.0.1", self.config.telnet_port))
            self._telnet_socket.settimeout(1.0)
        except Exception as e:
            print(f"Warning: Could not connect to Renode telnet: {e}")
    
    def _connect_uart(self):
        """Connect to UART terminal."""
        try:
            self._uart_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._uart_socket.connect(("127.0.0.1", self.config.uart_port))
            self._uart_socket.settimeout(0.1)
            
            # Start reader thread
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
        
        if self._telnet_socket:
            try:
                self._send_command("quit")
            except Exception:
                pass
            self._telnet_socket.close()
            self._telnet_socket = None
        
        if self._uart_socket:
            self._uart_socket.close()
            self._uart_socket = None
        
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None
    
    def _send_command(self, cmd: str) -> str:
        """Send command to Renode via telnet."""
        if not self._telnet_socket:
            raise RuntimeError("Not connected to Renode")
        
        self._telnet_socket.send(f"{cmd}\n".encode())
        
        # Read response
        response = b""
        try:
            while True:
                chunk = self._telnet_socket.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b"(machine-" in response or b"(monitor)" in response:
                    break
        except socket.timeout:
            pass
        
        return response.decode('utf-8', errors='ignore')
    
    def pause(self):
        """Pause emulation."""
        self._send_command("pause")
    
    def resume(self):
        """Resume emulation."""
        self._send_command("start")
    
    def step(self, instructions: int = 1):
        """Single-step execution."""
        self._send_command(f"sysbus.cpu Step {instructions}")
    
    def set_gpio(self, port: str, pin: int, value: bool):
        """Set GPIO input value."""
        cmd = f"sysbus.gpioPort{port} Set {pin} {str(value).lower()}"
        self._send_command(cmd)
    
    def get_gpio(self, port: str, pin: int) -> bool:
        """Get GPIO state."""
        cmd = f"sysbus.gpioPort{port} Get {pin}"
        response = self._send_command(cmd)
        return "True" in response or "true" in response
    
    def send_uart(self, data: str):
        """Send data to UART."""
        if self._uart_socket:
            self._uart_socket.send(data.encode())
    
    def read_memory(self, address: int, size: int = 4) -> int:
        """Read memory at address."""
        cmd = f"sysbus ReadDoubleWord {hex(address)}"
        response = self._send_command(cmd)
        # Parse hex value from response
        for line in response.split('\n'):
            if '0x' in line:
                try:
                    return int(line.strip(), 16)
                except ValueError:
                    pass
        return 0
    
    def write_memory(self, address: int, value: int):
        """Write memory at address."""
        cmd = f"sysbus WriteDoubleWord {hex(address)} {hex(value)}"
        self._send_command(cmd)
    
    def on_uart_rx(self, callback: Callable[[str], None]):
        """Register callback for UART receive."""
        self._callbacks["uart_rx"].append(callback)
    
    def get_state(self) -> dict:
        """Get emulator state."""
        return {
            "running": self.running,
            "platform": self.config.platform.value,
            "firmware": self.config.firmware_path,
            "gdb_port": self.config.gdb_port,
            "uart_port": self.config.uart_port,
        }


class RenodeBuilder:
    """Helper to compile STM32 firmware for Renode."""
    
    @staticmethod
    def compile_cmake(project_path: str, build_dir: str = "./build") -> str:
        """Compile a CMake-based STM32 project."""
        Path(build_dir).mkdir(parents=True, exist_ok=True)
        
        # Configure
        result = subprocess.run(
            ["cmake", "-B", build_dir, "-S", project_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"CMake configure failed: {result.stderr}")
        
        # Build
        result = subprocess.run(
            ["cmake", "--build", build_dir],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Build failed: {result.stderr}")
        
        # Find .elf
        for f in Path(build_dir).rglob("*.elf"):
            return str(f)
        
        raise RuntimeError("No .elf file produced")
    
    @staticmethod
    def check_renode() -> bool:
        """Check if Renode is installed."""
        try:
            result = subprocess.run(["renode", "--version"], 
                                    capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
