# Simulation fixtures

Two small firmware images. Each one writes known text to its serial port
(UART) and then stops. A test passes when the simulator prints that text.
The fixtures prove the simulator path before generated firmware is in the
loop.

| Fixture | Chip | Simulator | Expected UART text |
|---------|------|-----------|--------------------|
| `avr_uno_serial/` | ATmega328P (Arduino Uno) | simavr | `tick 0` to `tick 5`, one per line |
| `stm32f103_usart/` | STM32F103 (Blue Pill) | Renode | `oasis f103 hello` on USART1 |

## Arduino Uno (simavr)

Needs `arduino-cli` with the `arduino:avr` core, and `simavr`.

```bash
arduino-cli compile --fqbn arduino:avr:uno --output-dir build/uno simulation/fixtures/avr_uno_serial
simavr -m atmega328p -f 16000000 build/uno/avr_uno_serial.ino.elf
```

simavr prints UART0 output on stdout, one line at a time, in ANSI green.
A carriage return and a line feed show as `..` at the end of each line.
The firmware stops in a loop, so simavr does not exit. Stop simavr with a
signal after the expected text arrives.

## STM32F103 (Renode)

Needs Rust with the `thumbv7m-none-eabi` target, and Renode (tested with
v1.16.1).
The fixture has no crate dependencies. `link.x` is a minimal linker script
(vector table: stack pointer and reset handler only).

```bash
cd simulation/fixtures/stm32f103_usart
cargo build --release
renode --disable-gui --plain \
  -e '$elf=@target/thumbv7m-none-eabi/release/stm32f103_usart; $out=@/tmp/uart.txt; include @stm32f103_usart.resc'
cat /tmp/uart.txt
```

Renode runs `-e` commands after a script given as a positional argument.
Set the variables first and include the script last, as shown. Renode runs
0.2 s of simulated time and exits. Renode logs two warnings for the
unimplemented `RCC:APB2ENR` register. The warnings are expected.

## Results on the first run (2026-11-20, macOS 15, Apple M4 Max)

- simavr (Homebrew build at `/usr/local/bin/simavr`): `tick 0` to `tick 5`.
- Renode v1.16.1.16858: `oasis f103 hello`. Wall time 2 to 3 s.
