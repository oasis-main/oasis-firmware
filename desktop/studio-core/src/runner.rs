//! Streaming runner: start a program, send each output line to a callback,
//! and stop the program at a time limit or on request.
//!
//! Same rule as `tools.rs`: the app passes arguments as a list. No shell.
//!
//! Some programs (simavr) buffer stdout when stdout is a pipe, so their
//! output arrives only at exit. With `pty_stdout`, the runner gives the
//! program a pseudo-terminal (pty) for stdout on macOS and Linux. The
//! program then writes each line when the line is complete.

use std::io::{BufRead, BufReader, Read};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Stream {
    Stdout,
    Stderr,
}

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
#[serde(tag = "reason", rename_all = "snake_case")]
pub enum Exit {
    /// The program exited by itself. `code` is None after a signal.
    Exited { code: Option<i32> },
    /// The runner stopped the program at the time limit.
    TimeLimit,
    /// The runner stopped the program because the stop flag was set.
    Stopped,
}

impl Exit {
    /// Short text for the action log: "exited 0", "time limit", "stopped".
    pub fn describe(&self) -> String {
        match self {
            Exit::Exited { code } => format!("exited {}", code.map_or("by signal".into(), |c| c.to_string())),
            Exit::TimeLimit => "time limit".into(),
            Exit::Stopped => "stopped".into(),
        }
    }
}

pub struct Spec {
    pub program: PathBuf,
    pub args: Vec<String>,
    pub cwd: Option<PathBuf>,
    pub limit: Duration,
    pub pty_stdout: bool,
}

type LineFn = Arc<dyn Fn(Stream, String) + Send + Sync>;

/// Run the program and block until it ends. `on_line` gets each line of
/// stdout and stderr without the line ending.
pub fn run(spec: &Spec, stop: Arc<AtomicBool>, on_line: LineFn) -> std::io::Result<Exit> {
    let (mut child, stdout_reader) = spawn(spec)?;
    let mut readers: Vec<JoinHandle<()>> = Vec::new();
    if let Some(r) = stdout_reader {
        readers.push(pump(r, Stream::Stdout, on_line.clone()));
    }
    if let Some(e) = child.stderr.take() {
        readers.push(pump(Box::new(e), Stream::Stderr, on_line.clone()));
    }

    let start = Instant::now();
    let exit = loop {
        if let Some(status) = child.try_wait()? {
            break Exit::Exited { code: status.code() };
        }
        if stop.load(Ordering::SeqCst) {
            kill(&mut child);
            break Exit::Stopped;
        }
        if start.elapsed() >= spec.limit {
            kill(&mut child);
            break Exit::TimeLimit;
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    for r in readers {
        let _ = r.join();
    }
    Ok(exit)
}

fn kill(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

fn pump(reader: Box<dyn Read + Send>, stream: Stream, on_line: LineFn) -> JoinHandle<()> {
    std::thread::spawn(move || {
        let mut reader = BufReader::new(reader);
        let mut buf = Vec::new();
        loop {
            buf.clear();
            // A pty read fails with EIO on Linux after the program exits.
            match reader.read_until(b'\n', &mut buf) {
                Ok(0) | Err(_) => break,
                Ok(_) => {
                    let line = String::from_utf8_lossy(&buf);
                    on_line(stream, line.trim_end_matches(['\r', '\n']).to_string());
                }
            }
        }
    })
}

#[cfg(unix)]
fn spawn(spec: &Spec) -> std::io::Result<(Child, Option<Box<dyn Read + Send>>)> {
    if !spec.pty_stdout {
        return spawn_piped(spec);
    }
    let pty = nix::pty::openpty(None, None).map_err(std::io::Error::from)?;
    let child = {
        // The Command owns the pty slave. Drop the Command right after spawn,
        // so that the program holds the only open slave, and the master read
        // ends when the program exits.
        let mut cmd = base_command(spec);
        cmd.stdout(Stdio::from(pty.slave));
        cmd.spawn()?
    };
    let master = std::fs::File::from(pty.master);
    Ok((child, Some(Box::new(master))))
}

#[cfg(not(unix))]
fn spawn(spec: &Spec) -> std::io::Result<(Child, Option<Box<dyn Read + Send>>)> {
    // No pty on Windows here. Buffered programs deliver output at exit.
    spawn_piped(spec)
}

fn spawn_piped(spec: &Spec) -> std::io::Result<(Child, Option<Box<dyn Read + Send>>)> {
    let mut cmd = base_command(spec);
    cmd.stdout(Stdio::piped());
    let mut child = cmd.spawn()?;
    let out = child.stdout.take().map(|o| Box::new(o) as Box<dyn Read + Send>);
    Ok((child, out))
}

fn base_command(spec: &Spec) -> Command {
    let mut cmd = Command::new(&spec.program);
    cmd.args(&spec.args).stdin(Stdio::null()).stderr(Stdio::piped());
    if let Some(dir) = &spec.cwd {
        cmd.current_dir(dir);
    }
    cmd
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::sync::Mutex;

    fn collect() -> (LineFn, Arc<Mutex<Vec<(Stream, String)>>>) {
        let lines = Arc::new(Mutex::new(Vec::new()));
        let sink = lines.clone();
        (Arc::new(move |s, l| sink.lock().unwrap().push((s, l))), lines)
    }

    fn spec(program: &str, args: &[&str], limit_ms: u64, pty: bool) -> Spec {
        Spec {
            program: crate::tools::find(program).expect("program on PATH"),
            args: args.iter().map(|s| s.to_string()).collect(),
            cwd: None,
            limit: Duration::from_millis(limit_ms),
            pty_stdout: pty,
        }
    }

    #[test]
    fn lines_arrive_without_a_shell() {
        for pty in [false, true] {
            let (f, lines) = collect();
            let exit = run(&spec("echo", &["$HOME;", "two words"], 5000, pty), Arc::new(AtomicBool::new(false)), f).unwrap();
            assert_eq!(exit, Exit::Exited { code: Some(0) });
            assert_eq!(lines.lock().unwrap().as_slice(), &[(Stream::Stdout, "$HOME; two words".to_string())]);
        }
    }

    #[test]
    fn time_limit_stops_the_program() {
        let (f, _) = collect();
        let t = Instant::now();
        let exit = run(&spec("sleep", &["5"], 200, true), Arc::new(AtomicBool::new(false)), f).unwrap();
        assert_eq!(exit, Exit::TimeLimit);
        assert!(t.elapsed() < Duration::from_secs(3));
    }

    #[test]
    fn stop_flag_stops_the_program() {
        let (f, _) = collect();
        let stop = Arc::new(AtomicBool::new(false));
        let s2 = stop.clone();
        std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(150));
            s2.store(true, Ordering::SeqCst);
        });
        let exit = run(&spec("sleep", &["5"], 10_000, false), stop, f).unwrap();
        assert_eq!(exit, Exit::Stopped);
    }
}
