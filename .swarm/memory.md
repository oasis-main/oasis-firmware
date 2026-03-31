# Memory — oasis-firmware

Append-only. Non-obvious decisions, constraints, and rationale.
Format: `## <ISO8601-date> — <topic> (<agent-id>)`

---

## 2026-03-31 — legacy submodule absorption into codegen (windsurf)

`rusty_pins` and `rusty_pipes` were PyO3-bridged Rust crates (now deleted from master).
Their patterns have been absorbed into `oasis-rpi/src/codegen/rpi.rs` as pure Rust codegen:

| Legacy pattern | New home | Mechanism |
|---|---|---|
| `rusty_pins.GpioOut` (set_high/set_low) | `generate_actuators_module` | rppal 0.17 `OutputPin` per ActuatorType |
| `rusty_pins.GpioIn` (debounce VecDeque) | `generate_sensors_module` | VecDeque sliding window per SensorType |
| `rusty_pipes.Open` (subprocess) | `generate_serial_module` | tokio_serial async task, COBS/JSON framing |
| `rusty_pipes.custom_signal` (JSON file IPC) | `generate_mqtt_module` | MQTT topics as IPC primitive |
| `rusty_pipes.fast_mutx` (JSON file mutex) | `generate_mqtt_module` | `Arc<Mutex<HashMap<topic, Vec<cmd>>>>` |
| `#[pyclass(unsendable)]` GPIO singleton | `generate_main_rs` | `Arc<Gpio>` shared across async tasks |

Key constraint: rppal 0.17 `Gpio` is `Send + Sync` when wrapped in `Arc`.
The `#[pyclass(unsendable)]` anti-pattern is fully eliminated.

---

## 2026-03-31 — legacy/rpi deprecation rationale (windsurf)

`oasis-rpi/legacy/rpi/` contained 6 open Dependabot security vulnerabilities:
- `protobuf==3.20.*` — JSON recursion depth bypass (High) + DoS (High)
- `requests<=2.20.0` — Session verify=False bypass (Moderate), .netrc credential leak (Moderate), insecure temp file reuse in extract_zipped_paths() (Moderate)
- `pyo3==0.16.4` (rusty_pins/Cargo.toml) — PyString::from_object buffer overflow (Low)

Decision: snapshot master → prod branch (preserving legacy at a known state), then delete
`legacy/rpi/` from master entirely. `legacy/ino/` is unaffected and left in place.
The legacy RPi Python code is not used by any current service — it predates the Rust rewrite.
Deprecation is safe; no downstream consumers identified.
