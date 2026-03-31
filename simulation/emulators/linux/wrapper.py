"""Linux/SBC Board Emulator - QEMU-based emulation for RPi and other SBCs.

Supports full Linux system emulation via QEMU with:
- Raspberry Pi Zero W, 2W, 3B, 4B, 5
- BeagleBone Black
- NVIDIA Jetson Nano (ARM Cortex-A57)
- Generic ARM/RISC-V boards

Communication bridges:
- UART (PTY or TCP socket)
- GPIO via qemu-gpio plugin or sysfs injection
- Network (tap/user mode networking with MQTT, SSH)
- I2C/SPI via virtual bus proxy

Prerequisites:
    # QEMU (system emulation)
    brew install qemu

    # RPi kernel/image (lightweight - for testing without full OS):
    # Use a minimal Buildroot image or existing RPi OS image

Notes on RPi OS images:
    - Full RPi OS (~4GB): https://www.raspberrypi.com/software/
    - Minimal for testing: Use raspi-minibian or custom buildroot
    - Kernel-only: https://github.com/dhruvvyas90/qemu-rpi-kernel
"""

import subprocess
import threading
import socket
import os
import time
import pty
import select
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


class LinuxBoard(Enum):
    """Supported Linux SBC board types."""
    RPI_ZERO_W   = "rpi_zero_w"     # ARM1176JZF-S (ARMv6)
    RPI_ZERO_2W  = "rpi_zero_2w"    # Cortex-A53 (ARMv8)
    RPI_3B       = "rpi_3b"         # Cortex-A53 (ARMv8)
    RPI_4B       = "rpi_4b"         # Cortex-A72 (ARMv8)
    RPI_5        = "rpi_5"          # Cortex-A76 (ARMv8)
    BEAGLEBONE   = "beaglebone"     # Cortex-A8 (ARMv7)
    JETSON_NANO  = "jetson_nano"    # Cortex-A57 (ARMv8)
    GENERIC_ARM  = "generic_arm"    # Versatile Express (ARMv7, most compatible)
    GENERIC_ARM64 = "generic_arm64" # ARM64 virt machine


@dataclass
class BoardProfile:
    """QEMU machine profile for a Linux board."""
    machine: str           # QEMU -machine arg
    cpu: str               # QEMU -cpu arg
    arch: str              # qemu-system-{arch}
    ram_mb: int            # Default RAM in MB
    dtb: Optional[str]     # Device tree blob (optional)
    kernel_cmdline: str    # Default kernel cmdline
    uart_device: str       # Which UART device to expose (e.g., ttyAMA0)
    gpio_count: int        # Number of GPIO pins
    notes: str


BOARD_PROFILES: dict[LinuxBoard, BoardProfile] = {
    LinuxBoard.RPI_ZERO_W: BoardProfile(
        machine="versatilepb",
        cpu="arm1176",
        arch="arm",
        ram_mb=512,
        dtb=None,
        kernel_cmdline="console=ttyAMA0 root=/dev/mmcblk0p2 rootfstype=ext4",
        uart_device="ttyAMA0",
        gpio_count=26,
        notes="ARMv6, use versatile PB for compatibility. Real Zero uses BCM2835.",
    ),
    LinuxBoard.RPI_ZERO_2W: BoardProfile(
        machine="raspi3b",
        cpu="cortex-a53",
        arch="aarch64",
        ram_mb=512,
        dtb=None,
        kernel_cmdline="console=ttyAMA0 root=/dev/mmcblk0p2 rootfstype=ext4",
        uart_device="ttyAMA0",
        gpio_count=40,
        notes="ARMv8 Cortex-A53, use raspi3b machine.",
    ),
    LinuxBoard.RPI_3B: BoardProfile(
        machine="raspi3b",
        cpu="cortex-a53",
        arch="aarch64",
        ram_mb=1024,
        dtb=None,
        kernel_cmdline="console=ttyAMA0 root=/dev/mmcblk0p2 rootfstype=ext4",
        uart_device="ttyAMA0",
        gpio_count=40,
        notes="ARMv8 Cortex-A53, BCM2837.",
    ),
    LinuxBoard.RPI_4B: BoardProfile(
        machine="raspi4b",
        cpu="cortex-a72",
        arch="aarch64",
        ram_mb=4096,
        dtb=None,
        kernel_cmdline="console=ttyAMA0 root=/dev/mmcblk0p2 rootfstype=ext4 rw",
        uart_device="ttyAMA0",
        gpio_count=40,
        notes="ARMv8 Cortex-A72, BCM2711.",
    ),
    LinuxBoard.RPI_5: BoardProfile(
        machine="raspi4b",  # Closest available in QEMU
        cpu="cortex-a76",
        arch="aarch64",
        ram_mb=8192,
        dtb=None,
        kernel_cmdline="console=ttyAMA0 root=/dev/mmcblk0p2 rootfstype=ext4 rw",
        uart_device="ttyAMA0",
        gpio_count=40,
        notes="RPi 5 uses BCM2712 (not yet in QEMU). Falls back to raspi4b.",
    ),
    LinuxBoard.BEAGLEBONE: BoardProfile(
        machine="beagle",
        cpu="cortex-a8",
        arch="arm",
        ram_mb=512,
        dtb=None,
        kernel_cmdline="console=ttyO0,115200n8 root=/dev/mmcblk0p2 rootfstype=ext4",
        uart_device="ttyO0",
        gpio_count=92,
        notes="ARMv7 Cortex-A8, AM335x.",
    ),
    LinuxBoard.JETSON_NANO: BoardProfile(
        machine="virt",
        cpu="cortex-a57",
        arch="aarch64",
        ram_mb=4096,
        dtb=None,
        kernel_cmdline="console=ttyAMA0 root=/dev/vda rootfstype=ext4",
        uart_device="ttyAMA0",
        gpio_count=40,
        notes="Generic virt machine with Cortex-A57 approximates Jetson Nano.",
    ),
    LinuxBoard.GENERIC_ARM: BoardProfile(
        machine="virt",
        cpu="cortex-a15",
        arch="arm",
        ram_mb=1024,
        dtb=None,
        kernel_cmdline="console=ttyAMA0 root=/dev/vda",
        uart_device="ttyAMA0",
        gpio_count=32,
        notes="Generic ARMv7 virt machine. Most compatible for testing.",
    ),
    LinuxBoard.GENERIC_ARM64: BoardProfile(
        machine="virt",
        cpu="cortex-a53",
        arch="aarch64",
        ram_mb=2048,
        dtb=None,
        kernel_cmdline="console=ttyAMA0 root=/dev/vda",
        uart_device="ttyAMA0",
        gpio_count=32,
        notes="Generic ARM64 virt machine.",
    ),
}


@dataclass
class LinuxBoardConfig:
    """Configuration for a Linux SBC emulation instance."""
    board: LinuxBoard
    kernel_path: Optional[str] = None       # Path to kernel image (zImage/Image)
    dtb_path: Optional[str] = None          # Optional DTB
    rootfs_path: Optional[str] = None       # Root filesystem image
    ram_mb: Optional[int] = None            # Override default RAM
    uart_mode: str = "pty"                  # "pty" or "tcp"
    uart_tcp_port: int = 5555               # If uart_mode == "tcp"
    ssh_port: int = 2222                    # Host port for SSH forwarding
    extra_ports: dict[int, int] = field(default_factory=dict)  # {host: guest}
    gdb_port: Optional[int] = None          # GDB server port
    enable_kvm: bool = False                # Enable KVM acceleration (Linux host only)
    headless: bool = True                   # No display
    snapshot: bool = True                   # Don't write changes to disk image
    extra_args: list[str] = field(default_factory=list)


class LinuxBoardEmulator:
    """QEMU-based emulator for Linux SBCs (RPi, BeagleBone, etc.)."""

    def __init__(self, config: LinuxBoardConfig):
        self.config = config
        self.profile = BOARD_PROFILES[config.board]
        self.process: Optional[subprocess.Popen] = None
        self.running = False

        # UART communication
        self._uart_pty_master: Optional[int] = None   # PTY file descriptor
        self._uart_pty_path: Optional[str] = None      # PTY slave path
        self._uart_socket: Optional[socket.socket] = None
        self._uart_reader: Optional[threading.Thread] = None
        self._uart_buffer: list[str] = []

        # Callbacks
        self._callbacks: dict[str, list[Callable]] = {
            "uart_rx": [],
            "boot_complete": [],
            "error": [],
        }

        # SSH/network
        self._ssh_port = config.ssh_port

        # Boot state
        self._booted = False
        self._boot_timeout = 120  # seconds

    def load_kernel(self, kernel_path: str):
        """Set kernel image path."""
        path = Path(kernel_path)
        if not path.exists():
            raise FileNotFoundError(f"Kernel not found: {kernel_path}")
        self.config.kernel_path = str(path.absolute())

    def load_rootfs(self, rootfs_path: str):
        """Set root filesystem image path."""
        path = Path(rootfs_path)
        if not path.exists():
            raise FileNotFoundError(f"Rootfs not found: {rootfs_path}")
        self.config.rootfs_path = str(path.absolute())

    def _build_qemu_cmd(self) -> list[str]:
        """Build the QEMU command line."""
        profile = self.profile
        cfg = self.config
        ram = cfg.ram_mb or profile.ram_mb

        qemu_bin = f"qemu-system-{profile.arch}"

        cmd = [
            qemu_bin,
            "-machine", profile.machine,
            "-cpu", profile.cpu,
            "-m", str(ram),
        ]

        if cfg.headless:
            cmd.extend(["-display", "none"])

        # Kernel
        if cfg.kernel_path:
            cmd.extend(["-kernel", cfg.kernel_path])

        # DTB
        if cfg.dtb_path:
            cmd.extend(["-dtb", cfg.dtb_path])
        elif profile.dtb:
            cmd.extend(["-dtb", profile.dtb])

        # Root filesystem
        if cfg.rootfs_path:
            suffix = Path(cfg.rootfs_path).suffix
            if suffix in [".img", ".qcow2"]:
                fmt = "qcow2" if suffix == ".qcow2" else "raw"
                drive = f"file={cfg.rootfs_path},format={fmt},if=sd"
                if cfg.snapshot:
                    drive += ",snapshot=on"
                cmd.extend(["-drive", drive])
            else:
                cmd.extend(["-initrd", cfg.rootfs_path])

        # Kernel cmdline
        if cfg.kernel_path:
            cmd.extend(["-append", profile.kernel_cmdline])

        # UART
        if cfg.uart_mode == "pty":
            cmd.extend(["-serial", "pty"])
        else:
            cmd.extend(["-serial", f"tcp::{cfg.uart_tcp_port},server,nowait"])

        # Network: user-mode with port forwarding
        hostfwd = f"hostfwd=tcp::{cfg.ssh_port}-:22"
        for host_port, guest_port in cfg.extra_ports.items():
            hostfwd += f",hostfwd=tcp::{host_port}-:{guest_port}"
        cmd.extend(["-netdev", f"user,id=net0,{hostfwd}",
                    "-device", "virtio-net-device,netdev=net0"])

        # GDB
        if cfg.gdb_port:
            cmd.extend(["-gdb", f"tcp::{cfg.gdb_port}", "-S"])

        # KVM
        if cfg.enable_kvm:
            cmd.append("-enable-kvm")

        # Extra args
        cmd.extend(cfg.extra_args)

        return cmd

    def start(self) -> bool:
        """Start the Linux board emulator."""
        cmd = self._build_qemu_cmd()

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.running = True

            # Parse PTY path from QEMU stderr
            if self.config.uart_mode == "pty":
                self._uart_pty_path = self._detect_pty()
                if self._uart_pty_path:
                    self._uart_pty_master = os.open(self._uart_pty_path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
                    self._uart_reader = threading.Thread(target=self._read_uart_pty, daemon=True)
                    self._uart_reader.start()
            else:
                time.sleep(0.5)
                self._connect_uart_tcp()

            return True

        except FileNotFoundError:
            arch = self.profile.arch
            raise RuntimeError(
                f"qemu-system-{arch} not found. Install with: brew install qemu"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start Linux board emulator: {e}")

    def _detect_pty(self) -> Optional[str]:
        """Parse PTY path from QEMU stderr output."""
        if not self.process or not self.process.stderr:
            return None

        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                line = self.process.stderr.readline()
                if "char device redirected to" in line:
                    # e.g. "char device redirected to /dev/pts/3 (label serial0)"
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "to" and i + 1 < len(parts):
                            return parts[i + 1]
            except Exception:
                break
            time.sleep(0.05)

        return None

    def _connect_uart_tcp(self):
        """Connect to UART via TCP."""
        try:
            self._uart_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._uart_socket.connect(("127.0.0.1", self.config.uart_tcp_port))
            self._uart_socket.settimeout(0.1)
            self._uart_reader = threading.Thread(target=self._read_uart_tcp, daemon=True)
            self._uart_reader.start()
        except Exception as e:
            print(f"Warning: Could not connect to UART TCP: {e}")

    def _read_uart_pty(self):
        """Read from PTY UART."""
        while self.running and self._uart_pty_master is not None:
            try:
                r, _, _ = select.select([self._uart_pty_master], [], [], 0.1)
                if r:
                    data = os.read(self._uart_pty_master, 1024)
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        self._uart_buffer.append(text)
                        self._check_boot_complete(text)
                        for cb in self._callbacks["uart_rx"]:
                            cb(text)
            except OSError:
                break

    def _read_uart_tcp(self):
        """Read from TCP UART."""
        while self.running and self._uart_socket:
            try:
                data = self._uart_socket.recv(4096)
                if data:
                    text = data.decode("utf-8", errors="replace")
                    self._uart_buffer.append(text)
                    self._check_boot_complete(text)
                    for cb in self._callbacks["uart_rx"]:
                        cb(text)
            except socket.timeout:
                continue
            except Exception:
                break

    def _check_boot_complete(self, text: str):
        """Detect when Linux has booted (login prompt or custom marker)."""
        if not self._booted:
            boot_markers = ["login:", "# ", "$ ", "buildroot login:"]
            for marker in boot_markers:
                if marker in text:
                    self._booted = True
                    for cb in self._callbacks["boot_complete"]:
                        cb()
                    break

    def wait_for_boot(self, timeout: float = 120) -> bool:
        """Block until Linux boot is complete."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._booted:
                return True
            time.sleep(0.5)
        return False

    def send_uart(self, data: str):
        """Send data to UART (e.g., shell commands)."""
        encoded = (data + "\n").encode("utf-8")

        if self._uart_pty_master is not None:
            try:
                os.write(self._uart_pty_master, encoded)
            except OSError as e:
                print(f"UART write error: {e}")
        elif self._uart_socket:
            try:
                self._uart_socket.send(encoded)
            except Exception as e:
                print(f"UART TCP write error: {e}")

    def read_uart(self, timeout: float = 1.0) -> str:
        """Read accumulated UART output."""
        deadline = time.time() + timeout
        result = []

        while time.time() < deadline:
            if self._uart_buffer:
                result.extend(self._uart_buffer)
                self._uart_buffer.clear()
                break
            time.sleep(0.05)

        return "".join(result)

    def run_command(self, cmd: str, timeout: float = 10.0) -> str:
        """Run a shell command via UART and return output."""
        # Clear buffer
        self._uart_buffer.clear()

        # Send command with unique marker
        marker = f"__CMD_DONE_{int(time.time())}__"
        self.send_uart(f"{cmd}; echo {marker}")

        # Collect output until marker
        output = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            chunk = self.read_uart(timeout=0.2)
            if chunk:
                output.append(chunk)
                if marker in chunk:
                    break

        result = "".join(output)
        # Strip the marker and command echo
        if marker in result:
            result = result[:result.index(marker)].strip()
        return result

    def gpio_export(self, pin: int):
        """Export a GPIO pin via sysfs (run on the emulated board)."""
        self.run_command(f"echo {pin} > /sys/class/gpio/export")

    def gpio_set_direction(self, pin: int, direction: str):
        """Set GPIO direction ('in' or 'out')."""
        self.run_command(f"echo {direction} > /sys/class/gpio/gpio{pin}/direction")

    def gpio_write(self, pin: int, value: int):
        """Write to a GPIO pin (0 or 1)."""
        self.run_command(f"echo {value} > /sys/class/gpio/gpio{pin}/value")

    def gpio_read(self, pin: int) -> Optional[int]:
        """Read a GPIO pin value."""
        result = self.run_command(f"cat /sys/class/gpio/gpio{pin}/value")
        try:
            return int(result.strip())
        except ValueError:
            return None

    def stop(self):
        """Stop the emulator."""
        self.running = False

        if self._uart_pty_master is not None:
            try:
                os.close(self._uart_pty_master)
            except OSError:
                pass
            self._uart_pty_master = None

        if self._uart_socket:
            self._uart_socket.close()
            self._uart_socket = None

        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def on_uart_rx(self, callback: Callable[[str], None]):
        """Register callback for UART receive."""
        self._callbacks["uart_rx"].append(callback)

    def on_boot_complete(self, callback: Callable[[], None]):
        """Register callback for boot complete."""
        self._callbacks["boot_complete"].append(callback)

    def get_state(self) -> dict:
        """Get emulator state."""
        return {
            "running": self.running,
            "board": self.config.board.value,
            "booted": self._booted,
            "machine": self.profile.machine,
            "cpu": self.profile.cpu,
            "arch": self.profile.arch,
            "ram_mb": self.config.ram_mb or self.profile.ram_mb,
            "uart_pty": self._uart_pty_path,
            "ssh_port": self._ssh_port,
            "kernel": self.config.kernel_path,
            "rootfs": self.config.rootfs_path,
        }

    @staticmethod
    def check_qemu(arch: str = "aarch64") -> bool:
        """Check if qemu-system-{arch} is installed."""
        try:
            result = subprocess.run(
                [f"qemu-system-{arch}", "--version"],
                capture_output=True, text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False


class LinuxBoardBuilder:
    """Helper to build/manage Linux images for emulation."""

    @staticmethod
    def download_rpi_kernel(output_dir: str = "/tmp/oasis_rpi") -> dict[str, str]:
        """Download a pre-built QEMU-compatible RPi kernel.

        Uses the widely-used dhruvvyas90/qemu-rpi-kernel project.
        Returns paths to kernel and dtb files.
        """
        import urllib.request
        import urllib.error

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        base_url = "https://github.com/dhruvvyas90/qemu-rpi-kernel/raw/master"
        files = {
            "kernel": ("kernel-qemu-5.10.63-bullseye", f"{output_dir}/kernel-qemu"),
            "dtb": ("versatile-pb-bullseye-5.10.63.dtb", f"{output_dir}/versatile-pb.dtb"),
        }

        paths = {}
        for key, (filename, dest) in files.items():
            dest_path = Path(dest)
            if not dest_path.exists():
                url = f"{base_url}/{filename}"
                print(f"Downloading {filename}...")
                try:
                    urllib.request.urlretrieve(url, dest)
                    paths[key] = dest
                except urllib.error.URLError as e:
                    raise RuntimeError(f"Failed to download {filename}: {e}")
            else:
                paths[key] = dest

        return paths

    @staticmethod
    def create_minimal_rootfs(output_path: str, size_mb: int = 256) -> str:
        """Create a minimal ext4 rootfs for testing (no actual OS, just filesystem)."""
        output = Path(output_path)

        # Create empty image
        subprocess.run(["dd", "if=/dev/zero", f"of={output}", "bs=1M", f"count={size_mb}"],
                       check=True, capture_output=True)
        subprocess.run(["mkfs.ext4", str(output)], check=True, capture_output=True)

        return str(output.absolute())

    @staticmethod
    def check_kernel_available(kernel_path: str) -> bool:
        """Check if a kernel image exists."""
        return Path(kernel_path).exists()
