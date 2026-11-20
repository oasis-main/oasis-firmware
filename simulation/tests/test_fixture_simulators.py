"""Run the fixture firmware in the stock simulators.

Each test builds a fixture from simulation/fixtures/, runs it in the
simulator through the Python wrapper, and checks the UART text. A test is
skipped when a tool it needs is not installed.

    cd simulation
    pytest tests/test_fixture_simulators.py -v
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from emulators.renode.wrapper import (  # noqa: E402
    RenodeConfig, RenodeEmulator, RenodeBuilder, Stm32Mcu, batch_script, quote, run_for as renode_run_for,
)
from emulators.simavr.wrapper import (  # noqa: E402
    AvrMcu, SimavrConfig, SimavrEmulator, parse_uart_line, run_for as simavr_run_for,
)

FIXTURES = ROOT / "fixtures"
EXPECTED_AVR = [f"tick {n}" for n in range(6)]
EXPECTED_STM32 = "oasis f103 hello"


# ---------------------------------------------------------------- unit tests

def test_parse_uart_line_strips_color_and_crlf_marker():
    assert parse_uart_line("\x1b[32mtick 0..\x1b[0m\n") == "tick 0"
    assert parse_uart_line("\x1b[32mno newline\x1b[0m\n") == "no newline"
    assert parse_uart_line("Loaded 2128 bytes of Flash data at 0\n") is None


def test_parse_uart_line_reads_simavr_1_6_stderr_form():
    # simavr 1.6 (Ubuntu 22.04) writes the color reset at the start of the
    # next line: "ESC[32mtick 0..\nESC[0mESC[32mtick 1..\nESC[0m".
    assert parse_uart_line("\x1b[32mtick 0..\n") == "tick 0"
    assert parse_uart_line("\x1b[0m\x1b[32mtick 1..\n") == "tick 1"
    assert parse_uart_line("\x1b[0m") is None


def test_simavr_command_is_an_argument_list(tmp_path):
    fw = tmp_path / "fw with space.elf"
    fw.write_bytes(b"\x7fELF")
    emu = SimavrEmulator(SimavrConfig(mcu=AvrMcu.ATMEGA328P, simavr_path="simavr"))
    emu.load_firmware(str(fw))
    assert emu.command() == ["simavr", "-m", "atmega328p", "-f", "16000000", str(fw)]


def test_simavr_input_is_refused():
    emu = SimavrEmulator(SimavrConfig())
    assert emu.supports_gpio_input is False
    with pytest.raises(NotImplementedError):
        emu.set_gpio("B", 5, True)


def test_renode_quote_allows_spaces_and_refuses_quotes():
    assert quote("/a b/fw.elf") == '"/a b/fw.elf"'
    with pytest.raises(ValueError):
        quote('/a"b/fw.elf')
    with pytest.raises(ValueError):
        quote("/a\nb")


def test_renode_batch_script_has_no_duplicate_gpio():
    script = batch_script(Stm32Mcu.STM32F103, "/x/fw.elf", "usart1", "/x/out.txt", 0.2)
    assert "LoadPlatformDescriptionFromString" not in script
    assert "@platforms/cpus/stm32f103.repl" in script
    assert 'sysbus LoadELF "/x/fw.elf"' in script
    assert script.rstrip().endswith("quit")


# ------------------------------------------------------------ fixture builds

def _need(*tools):
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        pytest.skip(f"not installed: {', '.join(missing)}")


@pytest.fixture(scope="session")
def avr_elf(tmp_path_factory):
    _need("arduino-cli", "simavr")
    out = tmp_path_factory.mktemp("uno")
    result = subprocess.run(
        ["arduino-cli", "compile", "--fqbn", "arduino:avr:uno", "--output-dir", str(out),
         str(FIXTURES / "avr_uno_serial")],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"arduino-cli compile failed (is the arduino:avr core installed?): {result.stderr[-500:]}")
    return out / "avr_uno_serial.ino.elf"


@pytest.fixture(scope="session")
def stm32_elf():
    _need("cargo")
    if not RenodeBuilder.check_renode():
        pytest.skip("not installed: renode")
    try:
        return Path(RenodeBuilder.compile_cargo(str(FIXTURES / "stm32f103_usart")))
    except RuntimeError as e:
        pytest.skip(f"fixture build failed (is the thumbv7m-none-eabi target installed?): {e}")


# ------------------------------------------------------------- simulator runs

def test_simavr_runs_uno_fixture(avr_elf):
    lines = simavr_run_for(
        SimavrConfig(mcu=AvrMcu.ATMEGA328P, firmware_path=str(avr_elf)),
        seconds=10,
        until=lambda got: len(got) >= len(EXPECTED_AVR),
    )
    assert lines[: len(EXPECTED_AVR)] == EXPECTED_AVR


def test_simavr_emulator_stops_cleanly(avr_elf):
    emu = SimavrEmulator(SimavrConfig(firmware_path=str(avr_elf)))
    emu.start()
    try:
        assert emu.read_uart(timeout=5) == "tick 0"
    finally:
        emu.stop()
    assert emu.process is None
    assert any("Loaded" in line for line in emu.log)


def test_renode_batch_runs_f103_fixture(stm32_elf):
    text = renode_run_for(
        RenodeConfig(platform=Stm32Mcu.STM32F103, firmware_path=str(stm32_elf)), seconds=0.2,
    )
    assert EXPECTED_STM32 in text


def test_renode_batch_accepts_path_with_space(stm32_elf, tmp_path):
    spaced = tmp_path / "dir with space"
    spaced.mkdir()
    fw = spaced / "fw.elf"
    fw.write_bytes(stm32_elf.read_bytes())
    text = renode_run_for(RenodeConfig(firmware_path=str(fw)), seconds=0.2)
    assert EXPECTED_STM32 in text


def test_renode_interactive_gets_boot_uart(stm32_elf):
    received: list[str] = []
    emu = RenodeEmulator(RenodeConfig(platform=Stm32Mcu.STM32F103))
    emu.load_firmware(str(stm32_elf))
    emu.on_uart_rx(received.append)
    emu.start()
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and EXPECTED_STM32 not in "".join(received):
            time.sleep(0.1)
        emu.set_gpio("A", 3, True)
        assert emu.get_gpio("A", 3) is True
        assert emu.get_gpio("A", 4) is False
    finally:
        emu.stop()
    assert EXPECTED_STM32 in "".join(received)
