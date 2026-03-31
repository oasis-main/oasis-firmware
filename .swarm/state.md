# State — oasis-firmware

**Last touched**: 2026-03-31T22:09Z by windsurf
**Current focus**: FW-001 — firmware repo cleanup and documentation
**Active items**: (none)
**Blockers**: None
**Ready for pickup**: FW-001, FW-002

---

## Handoff Note

Session 2026-03-31 (windsurf) — legacy submodule absorption:

**What was done:**
- FW-005: Absorbed `rusty_pins` + `rusty_pipes` legacy patterns into `oasis-rpi/src/codegen/rpi.rs`
- `generate_sensors_module`: per-SensorType tokio tasks using rppal 0.17; VecDeque debounce window
  mirrors rusty_pins.GpioIn mode-tracking (PIR, moisture/ADC). I2C, 1-Wire, camera also covered.
- `generate_actuators_module`: per-ActuatorType rppal OutputPin tasks; watchdog safety timer
  replaces rusty_pipes fast_mutx resource locking for actuator safety.
- `generate_mqtt_module`: MqttClient struct with `poll_cmd()` queue backed by tokio HashMap;
  replaces rusty_pipes.custom_signal (JSON file IPC) and fast_mutx (JSON file mutex) entirely.
- `generate_serial_module`: tokio_serial async task with COBS/newline framing;
  replaces rusty_pipes.Open subprocess wrapper — no child processes, no pid files.
- `generate_main_rs`: Arc<Gpio> + Arc<Mutex<MqttClient>> threaded through all modules;
  replaces rusty_pins #[pyclass(unsendable)] single-thread constraint.
- `cargo check` → 0 errors, 0 warnings.

**Next priorities:**
1. FW-001 — firmware repo cleanup and documentation (mirrors ORG-019)
2. FW-002 — install swarm-drift-check GH Actions workflow
