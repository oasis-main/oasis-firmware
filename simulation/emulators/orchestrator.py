"""Emulator Orchestrator - Unified interface for all MCU emulators.

Bridges MCU emulators with behavioral component models via a shared signal bus.
Handles time synchronization, GPIO routing, and peripheral simulation.
"""

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union
from pathlib import Path

from .simavr.wrapper import SimavrEmulator, SimavrConfig, AvrMcu
from .renode.wrapper import RenodeEmulator, RenodeConfig, Stm32Mcu
from .esp32.wrapper import Esp32Emulator, Esp32Config, Esp32Variant, EmulationBackend

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from behavioral import BehavioralRuntime, SignalBus, SignalType


class Platform(Enum):
    """Supported MCU platforms."""
    ARDUINO_UNO = "arduino_uno"
    ARDUINO_MEGA = "arduino_mega"
    STM32F103 = "stm32f103"
    STM32F401 = "stm32f401"
    STM32F407 = "stm32f407"
    ESP32 = "esp32"
    ESP32_S3 = "esp32s3"
    ESP32_C3 = "esp32c3"


@dataclass
class GpioMapping:
    """Maps MCU GPIO to behavioral component signals."""
    mcu_port: str  # e.g., "D", "B", "GPIOA"
    mcu_pin: int
    component_id: str
    signal_name: str
    direction: str  # "input" or "output"


@dataclass
class UartMapping:
    """Maps MCU UART to behavioral component or external."""
    uart_id: int  # 0, 1, 2...
    component_id: Optional[str]  # None for external/debug
    baud_rate: int = 115200


@dataclass  
class OrchestratorConfig:
    """Configuration for the emulator orchestrator."""
    platform: Platform
    firmware_path: str
    gpio_mappings: list[GpioMapping] = field(default_factory=list)
    uart_mappings: list[UartMapping] = field(default_factory=list)
    step_size_us: int = 1000  # Simulation step size in microseconds
    realtime: bool = False  # Run at real-time speed


class EmulatorOrchestrator:
    """Orchestrates MCU emulation with behavioral models."""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self._emulator: Optional[Union[SimavrEmulator, RenodeEmulator, Esp32Emulator]] = None
        self._behavioral_runtime: Optional[BehavioralRuntime] = None
        self._signal_bus: Optional[SignalBus] = None
        self._running = False
        self._paused = False
        self._sim_time_us = 0
        self._step_thread: Optional[threading.Thread] = None
        self._callbacks: dict[str, list[Callable]] = {
            "step": [],
            "gpio_change": [],
            "uart_rx": [],
            "error": [],
        }
        
        self._setup_emulator()
    
    def _setup_emulator(self):
        """Initialize the appropriate emulator based on platform."""
        platform = self.config.platform
        
        if platform in [Platform.ARDUINO_UNO, Platform.ARDUINO_MEGA]:
            mcu = AvrMcu.ATMEGA328P if platform == Platform.ARDUINO_UNO else AvrMcu.ATMEGA2560
            config = SimavrConfig(mcu=mcu)
            self._emulator = SimavrEmulator(config)
            
        elif platform in [Platform.STM32F103, Platform.STM32F401, Platform.STM32F407]:
            mcu_map = {
                Platform.STM32F103: Stm32Mcu.STM32F103,
                Platform.STM32F401: Stm32Mcu.STM32F401,
                Platform.STM32F407: Stm32Mcu.STM32F407,
            }
            config = RenodeConfig(platform=mcu_map[platform])
            self._emulator = RenodeEmulator(config)
            
        elif platform in [Platform.ESP32, Platform.ESP32_S3, Platform.ESP32_C3]:
            variant_map = {
                Platform.ESP32: Esp32Variant.ESP32,
                Platform.ESP32_S3: Esp32Variant.ESP32_S3,
                Platform.ESP32_C3: Esp32Variant.ESP32_C3,
            }
            config = Esp32Config(variant=variant_map[platform])
            self._emulator = Esp32Emulator(config)
        else:
            raise ValueError(f"Unsupported platform: {platform}")
        
        # Load firmware
        self._emulator.load_firmware(self.config.firmware_path)
        
        # Set up callbacks
        self._emulator.on_uart_rx(self._on_emulator_uart_rx)
    
    def set_behavioral_runtime(self, runtime: BehavioralRuntime):
        """Connect behavioral runtime for component simulation."""
        self._behavioral_runtime = runtime
        self._signal_bus = runtime.signal_bus
    
    def start(self) -> bool:
        """Start the orchestrator."""
        if not self._emulator:
            raise RuntimeError("Emulator not configured")
        
        # Start MCU emulator
        if not self._emulator.start():
            return False
        
        self._running = True
        self._paused = False
        
        # Start step thread if not realtime
        if not self.config.realtime:
            self._step_thread = threading.Thread(target=self._step_loop, daemon=True)
            self._step_thread.start()
        
        return True
    
    def stop(self):
        """Stop the orchestrator."""
        self._running = False
        
        if self._emulator:
            self._emulator.stop()
    
    def pause(self):
        """Pause simulation."""
        self._paused = True
    
    def resume(self):
        """Resume simulation."""
        self._paused = False
    
    def step(self, duration_us: Optional[int] = None) -> dict:
        """Execute one simulation step."""
        if duration_us is None:
            duration_us = self.config.step_size_us
        
        # 1. Process GPIO mappings: MCU outputs → behavioral inputs
        self._sync_mcu_to_behavioral()
        
        # 2. Step behavioral models
        if self._behavioral_runtime:
            self._behavioral_runtime.step(duration_us // 1000)  # Convert to ms
        
        # 3. Process GPIO mappings: behavioral outputs → MCU inputs
        self._sync_behavioral_to_mcu()
        
        # 4. Update simulation time
        self._sim_time_us += duration_us
        
        # 5. Notify callbacks
        for cb in self._callbacks["step"]:
            cb(self._sim_time_us)
        
        return self.get_state()
    
    def _step_loop(self):
        """Background stepping loop."""
        while self._running:
            if not self._paused:
                self.step()
                
                if self.config.realtime:
                    time.sleep(self.config.step_size_us / 1_000_000)
            else:
                time.sleep(0.01)
    
    def _sync_mcu_to_behavioral(self):
        """Sync GPIO outputs from MCU to behavioral model inputs."""
        if not self._signal_bus or not self._emulator:
            return
        
        for mapping in self.config.gpio_mappings:
            if mapping.direction == "output":
                # MCU is outputting, behavioral model receives
                if hasattr(self._emulator, 'get_gpio'):
                    value = self._emulator.get_gpio(mapping.mcu_port, mapping.mcu_pin)
                    signal_name = f"{mapping.component_id}.{mapping.signal_name}"
                    self._signal_bus.set(
                        signal_name, 
                        1.0 if value else 0.0, 
                        SignalType.DIGITAL,
                        self._sim_time_us // 1000
                    )
    
    def _sync_behavioral_to_mcu(self):
        """Sync behavioral model outputs to MCU GPIO inputs."""
        if not self._signal_bus or not self._emulator:
            return
        
        for mapping in self.config.gpio_mappings:
            if mapping.direction == "input":
                # Behavioral model is outputting, MCU receives
                signal_name = f"{mapping.component_id}.{mapping.signal_name}"
                signal = self._signal_bus.get(signal_name)
                
                if signal and hasattr(self._emulator, 'set_gpio'):
                    value = signal.value > 0.5  # Threshold for digital
                    self._emulator.set_gpio(mapping.mcu_port, mapping.mcu_pin, value)
    
    def _on_emulator_uart_rx(self, data: str):
        """Handle UART data from emulator."""
        for cb in self._callbacks["uart_rx"]:
            cb(data)
        
        # Route to behavioral component if mapped
        for mapping in self.config.uart_mappings:
            if mapping.component_id and self._signal_bus:
                signal_name = f"{mapping.component_id}.uart_rx"
                self._signal_bus.set(
                    signal_name,
                    data,
                    SignalType.UART,
                    self._sim_time_us // 1000
                )
    
    def send_uart(self, data: str, uart_id: int = 0):
        """Send data to MCU UART."""
        if self._emulator and hasattr(self._emulator, 'send_uart'):
            self._emulator.send_uart(data)
    
    def set_gpio(self, port: str, pin: int, value: bool):
        """Set MCU GPIO input."""
        if self._emulator and hasattr(self._emulator, 'set_gpio'):
            self._emulator.set_gpio(port, pin, value)
    
    def get_gpio(self, port: str, pin: int) -> bool:
        """Get MCU GPIO state."""
        if self._emulator and hasattr(self._emulator, 'get_gpio'):
            return self._emulator.get_gpio(port, pin)
        return False
    
    def on_step(self, callback: Callable[[int], None]):
        """Register callback for each simulation step."""
        self._callbacks["step"].append(callback)
    
    def on_uart_rx(self, callback: Callable[[str], None]):
        """Register callback for UART receive."""
        self._callbacks["uart_rx"].append(callback)
    
    def get_state(self) -> dict:
        """Get orchestrator state."""
        state = {
            "running": self._running,
            "paused": self._paused,
            "sim_time_us": self._sim_time_us,
            "sim_time_ms": self._sim_time_us // 1000,
            "platform": self.config.platform.value,
            "emulator": None,
            "behavioral": None,
        }
        
        if self._emulator:
            state["emulator"] = self._emulator.get_state()
        
        if self._behavioral_runtime:
            state["behavioral"] = self._behavioral_runtime.get_state()
        
        return state
    
    def get_sim_time_ms(self) -> int:
        """Get current simulation time in milliseconds."""
        return self._sim_time_us // 1000


def create_orchestrator_from_device_yaml(device_yaml: dict) -> EmulatorOrchestrator:
    """Create orchestrator from device.yaml configuration."""
    device = device_yaml.get("device", {})
    board = device.get("board", {})
    
    # Map board model to platform
    model = board.get("model", "esp32_devkit").lower()
    platform_map = {
        "esp32_devkit": Platform.ESP32,
        "esp32": Platform.ESP32,
        "esp32s3": Platform.ESP32_S3,
        "esp32c3": Platform.ESP32_C3,
        "arduino_uno": Platform.ARDUINO_UNO,
        "arduino_mega": Platform.ARDUINO_MEGA,
        "stm32f103": Platform.STM32F103,
        "stm32f401": Platform.STM32F401,
        "stm32f407": Platform.STM32F407,
        "bluepill": Platform.STM32F103,
    }
    
    platform = platform_map.get(model, Platform.ESP32)
    
    # Extract GPIO mappings from sensors/actuators
    gpio_mappings = []
    
    for sensor in device_yaml.get("sensors", []):
        pins = sensor.get("pins", {})
        for pin_name, pin_num in pins.items():
            gpio_mappings.append(GpioMapping(
                mcu_port="D",  # Default, would need board-specific mapping
                mcu_pin=pin_num,
                component_id=sensor["name"],
                signal_name=pin_name,
                direction="input",  # Sensor outputs to MCU
            ))
    
    for actuator in device_yaml.get("actuators", []):
        pins = actuator.get("pins", {})
        for pin_name, pin_num in pins.items():
            gpio_mappings.append(GpioMapping(
                mcu_port="D",
                mcu_pin=pin_num,
                component_id=actuator["name"],
                signal_name=pin_name,
                direction="output",  # MCU outputs to actuator
            ))
    
    config = OrchestratorConfig(
        platform=platform,
        firmware_path="",  # Must be set separately
        gpio_mappings=gpio_mappings,
    )
    
    return EmulatorOrchestrator(config)
