//! End-to-end flash runs with fake flash programs.
//!
//! This file is its own test process, so the test can set PATH before the
//! app looks up a program. Each fake program writes its arguments to a log
//! file, one line for each call. No real board, probe, or Pi is touched.

#![cfg(unix)]

use oasis_studio_core::flash::{FlashLine, PlanRequest, RunRequest};
use oasis_studio_core::registry::{IdentityKind, NewDevice};
use oasis_studio_core::{Actor, Paths, Studio};
use std::os::unix::fs::PermissionsExt;
use std::path::Path;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};

fn fake(dir: &Path, name: &str, calls: &Path, body: &str) {
    let p = dir.join(name);
    let script = format!(
        "#!/bin/sh\nprintf '%s' '{name}' >> '{log}'\nfor a in \"$@\"; do printf ' [%s]' \"$a\" >> '{log}'; done\necho >> '{log}'\n{body}\nexit 0\n",
        log = calls.display()
    );
    std::fs::write(&p, script).unwrap();
    std::fs::set_permissions(&p, std::fs::Permissions::from_mode(0o755)).unwrap();
}

fn own(studio: &Studio, kind: IdentityKind, identity: &str, family: &str) {
    studio
        .registry_add(NewDevice { name: format!("bench {family}"), identity_kind: kind, identity: identity.into(), family: Some(family.into()), notes: String::new(), owned: true })
        .unwrap();
}

#[test]
fn person_flashes_an_uno_and_a_pi_with_fake_tools() {
    let tmp = tempfile::tempdir().unwrap();
    let bin = tmp.path().join("bin");
    std::fs::create_dir_all(&bin).unwrap();
    let calls = tmp.path().join("calls.txt");
    // avrdude: a read (flash:r:<file>:i) writes a small Intel HEX file.
    fake(&bin, "avrdude", &calls, r#"for a in "$@"; do case "$a" in flash:r:*) f=${a#flash:r:}; f=${f%:i}; echo ':00000001FF' > "$f";; esac; done; echo 'avrdude done' >&2"#);
    fake(&bin, "ssh", &calls, "echo 'remote ok'");
    fake(&bin, "scp", &calls, "");
    fake(&bin, "espflash", &calls, "echo 'Flashing has completed!'");
    fake(&bin, "probe-rs", &calls, "echo 'Finished in 1.0s'");
    // Only the fake programs and the system folders, so a real avrdude or ssh
    // on this computer is never found first.
    std::env::set_var("PATH", format!("{}:/usr/bin:/bin", bin.display()));

    let studio = Studio::new(Paths { data_dir: tmp.path().join("data"), projects_dir: tmp.path().join("projects") });
    own(&studio, IdentityKind::UsbSerial, "UNO-0001", "avr_uno");
    own(&studio, IdentityKind::Hostname, "pi4.local", "rpi");
    own(&studio, IdentityKind::UsbSerial, "ESP-7C:DF", "esp32");
    own(&studio, IdentityKind::ProbeId, "066DFF485457", "stm32");

    let fw = tmp.path().join("blink.hex");
    std::fs::write(&fw, ":00000001FF\n").unwrap();
    let pi_bin = tmp.path().join("greenhouse-01-supervisor");
    std::fs::write(&pi_bin, b"\x7fELF fake").unwrap();

    let lines: Arc<Mutex<Vec<FlashLine>>> = Arc::new(Mutex::new(Vec::new()));
    let sink = lines.clone();
    let emit = Arc::new(move |l: FlashLine| sink.lock().unwrap().push(l));

    // ---- Arduino Uno: backup, then write.
    let uno = PlanRequest {
        port: "/dev/cu.usbmodem1101".into(),
        family: "avr_uno".into(),
        artifact: fw.to_string_lossy().into(),
        usb_serial: Some("UNO-0001".into()),
        usb_vid: Some(0x2341),
        usb_pid: Some(0x0043),
        device_id: None,
    };
    let plan = studio.flash_plan(&uno, Actor::User);
    assert!(plan.blockers.is_empty(), "{:?}", plan.blockers);
    let sha = plan.artifact_sha256.clone().unwrap();

    // A wrong hash (the file changed after the confirm dialog) is refused.
    let err = studio.flash_begin(&RunRequest { plan: uno.clone(), expected_sha256: "00".into(), allow_no_backup: false }, Actor::User, Arc::new(AtomicBool::new(false)));
    assert!(err.err().unwrap().contains("changed"));

    let ticket = studio.flash_begin(&RunRequest { plan: uno, expected_sha256: sha.clone(), allow_no_backup: false }, Actor::User, Arc::new(AtomicBool::new(false))).unwrap();
    let done = studio.flash_execute(ticket, emit.clone());
    assert!(done.ok, "{done:?}");
    let backup = done.backup_file.clone().unwrap();
    assert!(backup.contains("/backups/") && backup.ends_with(".hex"));
    assert_eq!(std::fs::read_to_string(&backup).unwrap().trim(), ":00000001FF");

    // ---- Raspberry Pi: backup, write, install, restart, verify over SSH.
    let pi = PlanRequest {
        port: "oasis@pi4.local".into(),
        family: "rpi".into(),
        artifact: pi_bin.to_string_lossy().into(),
        usb_serial: None,
        usb_vid: None,
        usb_pid: None,
        device_id: Some("greenhouse-01".into()),
    };
    let plan = studio.flash_plan(&pi, Actor::User);
    assert!(plan.blockers.is_empty(), "{:?}", plan.blockers);
    let ticket = studio
        .flash_begin(&RunRequest { plan: pi, expected_sha256: plan.artifact_sha256.unwrap(), allow_no_backup: false }, Actor::User, Arc::new(AtomicBool::new(false)))
        .unwrap();
    let done = studio.flash_execute(ticket, emit.clone());
    assert!(done.ok, "{done:?}");
    assert_eq!(done.steps.iter().map(|s| s.name.as_str()).collect::<Vec<_>>(), ["backup", "write", "install", "restart", "verify"]);
    assert_eq!(done.backup_file.as_deref(), Some("on the Pi: /opt/oasis/greenhouse-01/greenhouse_01-supervisor.bak"));

    // Each program got the exact argument list.
    let calls = std::fs::read_to_string(&calls).unwrap();
    let calls: Vec<&str> = calls.lines().collect();
    assert_eq!(calls.len(), 7, "{calls:#?}");
    assert!(calls[0].starts_with("avrdude ") && calls[0].contains("[flash:r:") && calls[0].contains("[-P] [/dev/cu.usbmodem1101]"));
    assert!(calls[1].starts_with("avrdude ") && calls[1].contains(&format!("[flash:w:{}:i]", fw.display())));
    let opts = "[-o] [BatchMode=yes] [-o] [StrictHostKeyChecking=yes] [-o] [ConnectTimeout=10] [--]";
    assert_eq!(calls[2], format!("ssh {opts} [oasis@pi4.local] [if [ -f /opt/oasis/greenhouse-01/greenhouse_01-supervisor ]; then cp -p /opt/oasis/greenhouse-01/greenhouse_01-supervisor /opt/oasis/greenhouse-01/greenhouse_01-supervisor.bak; fi]"));
    assert_eq!(calls[3], format!("scp {opts} [{}] [oasis@pi4.local:/opt/oasis/greenhouse-01/greenhouse_01-supervisor.new]", pi_bin.display()));
    assert!(calls[4].ends_with("[mv /opt/oasis/greenhouse-01/greenhouse_01-supervisor.new /opt/oasis/greenhouse-01/greenhouse_01-supervisor && chmod 755 /opt/oasis/greenhouse-01/greenhouse_01-supervisor]"));
    assert!(calls[5].ends_with("[sudo -n systemctl restart greenhouse_01.service]"));
    assert!(calls[6].ends_with("[systemctl is-active --quiet greenhouse_01.service]"));

    // ---- ESP32 and STM32: no backup method yet, so the person must accept
    // a flash with no backup.
    let esp_fw = tmp.path().join("esp.elf");
    std::fs::write(&esp_fw, b"\x7fELF esp").unwrap();
    let stm_fw = tmp.path().join("stm.elf");
    std::fs::write(&stm_fw, b"\x7fELF stm").unwrap();
    let local = |family: &str, port: &str, fw: &Path, serial: &str, vid: u16, pid: u16| PlanRequest {
        port: port.into(),
        family: family.into(),
        artifact: fw.to_string_lossy().into(),
        usb_serial: Some(serial.into()),
        usb_vid: Some(vid),
        usb_pid: Some(pid),
        device_id: None,
    };
    for req in [
        local("esp32", "/dev/cu.usbserial-10", &esp_fw, "ESP-7C:DF", 0x10C4, 0xEA60),
        local("stm32", "/dev/cu.usbmodem2", &stm_fw, "066DFF485457", 0x0483, 0x374B),
    ] {
        let plan = studio.flash_plan(&req, Actor::User);
        assert!(plan.blockers.is_empty(), "{}: {:?}", req.family, plan.blockers);
        assert!(plan.backup_method.is_none());
        let sha = plan.artifact_sha256.unwrap();
        let refused = studio.flash_begin(&RunRequest { plan: req.clone(), expected_sha256: sha.clone(), allow_no_backup: false }, Actor::User, Arc::new(AtomicBool::new(false)));
        assert!(refused.err().unwrap().contains("no backup method"));
        let ticket = studio.flash_begin(&RunRequest { plan: req, expected_sha256: sha, allow_no_backup: true }, Actor::User, Arc::new(AtomicBool::new(false))).unwrap();
        let done = studio.flash_execute(ticket, emit.clone());
        assert!(done.ok, "{done:?}");
        assert!(done.backup_file.is_none());
    }
    let all = std::fs::read_to_string(tmp.path().join("calls.txt")).unwrap();
    let all: Vec<&str> = all.lines().collect();
    assert_eq!(all.len(), 9, "{all:#?}");
    assert_eq!(all[7], format!("espflash [flash] [--port] [/dev/cu.usbserial-10] [{}]", esp_fw.display()));
    assert_eq!(all[8], format!("probe-rs [download] [--probe] [0483:374b:066DFF485457] [--verify] [--chip] [STM32F103C8] [{}]", stm_fw.display()));

    // The output reached the app, and the action log has all four runs.
    let lines = lines.lock().unwrap();
    assert!(lines.iter().any(|l| l.step == "write" && l.stream == "stderr" && l.text == "avrdude done"));
    assert!(lines.iter().any(|l| l.step == "verify" && l.stream == "stdout" && l.text == "remote ok"));
    let runs: Vec<_> = studio.audit_tail(50).into_iter().filter(|e| e.action == "flash.run").collect();
    // Four runs that wrote, plus three refused requests (the wrong hash and
    // the two missing backup approvals) that did not take the slot.
    assert_eq!(runs.len(), 4, "{runs:?}");
    assert!(runs.iter().all(|e| e.actor == "user" && e.result.starts_with("ok")));
    assert!(runs.iter().any(|e| e.target.contains(&format!("sha256:{}", &sha[..16]))));
}
