//! Simulation: run firmware in simavr (AVR) or Renode (STM32) with no board.
//!
//! A simulation touches no hardware, so a run needs no owned-device record.
//! Each run writes one audit record.
//!
//! - simavr prints UART0 lines on stdout in ANSI color. The runner gives
//!   simavr a pty so that the lines arrive while the firmware runs.
//! - Renode runs a script that the app writes into a new run folder. The
//!   script connects the UART to a file. The app reads new bytes from the
//!   file while Renode runs.

use crate::boards::{self, Simulate};
use crate::runner::{self, Exit, Spec, Stream};
use crate::tools;
use serde::{Deserialize, Serialize};
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;

pub const DEFAULT_SECONDS: f64 = 5.0;
pub const MAX_SECONDS: f64 = 600.0;
/// The UI gets at most this many UART lines from one run.
pub const MAX_UART_LINES: usize = 5000;
/// Renode start-up time is not part of the simulated time.
const RENODE_WALL_EXTRA: Duration = Duration::from_secs(60);

#[derive(Debug, Clone, Deserialize)]
pub struct SimRequest {
    pub family: String,
    pub artifact: String,
    #[serde(default)]
    pub seconds: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SimPlan {
    pub family: String,
    pub engine: Option<String>,
    pub engine_path: Option<String>,
    /// Argument list. `{run_dir}` is the run folder, made at start.
    pub args: Vec<String>,
    /// Renode only: the script that the app writes into the run folder.
    pub script: Option<String>,
    pub artifact: String,
    pub artifact_kind: Option<String>,
    pub artifact_sha256: Option<String>,
    pub seconds: f64,
    pub blockers: Vec<String>,
}

/// ELF `e_machine` values that the engines accept.
const EM_ARM: u16 = 40;
const EM_AVR: u16 = 83;

#[derive(Debug, PartialEq, Eq)]
pub enum ArtifactKind {
    Elf { machine: u16 },
    Hex,
    Bin,
}

impl ArtifactKind {
    fn name(&self) -> &'static str {
        match self {
            ArtifactKind::Elf { .. } => "elf",
            ArtifactKind::Hex => "hex",
            ArtifactKind::Bin => "bin",
        }
    }
}

/// Detect the file type from its first bytes, not from its name.
pub fn detect_kind(path: &Path) -> std::io::Result<ArtifactKind> {
    let mut head = [0u8; 20];
    let mut f = std::fs::File::open(path)?;
    let n = f.read(&mut head)?;
    if n >= 20 && head[..4] == *b"\x7fELF" {
        // e_machine is at offset 18. Byte order: e_ident[5] (1 = little endian).
        let machine = if head[5] == 2 {
            u16::from_be_bytes([head[18], head[19]])
        } else {
            u16::from_le_bytes([head[18], head[19]])
        };
        return Ok(ArtifactKind::Elf { machine });
    }
    if n > 0 && head[0] == b':' {
        return Ok(ArtifactKind::Hex);
    }
    Ok(ArtifactKind::Bin)
}

fn machine_name(m: u16) -> String {
    match m {
        EM_ARM => "ARM".into(),
        EM_AVR => "AVR".into(),
        other => format!("machine {other}"),
    }
}

/// Quote a path for a Renode script. Renode accepts spaces inside double
/// quotes. A path with a double quote or a line break is refused.
pub fn renode_quote(path: &str) -> Result<String, String> {
    if path.contains(['"', '\n', '\r']) {
        return Err(format!("Renode cannot load a path that contains a quote or a line break: {path}"));
    }
    Ok(format!("\"{path}\""))
}

pub fn renode_script(sim: &Simulate, artifact: &str, uart_out: &str, seconds: f64) -> Result<String, String> {
    let platform = sim.platform.as_deref().ok_or("family has no Renode platform")?;
    let uart = sim.uart.as_deref().unwrap_or("usart1");
    Ok([
        "mach create \"sim\"".to_string(),
        format!("machine LoadPlatformDescription @{platform}"),
        format!("sysbus LoadELF {}", renode_quote(artifact)?),
        format!("sysbus.{uart} CreateFileBackend {} true", renode_quote(uart_out)?),
        format!("emulation RunFor \"{seconds}\""),
        "quit".to_string(),
        String::new(),
    ]
    .join("\n"))
}

/// The UART text in one stdout line from simavr, or None for other output.
pub fn simavr_uart_line(raw: &str) -> Option<String> {
    if !raw.contains("\x1b[") {
        return None;
    }
    let mut text = String::with_capacity(raw.len());
    let mut chars = raw.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\x1b' && chars.peek() == Some(&'[') {
            chars.next();
            for c2 in chars.by_ref() {
                if c2.is_ascii_alphabetic() {
                    break;
                }
            }
        } else {
            text.push(c);
        }
    }
    let text = text.trim_end_matches(['\r', '\n']);
    Some(text.strip_suffix("..").unwrap_or(text).to_string())
}

pub fn plan(req: &SimRequest) -> SimPlan {
    let seconds = req.seconds.unwrap_or(DEFAULT_SECONDS);
    let mut p = SimPlan {
        family: req.family.clone(),
        engine: None,
        engine_path: None,
        args: vec![],
        script: None,
        artifact: req.artifact.clone(),
        artifact_kind: None,
        artifact_sha256: None,
        seconds,
        blockers: vec![],
    };
    if !(seconds > 0.0 && seconds <= MAX_SECONDS) {
        p.blockers.push(format!("Time limit must be more than 0 s and not more than {MAX_SECONDS} s."));
    }
    let Some(fam) = boards::family(&req.family) else {
        p.blockers.push(format!("Unknown board family \"{}\".", req.family));
        return p;
    };
    let Some(sim) = &fam.simulate else {
        p.blockers.push(format!("The \"{}\" family has no simulator yet.", fam.family));
        return p;
    };
    p.engine = Some(sim.engine.clone());
    p.engine_path = tools::find(&sim.engine).map(|x| x.to_string_lossy().into_owned());
    if p.engine_path.is_none() {
        p.blockers.push(format!("{} is not installed. See the Hardware page for install steps.", sim.engine));
    }

    let artifact = Path::new(&req.artifact);
    if req.artifact.trim().is_empty() {
        p.blockers.push("Choose a firmware file.".into());
    } else if !artifact.is_file() {
        p.blockers.push(format!("Firmware file not found: {}", req.artifact));
    } else {
        p.artifact_sha256 = crate::flash::sha256_file(artifact);
        match detect_kind(artifact) {
            Ok(kind) => {
                p.artifact_kind = Some(kind.name().into());
                if !sim.accepts.iter().any(|a| a == kind.name()) {
                    p.blockers.push(format!(
                        "{} does not accept a .{} file here. Accepted: {}.",
                        sim.engine,
                        kind.name(),
                        sim.accepts.join(", ")
                    ));
                }
                if let (ArtifactKind::Elf { machine }, Some(want)) = (&kind, sim.elf_machine) {
                    if *machine != want {
                        p.blockers.push(format!(
                            "The ELF file is for {}. The \"{}\" family needs {}.",
                            machine_name(*machine),
                            fam.family,
                            machine_name(want)
                        ));
                    }
                }
            }
            Err(e) => p.blockers.push(format!("Cannot read the firmware file: {e}")),
        }
    }

    match sim.engine.as_str() {
        "simavr" => {
            p.args = crate::flash::substitute(&sim.args, "", fam.baud, &req.artifact, fam.chip.as_deref());
        }
        "renode" => {
            // Renode cannot open a script path with a space when the path is a
            // plain argument. `-e include "<path>"` works. `-e` splits at ";".
            p.args = vec!["--disable-xwt".into(), "--plain".into(), "-e".into(), "include \"{run_dir}/run.resc\"".into()];
            match renode_script(sim, &req.artifact, "{run_dir}/uart.txt", seconds) {
                Ok(s) => p.script = Some(s),
                Err(e) => p.blockers.push(e),
            }
        }
        other => p.blockers.push(format!("Unknown simulator engine \"{other}\".")),
    }
    p
}

#[derive(Debug, Clone, Serialize)]
pub struct SimLine {
    pub run_id: String,
    /// "uart" for firmware output, "log" for simulator messages.
    pub kind: &'static str,
    pub text: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct SimDone {
    pub run_id: String,
    pub exit: Exit,
    pub uart_lines: usize,
    pub truncated: bool,
    pub error: Option<String>,
}

/// Run a plan that has no blockers. Blocks until the run ends.
pub fn execute(
    plan: &SimPlan,
    run_id: &str,
    run_dir: &Path,
    stop: Arc<AtomicBool>,
    emit: Arc<dyn Fn(SimLine) + Send + Sync>,
) -> SimDone {
    let uart_count = Arc::new(AtomicUsize::new(0));
    let truncated = Arc::new(AtomicBool::new(false));
    let send_uart = {
        let emit = emit.clone();
        let count = uart_count.clone();
        let truncated = truncated.clone();
        let run_id = run_id.to_string();
        Arc::new(move |text: String| {
            if count.fetch_add(1, Ordering::SeqCst) < MAX_UART_LINES {
                emit(SimLine { run_id: run_id.clone(), kind: "uart", text });
            } else {
                truncated.store(true, Ordering::SeqCst);
            }
        })
    };
    let send_log = {
        let emit = emit.clone();
        let run_id = run_id.to_string();
        move |text: String| emit(SimLine { run_id: run_id.clone(), kind: "log", text })
    };

    let result = (|| -> Result<Exit, String> {
        let engine = plan.engine.as_deref().unwrap_or_default();
        let program = PathBuf::from(plan.engine_path.as_deref().ok_or("simulator not found")?);
        std::fs::create_dir_all(run_dir).map_err(|e| format!("cannot make the run folder: {e}"))?;
        let dir = run_dir.to_string_lossy().into_owned();
        if dir.contains(['"', ';', '\n', '\r']) {
            return Err(format!("the run folder path cannot contain a quote, a semicolon, or a line break: {dir}"));
        }
        let args: Vec<String> = plan.args.iter().map(|a| a.replace("{run_dir}", &dir)).collect();
        let limit = Duration::from_secs_f64(plan.seconds);
        match engine {
            "simavr" => {
                let uart = send_uart.clone();
                let on_line = Arc::new(move |stream: Stream, line: String| match (stream, simavr_uart_line(&line)) {
                    (Stream::Stdout, Some(text)) => uart(text),
                    _ => send_log(line),
                });
                let spec = Spec { program, args, cwd: Some(run_dir.to_path_buf()), limit, pty_stdout: true };
                runner::run(&spec, stop, on_line).map_err(|e| e.to_string())
            }
            "renode" => {
                let script = plan.script.as_deref().ok_or("no Renode script")?.replace("{run_dir}", &dir);
                std::fs::write(run_dir.join("run.resc"), script).map_err(|e| e.to_string())?;
                let uart_file = run_dir.join("uart.txt");
                let done = Arc::new(AtomicBool::new(false));
                let tail = {
                    let done = done.clone();
                    let uart = send_uart.clone();
                    std::thread::spawn(move || tail_lines(&uart_file, &done, |l| uart(l)))
                };
                let on_line = Arc::new(move |_: Stream, line: String| send_log(line));
                let spec = Spec { program, args, cwd: Some(run_dir.to_path_buf()), limit: limit + RENODE_WALL_EXTRA, pty_stdout: false };
                let exit = runner::run(&spec, stop, on_line).map_err(|e| e.to_string());
                done.store(true, Ordering::SeqCst);
                let _ = tail.join();
                exit
            }
            other => Err(format!("unknown engine {other}")),
        }
    })();

    let (exit, error) = match result {
        Ok(e) => (e, None),
        Err(e) => (Exit::Exited { code: None }, Some(e)),
    };
    SimDone {
        run_id: run_id.to_string(),
        exit,
        uart_lines: uart_count.load(Ordering::SeqCst),
        truncated: truncated.load(Ordering::SeqCst),
        error,
    }
}

/// Read new complete lines from a file that another program appends to.
/// Ends after `done` is set and the last bytes are read.
fn tail_lines(path: &Path, done: &AtomicBool, mut on_line: impl FnMut(String)) {
    let mut pos: u64 = 0;
    let mut partial = String::new();
    loop {
        let finished = done.load(Ordering::SeqCst);
        if let Ok(mut f) = std::fs::File::open(path) {
            if f.seek(SeekFrom::Start(pos)).is_ok() {
                let mut buf = Vec::new();
                if let Ok(n) = f.read_to_end(&mut buf) {
                    pos += n as u64;
                    partial.push_str(&String::from_utf8_lossy(&buf));
                    while let Some(i) = partial.find('\n') {
                        let line: String = partial.drain(..=i).collect();
                        on_line(line.trim_end_matches(['\r', '\n']).to_string());
                    }
                }
            }
        }
        if finished {
            break;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    if !partial.is_empty() {
        on_line(partial.trim_end_matches('\r').to_string());
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    fn write(dir: &Path, name: &str, bytes: &[u8]) -> String {
        let p = dir.join(name);
        std::fs::write(&p, bytes).unwrap();
        p.to_string_lossy().into_owned()
    }

    fn elf(machine: u16) -> Vec<u8> {
        let mut b = vec![0u8; 64];
        b[..4].copy_from_slice(b"\x7fELF");
        b[5] = 1;
        b[18..20].copy_from_slice(&machine.to_le_bytes());
        b
    }

    fn req(family: &str, artifact: &str) -> SimRequest {
        SimRequest { family: family.into(), artifact: artifact.into(), seconds: Some(1.0) }
    }

    #[test]
    fn simavr_line_parsing() {
        assert_eq!(simavr_uart_line("\x1b[32mtick 0..\x1b[0m\r"), Some("tick 0".into()));
        assert_eq!(simavr_uart_line("\x1b[32mno end\x1b[0m"), Some("no end".into()));
        assert_eq!(simavr_uart_line("Loaded 2128 bytes of Flash data at 0"), None);
    }

    #[test]
    fn kind_detection_uses_content() {
        let dir = tempfile::tempdir().unwrap();
        assert_eq!(detect_kind(Path::new(&write(dir.path(), "a.bin", &elf(EM_AVR)))).unwrap(), ArtifactKind::Elf { machine: EM_AVR });
        assert_eq!(detect_kind(Path::new(&write(dir.path(), "b.elf", b":100000000C94"))).unwrap(), ArtifactKind::Hex);
        assert_eq!(detect_kind(Path::new(&write(dir.path(), "c.hex", &[0, 1, 2]))).unwrap(), ArtifactKind::Bin);
    }

    #[test]
    fn plan_blocks_unknown_family_and_family_without_simulator() {
        assert!(!plan(&req("nope", "/x")).blockers.is_empty());
        let p = plan(&req("esp32", "/x"));
        assert!(p.blockers.iter().any(|b| b.contains("no simulator")));
    }

    #[test]
    fn plan_blocks_wrong_chip_and_wrong_kind() {
        let dir = tempfile::tempdir().unwrap();
        let arm = write(dir.path(), "arm.elf", &elf(EM_ARM));
        let p = plan(&req("avr_uno", &arm));
        assert!(p.blockers.iter().any(|b| b.contains("for ARM") && b.contains("needs AVR")), "{:?}", p.blockers);

        let bin = write(dir.path(), "fw.bin", &[0u8; 32]);
        let p = plan(&req("stm32", &bin));
        assert!(p.blockers.iter().any(|b| b.contains(".bin")), "{:?}", p.blockers);
    }

    #[test]
    fn plan_blocks_missing_file_and_bad_time() {
        let mut r = req("avr_uno", "/no/such/file.elf");
        r.seconds = Some(0.0);
        let p = plan(&r);
        assert!(p.blockers.iter().any(|b| b.contains("not found")));
        assert!(p.blockers.iter().any(|b| b.contains("Time limit")));
    }

    #[test]
    fn simavr_plan_is_an_argument_list() {
        let dir = tempfile::tempdir().unwrap();
        let fw = write(dir.path(), "fw with space.elf", &elf(EM_AVR));
        let p = plan(&req("avr_uno", &fw));
        assert_eq!(p.args, vec!["-m", "atmega328p", "-f", "16000000", fw.as_str()]);
        assert_eq!(p.artifact_kind.as_deref(), Some("elf"));
    }

    #[test]
    fn renode_script_quotes_paths_and_refuses_quotes() {
        let dir = tempfile::tempdir().unwrap();
        let fw = write(dir.path(), "fw with space", &elf(EM_ARM));
        let p = plan(&req("stm32", &fw));
        let script = p.script.unwrap();
        assert!(script.contains(&format!("sysbus LoadELF \"{fw}\"")));
        assert!(script.contains("@platforms/cpus/stm32f103.repl"));
        assert!(!script.contains("LoadPlatformDescriptionFromString"));
        assert!(renode_quote("/a\"b").is_err());
    }

    #[test]
    fn tail_reads_lines_written_while_running() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("uart.txt");
        let done = Arc::new(AtomicBool::new(false));
        let got = Arc::new(Mutex::new(Vec::new()));
        let t = {
            let (p, d, g) = (path.clone(), done.clone(), got.clone());
            std::thread::spawn(move || tail_lines(&p, &d, |l| g.lock().unwrap().push(l)))
        };
        std::fs::write(&path, "one\r\ntw").unwrap();
        std::thread::sleep(Duration::from_millis(250));
        std::fs::write(&path, "one\r\ntwo\nthree").unwrap();
        std::thread::sleep(Duration::from_millis(250));
        done.store(true, Ordering::SeqCst);
        t.join().unwrap();
        assert_eq!(*got.lock().unwrap(), vec!["one", "two", "three"]);
    }

    /// Runs only when the fixture ELF paths are set, for example in the
    /// simulation CI job:
    ///   OASIS_SIM_AVR_ELF=.../avr_uno_serial.ino.elf
    ///   OASIS_SIM_STM32_ELF=.../stm32f103_usart
    #[test]
    fn fixtures_run_in_real_simulators() {
        for (family, var, expect) in [
            ("avr_uno", "OASIS_SIM_AVR_ELF", "tick 3"),
            ("stm32", "OASIS_SIM_STM32_ELF", "oasis f103 hello"),
        ] {
            let Ok(fw) = std::env::var(var) else {
                eprintln!("skip {family}: {var} not set");
                continue;
            };
            let mut r = req(family, &fw);
            r.seconds = Some(if family == "stm32" { 0.2 } else { 2.0 });
            let p = plan(&r);
            assert!(p.blockers.is_empty(), "{family}: {:?}", p.blockers);
            let dir = tempfile::tempdir().unwrap();
            let lines = Arc::new(Mutex::new(Vec::new()));
            let sink = lines.clone();
            let done = execute(&p, "t", &dir.path().join("run dir"), Arc::new(AtomicBool::new(false)), Arc::new(move |l: SimLine| {
                if l.kind == "uart" {
                    sink.lock().unwrap().push(l.text);
                }
            }));
            assert!(done.error.is_none(), "{family}: {:?}", done.error);
            let got = lines.lock().unwrap();
            assert!(got.iter().any(|l| l == expect), "{family}: {got:?}");
        }
    }
}
