"""simavr wrapper: Arduino/AVR emulation with the stock simavr program.

The stock `simavr` program:
- loads an .elf or .hex firmware image;
- prints UART0 output on stdout, one line at a time, wrapped in ANSI color
  codes, with CR/LF shown as ".." at the end of the line;
- prints load messages ("Loaded N bytes ...") on stderr;
- buffers stdout when stdout is a pipe, so UART text arrives only at exit.
  On macOS and Linux this wrapper gives simavr a pseudo-terminal (pty) for
  stdout, so each UART line arrives when the firmware sends it;
- does not read stdin. There is no input channel for GPIO, UART, or
  interrupts. Input needs a simavr board harness written in C against
  libsimavr (planned, see docs/SIMULATION_PATHS_AVR_STM32.md phase S3).

Prerequisites:
    brew install simavr  # macOS
    apt install simavr   # Ubuntu/Debian
"""

from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


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
    """Configuration for a simavr run."""
    mcu: AvrMcu = AvrMcu.ATMEGA328P
    frequency: int = 16_000_000  # 16 MHz
    firmware_path: Optional[str] = None
    gdb_port: Optional[int] = None  # simavr -g <port>
    vcd_output: Optional[str] = None  # simavr -o <file>
    vcd_traces: tuple[str, ...] = ()  # simavr -at <name=kind@addr/mask>
    simavr_path: Optional[str] = None  # default: "simavr" on PATH


def parse_uart_line(raw: str) -> Optional[str]:
    """Return the UART text in one stdout line from simavr, or None.

    simavr colors each UART line. A line with no color code is not UART
    output.
    """
    if "\x1b[" not in raw:
        return None
    text = _ANSI.sub("", raw).rstrip("\r\n")
    if text.endswith(".."):
        text = text[:-2]
    return text


class SimavrEmulator:
    """Run firmware in the stock simavr program and collect UART output."""

    # The orchestrator reads this flag before it sends GPIO input.
    supports_gpio_input = False

    def __init__(self, config: SimavrConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self._gpio_state: dict[str, GpioState] = {}
        self._uart_lines: queue.Queue[str] = queue.Queue()
        self._log: list[str] = []
        self._callbacks: dict[str, list[Callable]] = {
            "gpio_change": [],
            "uart_rx": [],
        }
        self._threads: list[threading.Thread] = []
        self._pty_master: Optional[int] = None

    def load_firmware(self, firmware_path: str):
        """Load firmware from an .elf or .hex file."""
        path = Path(firmware_path)
        if not path.exists():
            raise FileNotFoundError(f"Firmware not found: {firmware_path}")
        if path.suffix not in (".elf", ".hex"):
            raise ValueError(f"Unsupported firmware format: {path.suffix}")
        self.config.firmware_path = str(path.absolute())

    def command(self) -> list[str]:
        """The simavr argument list. No shell is used."""
        if not self.config.firmware_path:
            raise ValueError("No firmware loaded")
        exe = self.config.simavr_path or shutil.which("simavr") or "simavr"
        cmd = [exe, "-m", self.config.mcu.value, "-f", str(self.config.frequency)]
        if self.config.gdb_port:
            cmd += ["-g", str(self.config.gdb_port)]
        if self.config.vcd_output:
            cmd += ["-o", self.config.vcd_output]
            for trace in self.config.vcd_traces:
                cmd += ["-at", trace]
        cmd.append(self.config.firmware_path)
        return cmd

    def start(self) -> bool:
        """Start simavr. UART lines arrive through read_uart() and callbacks."""
        cmd = self.command()
        stdout = subprocess.PIPE
        slave: Optional[int] = None
        if os.name == "posix":
            import pty
            self._pty_master, slave = pty.openpty()
            stdout = slave
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            self._close_pty()
            raise RuntimeError("simavr not found. Install with: brew install simavr")
        finally:
            if slave is not None:
                os.close(slave)
        self.running = True
        self._threads = [
            threading.Thread(target=self._read_stdout, daemon=True),
            threading.Thread(target=self._read_stderr, daemon=True),
        ]
        for t in self._threads:
            t.start()
        return True

    def stop(self):
        """Stop simavr."""
        self.running = False
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None
        self._close_pty()

    def _close_pty(self):
        if self._pty_master is not None:
            try:
                os.close(self._pty_master)
            except OSError:
                pass
            self._pty_master = None

    def reset(self):
        """Restart simavr from the reset vector."""
        self.stop()
        self.start()

    def _stdout_lines(self):
        """Yield decoded stdout lines from the pty or the pipe."""
        if self._pty_master is not None:
            buf = b""
            while True:
                try:
                    chunk = os.read(self._pty_master, 4096)
                except OSError:  # EIO on Linux when simavr exits; EBADF after stop()
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    yield line.decode("utf-8", errors="replace")
            if buf:
                yield buf.decode("utf-8", errors="replace")
        elif self.process and self.process.stdout:
            for raw in self.process.stdout:
                yield raw.decode("utf-8", errors="replace")

    def _read_stdout(self):
        for raw in self._stdout_lines():
            text = parse_uart_line(raw)
            if text is None:
                self._log.append(raw.rstrip("\n"))
                continue
            self._uart_lines.put(text)
            for cb in self._callbacks["uart_rx"]:
                cb(text)

    def _read_stderr(self):
        proc = self.process
        if not proc or not proc.stderr:
            return
        for raw in proc.stderr:
            self._log.append(raw.decode("utf-8", errors="replace").rstrip("\n"))

    @property
    def log(self) -> list[str]:
        """simavr messages that are not UART output."""
        return list(self._log)

    def read_uart(self, timeout: float = 0.1) -> Optional[str]:
        """Return the next UART line, or None after the timeout."""
        try:
            return self._uart_lines.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_gpio(self, port: str, pin: int) -> Optional[GpioState]:
        """GPIO output state. Stock simavr does not report it (use VCD traces)."""
        return self._gpio_state.get(f"{port}{pin}")

    def set_gpio(self, port: str, pin: int, value: bool):
        raise NotImplementedError(
            "stock simavr has no GPIO input channel; a libsimavr board harness is needed"
        )

    def send_uart(self, data: str):
        raise NotImplementedError(
            "stock simavr has no UART input channel; a libsimavr board harness is needed"
        )

    def trigger_interrupt(self, vector: int):
        raise NotImplementedError(
            "stock simavr has no interrupt input channel; a libsimavr board harness is needed"
        )

    def on_gpio_change(self, callback: Callable[[GpioState], None]):
        self._callbacks["gpio_change"].append(callback)

    def on_uart_rx(self, callback: Callable[[str], None]):
        self._callbacks["uart_rx"].append(callback)

    def get_state(self) -> dict:
        return {
            "running": self.running and self.process is not None and self.process.poll() is None,
            "mcu": self.config.mcu.value,
            "frequency": self.config.frequency,
            "firmware": self.config.firmware_path,
            "gpio": {k: {"port": v.port, "pin": v.pin, "value": v.value}
                     for k, v in self._gpio_state.items()},
        }


def run_for(config: SimavrConfig, seconds: float,
            until: Optional[Callable[[list[str]], bool]] = None) -> list[str]:
    """Run firmware for a wall-clock time limit and return the UART lines.

    Stops early when `until(lines)` returns True.
    """
    emu = SimavrEmulator(config)
    emu.start()
    lines: list[str] = []
    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline:
            line = emu.read_uart(timeout=0.05)
            if line is not None:
                lines.append(line)
                if until and until(lines):
                    break
            elif emu.process and emu.process.poll() is not None and emu._uart_lines.empty():
                break
    finally:
        emu.stop()
    return lines


class SimavrBuilder:
    """Compile Arduino sketches for simavr with arduino-cli."""

    @staticmethod
    def compile_sketch(sketch_path: str, board: str = "arduino:avr:uno",
                       output_dir: str = "./build") -> str:
        """Compile an Arduino sketch and return the path of the .elf file."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        cmd = [
            "arduino-cli", "compile",
            "--fqbn", board,
            "--output-dir", output_dir,
            sketch_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Compilation failed: {result.stderr}")
        for f in Path(output_dir).glob("*.elf"):
            return str(f)
        raise RuntimeError("No .elf file produced")

    @staticmethod
    def check_arduino_cli() -> bool:
        return shutil.which("arduino-cli") is not None
