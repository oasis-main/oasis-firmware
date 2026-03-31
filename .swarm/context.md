# Context — oasis-firmware

**Level**: Division
**Division code**: FW
**Last updated**: 2026-03-26

## What This Division Is

IoT device firmware generation and simulation for Oasis hardware devices. Firmware is written
in Rust; simulation environments use Python with QEMU and Renode. Targets embedded systems
in the Oasis grow hardware ecosystem.

## Architecture Constraints

1. Firmware written in Rust — strong typing and memory safety requirements.
2. Hardware simulation via QEMU/Renode — all firmware changes should pass simulation before hardware deployment.
3. No networked secrets in firmware — device credentials provisioned at manufacture time.
4. Repository is not yet a git repo — initialize before pushing.

## Current Focus Areas

1. SwarmCity bootstrap complete — ready for work items.

## Key Technologies

- Rust (embedded, no_std), QEMU, Renode, Python (simulation tooling)
