"""MCU Emulator Wrappers for Oasis Simulation."""

from .orchestrator import (
    EmulatorOrchestrator,
    OrchestratorConfig,
    Platform,
    GpioMapping,
    UartMapping,
    create_orchestrator_from_device_yaml,
)
from .linux import (
    LinuxBoardEmulator,
    LinuxBoardConfig,
    LinuxBoard,
    BOARD_PROFILES,
)
from .comms import (
    SerialBus,
    I2CBus,
    NetworkBus,
    MultiBoardOrchestrator,
    BoardLink,
    LinkType,
)

__all__ = [
    # MCU emulators
    "EmulatorOrchestrator",
    "OrchestratorConfig",
    "Platform",
    "GpioMapping",
    "UartMapping",
    "create_orchestrator_from_device_yaml",
    # Linux/SBC emulators
    "LinuxBoardEmulator",
    "LinuxBoardConfig",
    "LinuxBoard",
    "BOARD_PROFILES",
    # Inter-board communication
    "SerialBus",
    "I2CBus",
    "NetworkBus",
    "MultiBoardOrchestrator",
    "BoardLink",
    "LinkType",
]
