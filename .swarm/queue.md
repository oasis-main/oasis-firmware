# Queue — oasis-firmware (Organization Level)

Items are listed in priority order within each section.
Item IDs: `<DIVISION-CODE>-<3-digit-number>` — assigned sequentially, never reused.

---

## Active

## Pending

- [ ] [FW-001] [OPEN] oasis-firmware: clean up, link repos with code & tutorials (see also ORG-019)
      priority: medium | project: cleanup
      notes: Mirrors ORG-019. Consolidate oasis-core, oasis-rpi, oasis-ino, oasis-mcu into documented structure.

- [ ] [FW-002] [OPEN] Install swarm-drift-check GitHub Actions workflow
      priority: low | project: swarm-city-bootstrap
      notes: Run: swarm setup-drift-check --commit (requires gh CLI + AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY secrets in repo)

## Done

- [x] [FW-005] [DONE · windsurf · 2026-03-31T22:09Z] Absorb legacy rusty_pins + rusty_pipes into composability codegen
      notes: All 4 stub functions in `oasis-rpi/src/codegen/rpi.rs` replaced with config-driven codegen:
             - `generate_sensors_module`: per-SensorType rppal 0.17 tasks, VecDeque debounce (from GpioIn)
             - `generate_actuators_module`: per-ActuatorType OutputPin tasks, watchdog safety (from GpioOut)
             - `generate_mqtt_module`: MqttClient struct with poll_cmd queue (replaces fast_mutx JSON locks)
             - `generate_serial_module`: tokio_serial async bridge w/ COBS/JSON framing (replaces rusty_pipes.Open)
             - `generate_main_rs`: Arc<Gpio> + Arc<Mutex<MqttClient>> wired through all modules
             `cargo check` passes with 0 warnings.

- [x] [FW-004] [DONE · windsurf · 2026-03-31T21:05Z] Remove legacy/rpi from master branch (security deprecation)
      notes: `git rm -r legacy/rpi/` — 94 files, 8337 deletions. Committed as d9670549, pushed to origin/master.
             All 6 Dependabot vulnerabilities removed from dev branch. legacy/ino/ retained.

- [x] [FW-003] [DONE · windsurf · 2026-03-31T21:05Z] Snapshot legacy/rpi to prod branch before deprecation
      notes: Created prod branch from master (7798ca60) and pushed to origin/prod.
             Legacy code preserved at known state on oasis-main/oasis-firmware:prod.
