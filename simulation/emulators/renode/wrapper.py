"""Renode wrapper: STM32/ARM emulation.

Two modes:
- run_for(): batch run. Renode loads the firmware, runs for a set simulated
  time, writes UART output to a file, and exits. No sockets.
- RenodeEmulator: interactive run. The Renode monitor listens on a telnet
  port; the UART is a server socket. The wrapper connects to the UART first,
  then sends "start", so no early UART output is lost.

Paths go into Renode scripts as double-quoted strings. Renode accepts
spaces inside a quoted string. A path that contains a double quote or a
line break is refused.

Prerequisites:
    macOS: install the Renode .dmg (https://renode.io); the program is
           /Applications/Renode.app/Contents/MacOS/Renode
    Linux: renode-<version>.linux-portable-dotnet.tar.gz from the Renode
           GitHub releases
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

MACOS_APP = "/Applications/Renode.app/Contents/MacOS/Renode"


class Stm32Mcu(Enum):
    """Supported STM32 platforms in Renode."""
    STM32F103 = "stm32f103"  # Blue Pill
    STM32F401 = "stm32f401"  # Nucleo-F401RE (nearest Renode model: stm32f4.repl)
    STM32F407 = "stm32f407"  # Discovery
    STM32F429 = "stm32f429"  # Discovery
    STM32L476 = "stm32l476"  # Nucleo-L476RG (no Renode model in 1.16)
    STM32H743 = "stm32h743"  # Nucleo-H743ZI


# Renode platform description for each chip. stm32f103.repl already defines
# GPIO ports A to D and USART1 to USART3.
PLATFORM_REPL = {
    Stm32Mcu.STM32F103: "platforms/cpus/stm32f103.repl",
    # stm32f4.repl describes an STM32F407-class chip. Renode 1.16 has no
    # STM32F401 or STM32F411 model.
    Stm32Mcu.STM32F401: "platforms/cpus/stm32f4.repl",
    Stm32Mcu.STM32F407: "platforms/boards/stm32f4_discovery.repl",
    Stm32Mcu.STM32F429: "platforms/cpus/stm32f429.repl",
    Stm32Mcu.STM32H743: "platforms/cpus/stm32h743.repl",
}


@dataclass
class RenodeConfig:
    """Configuration for a Renode run."""
    platform: Stm32Mcu = Stm32Mcu.STM32F103
    firmware_path: Optional[str] = None
    uart: str = "usart1"
    telnet_port: int = 0  # 0: pick a free port
    uart_port: int = 0    # 0: pick a free port
    gdb_port: Optional[int] = None
    renode_path: Optional[str] = None
    start_timeout: float = 30.0


def find_renode(explicit: Optional[str] = None) -> str:
    """Return the Renode program path."""
    if explicit:
        return explicit
    found = shutil.which("renode")
    if found:
        return found
    if Path(MACOS_APP).exists():
        return MACOS_APP
    raise RuntimeError("Renode not found. Install from https://renode.io/")


def quote(path: str | Path) -> str:
    """Quote a file path for a Renode script."""
    text = str(path)
    if '"' in text or "\n" in text or "\r" in text:
        raise ValueError(f"path cannot be used in a Renode script: {text!r}")
    return f'"{text}"'


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _platform_repl(platform: Stm32Mcu) -> str:
    try:
        return PLATFORM_REPL[platform]
    except KeyError:
        raise ValueError(f"No Renode platform description for {platform.value}")


def batch_script(platform: Stm32Mcu, firmware: str | Path, uart: str,
                 uart_out: str | Path, seconds: float) -> str:
    """Renode script for a batch run: load, run, write UART to a file, quit."""
    return "\n".join([
        f'mach create "{platform.value}"',
        f"machine LoadPlatformDescription @{_platform_repl(platform)}",
        f"sysbus LoadELF {quote(firmware)}",
        f"sysbus.{uart} CreateFileBackend {quote(uart_out)} true",
        f'emulation RunFor "{seconds}"',
        "quit",
        "",
    ])


def run_for(config: RenodeConfig, seconds: float, wall_timeout: float = 120.0) -> str:
    """Run firmware for `seconds` of simulated time. Return the UART text."""
    if not config.firmware_path:
        raise ValueError("No firmware loaded")
    exe = find_renode(config.renode_path)
    with tempfile.TemporaryDirectory(prefix="oasis-renode-") as tmp:
        out = Path(tmp) / "uart.txt"
        script = Path(tmp) / "run.resc"
        script.write_text(batch_script(config.platform, config.firmware_path,
                                       config.uart, out, seconds))
        result = subprocess.run(
            # A script path with a space fails as a plain argument; `-e include` works.
            [exe, "--disable-xwt", "--plain", "-e", f"include {quote(script)}"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            errors="replace", timeout=wall_timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Renode exited with {result.returncode}: {result.stdout[-2000:]}")
        return out.read_text(errors="replace") if out.exists() else ""


class RenodeEmulator:
    """Interactive Renode run with a monitor socket and a UART socket."""

    supports_gpio_input = True

    def __init__(self, config: RenodeConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self._tmp: Optional[tempfile.TemporaryDirectory] = None
        self._telnet: Optional[socket.socket] = None
        self._uart: Optional[socket.socket] = None
        self._reader: Optional[threading.Thread] = None
        self._callbacks: dict[str, list[Callable]] = {"gpio_change": [], "uart_rx": []}
        self._lock = threading.Lock()

    @property
    def machine(self) -> str:
        return self.config.platform.value

    def load_firmware(self, firmware_path: str):
        path = Path(firmware_path)
        if not path.exists():
            raise FileNotFoundError(f"Firmware not found: {firmware_path}")
        with path.open("rb") as f:
            if f.read(4) != b"\x7fELF":
                raise ValueError(f"Renode needs an ELF file: {firmware_path}")
        self.config.firmware_path = str(path.absolute())

    def _generate_script(self) -> str:
        lines = [
            f'mach create "{self.machine}"',
            f"machine LoadPlatformDescription @{_platform_repl(self.config.platform)}",
            f"sysbus LoadELF {quote(self.config.firmware_path)}",
            f'emulation CreateServerSocketTerminal {self.config.uart_port} "uart_term" false',
            f"connector Connect sysbus.{self.config.uart} uart_term",
        ]
        if self.config.gdb_port:
            lines.append(f"machine StartGdbServer {self.config.gdb_port}")
        # No "start" here: start() connects the UART socket first.
        return "\n".join(lines) + "\n"

    def start(self) -> bool:
        if not self.config.firmware_path:
            raise ValueError("No firmware loaded")
        exe = find_renode(self.config.renode_path)
        if not self.config.telnet_port:
            self.config.telnet_port = _free_port()
        if not self.config.uart_port:
            self.config.uart_port = _free_port()
        self._tmp = tempfile.TemporaryDirectory(prefix="oasis-renode-")
        script = Path(self._tmp.name) / "run.resc"
        script.write_text(self._generate_script())
        self.process = subprocess.Popen(
            [exe, "--disable-xwt", "--plain", "--port", str(self.config.telnet_port),
             "-e", f"include {quote(script)}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.running = True
        try:
            self._telnet = self._connect(self.config.telnet_port)
            self._telnet.settimeout(2.0)
            self._read_until_prompt()
            # The script runs after the monitor opens. Wait for the machine prompt.
            self._wait_for_machine()
            self._uart = self._connect(self.config.uart_port)
            self._uart.settimeout(0.2)
            self._reader = threading.Thread(target=self._read_uart, daemon=True)
            self._reader.start()
            self._send_command("start")
        except Exception:
            self.stop()
            raise
        return True

    def _connect(self, port: int) -> socket.socket:
        deadline = time.monotonic() + self.config.start_timeout
        last: Optional[Exception] = None
        while time.monotonic() < deadline:
            if self.process and self.process.poll() is not None:
                raise RuntimeError(f"Renode exited with {self.process.returncode}")
            try:
                return socket.create_connection(("127.0.0.1", port), timeout=1.0)
            except OSError as e:
                last = e
                time.sleep(0.2)
        raise RuntimeError(f"Renode port {port} did not open: {last}")

    def _wait_for_machine(self):
        deadline = time.monotonic() + self.config.start_timeout
        while time.monotonic() < deadline:
            reply = self._send_command(f'mach set "{self.machine}"')
            if f"({self.machine})" in reply:
                return
            time.sleep(0.3)
        raise RuntimeError(f"Renode machine {self.machine} did not appear")

    def _read_until_prompt(self) -> str:
        assert self._telnet is not None
        data = b""
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                chunk = self._telnet.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            data += chunk
            tail = data.rstrip()
            if tail.endswith(f"({self.machine})".encode()) or tail.endswith(b"(monitor)"):
                break
        return data.decode("utf-8", errors="ignore")

    def _read_uart(self):
        while self.running and self._uart:
            try:
                data = self._uart.recv(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            text = data.decode("utf-8", errors="ignore")
            for cb in self._callbacks["uart_rx"]:
                cb(text)

    def _send_command(self, cmd: str) -> str:
        if not self._telnet:
            raise RuntimeError("Not connected to Renode")
        with self._lock:
            self._telnet.sendall(f"{cmd}\n".encode())
            return self._read_until_prompt()

    def stop(self):
        self.running = False
        if self._telnet:
            try:
                self._telnet.sendall(b"quit\n")
            except OSError:
                pass
            self._telnet.close()
            self._telnet = None
        if self._uart:
            self._uart.close()
            self._uart = None
        if self.process:
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process = None
        if self._tmp:
            self._tmp.cleanup()
            self._tmp = None

    def pause(self):
        self._send_command("pause")

    def resume(self):
        self._send_command("start")

    def step(self, instructions: int = 1):
        self._send_command(f"sysbus.cpu Step {instructions}")

    def set_gpio(self, port: str, pin: int, value: bool):
        self._send_command(f"sysbus.gpioPort{port} OnGPIO {pin} {str(value).lower()}")

    def get_gpio(self, port: str, pin: int) -> bool:
        """Pin state. GetGPIOs prints "(N, GPIO: set)" or "(N, GPIO: unset)" per pin."""
        reply = self._send_command(f"sysbus.gpioPort{port} GetGPIOs")
        return f"({pin}, GPIO: set)" in reply

    def send_uart(self, data: str):
        if self._uart:
            self._uart.sendall(data.encode())

    def read_memory(self, address: int) -> int:
        reply = self._send_command(f"sysbus ReadDoubleWord {hex(address)}")
        for line in reply.splitlines():
            line = line.strip()
            if line.startswith("0x"):
                try:
                    return int(line, 16)
                except ValueError:
                    pass
        return 0

    def write_memory(self, address: int, value: int):
        self._send_command(f"sysbus WriteDoubleWord {hex(address)} {hex(value)}")

    def on_uart_rx(self, callback: Callable[[str], None]):
        self._callbacks["uart_rx"].append(callback)

    def get_state(self) -> dict:
        return {
            "running": self.running,
            "platform": self.config.platform.value,
            "firmware": self.config.firmware_path,
            "gdb_port": self.config.gdb_port,
            "uart_port": self.config.uart_port,
        }


class RenodeBuilder:
    """Build STM32 firmware for Renode."""

    @staticmethod
    def compile_cargo(project_path: str, target: str = "thumbv7m-none-eabi") -> str:
        """Build a Cargo firmware project in release mode and return the ELF path."""
        result = subprocess.run(["cargo", "build", "--release"], cwd=project_path,
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Build failed: {result.stderr}")
        meta = subprocess.run(["cargo", "metadata", "--no-deps", "--format-version", "1"],
                              cwd=project_path, capture_output=True, text=True, check=True)
        import json
        data = json.loads(meta.stdout)
        name = data["packages"][0]["name"]
        elf = Path(data["target_directory"]) / target / "release" / name
        if not elf.exists():
            raise RuntimeError(f"No ELF at {elf}")
        return str(elf)

    @staticmethod
    def compile_cmake(project_path: str, build_dir: str = "./build") -> str:
        """Build a CMake STM32 project and return the first .elf file."""
        Path(build_dir).mkdir(parents=True, exist_ok=True)
        for args in (["cmake", "-B", build_dir, "-S", project_path],
                     ["cmake", "--build", build_dir]):
            result = subprocess.run(args, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"{args[1]} failed: {result.stderr}")
        for f in Path(build_dir).rglob("*.elf"):
            return str(f)
        raise RuntimeError("No .elf file produced")

    @staticmethod
    def check_renode() -> bool:
        try:
            find_renode()
            return True
        except RuntimeError:
            return False
