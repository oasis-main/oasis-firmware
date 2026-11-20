//! External tool discovery and a supervised runner.
//!
//! Rule: the app passes arguments as a list to the program. The app never
//! builds a shell command string, and never runs a shell.

use serde::Serialize;
use std::io::Read;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

/// Tools that Oasis Studio knows. `version_arg` prints a version and exits.
pub const KNOWN_TOOLS: &[(&str, &str, &str)] = &[
    ("cargo", "--version", "Rust build tool (generated firmware)"),
    ("espflash", "--version", "ESP32 flash tool"),
    ("probe-rs", "--version", "Debug-probe flash and log tool (STM32, RP2040)"),
    ("picotool", "version", "RP2040 flash tool"),
    ("mpremote", "--version", "MicroPython board tool"),
    ("arduino-cli", "version", "Arduino build and upload tool"),
    ("avrdude", "-?", "AVR flash tool"),
    ("simavr", "", "AVR simulator (Arduino Uno)"),
    ("renode", "--version", "STM32 simulator"),
];

#[derive(Debug, Clone, Serialize)]
pub struct ToolStatus {
    pub name: String,
    pub purpose: String,
    pub path: Option<String>,
    pub version: Option<String>,
}

pub struct RunOutput {
    #[allow(dead_code)] // read by the flash runner (FW-015)
    pub status: Option<i32>,
    pub stdout: String,
    pub stderr: String,
    pub timed_out: bool,
}

/// Run `program` with `args` and a time limit. No shell is involved.
/// For short outputs only (version checks): the app reads the pipes after
/// the program exits. The flash runner (FW-015) must stream the pipes.
pub fn run_with_timeout(program: &PathBuf, args: &[&str], limit: Duration) -> std::io::Result<RunOutput> {
    let mut child = Command::new(program)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    let start = Instant::now();
    let mut timed_out = false;
    let status = loop {
        if let Some(s) = child.try_wait()? {
            break s.code();
        }
        if start.elapsed() > limit {
            let _ = child.kill();
            let _ = child.wait();
            timed_out = true;
            break None;
        }
        std::thread::sleep(Duration::from_millis(25));
    };
    let mut stdout = String::new();
    let mut stderr = String::new();
    if let Some(mut o) = child.stdout.take() {
        let _ = o.read_to_string(&mut stdout);
    }
    if let Some(mut e) = child.stderr.take() {
        let _ = e.read_to_string(&mut stderr);
    }
    Ok(RunOutput { status, stdout, stderr, timed_out })
}

/// GUI apps on macOS start with a short PATH. Add the usual tool folders.
pub fn search_path() -> String {
    let mut dirs: Vec<PathBuf> = std::env::var_os("PATH")
        .map(|p| std::env::split_paths(&p).collect())
        .unwrap_or_default();
    if let Some(home) = dirs::home_dir() {
        dirs.push(home.join(".cargo/bin"));
        dirs.push(home.join(".local/bin"));
    }
    for d in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"] {
        dirs.push(PathBuf::from(d));
    }
    // The Renode .dmg installs the program inside the app bundle.
    if cfg!(target_os = "macos") {
        dirs.push(PathBuf::from("/Applications/Renode.app/Contents/MacOS"));
    }
    std::env::join_paths(dirs).map(|p| p.to_string_lossy().into_owned()).unwrap_or_default()
}

pub fn find(name: &str) -> Option<PathBuf> {
    let cwd = std::env::current_dir().ok()?;
    which::which_in(name, Some(search_path()), cwd).ok()
}

fn first_line(s: &str) -> Option<String> {
    s.lines().map(str::trim).find(|l| !l.is_empty()).map(|l| l.chars().take(120).collect())
}

/// An empty `version_arg` means the tool has no version flag (simavr).
pub fn status_of(name: &str, version_arg: &str, purpose: &str) -> ToolStatus {
    let path = find(name);
    let version = path.as_ref().filter(|_| !version_arg.is_empty()).and_then(|p| {
        let out = run_with_timeout(p, &[version_arg], Duration::from_secs(5)).ok()?;
        if out.timed_out {
            return Some("no answer in 5 s".into());
        }
        // avrdude prints its version on stderr.
        first_line(&out.stdout).or_else(|| first_line(&out.stderr))
    });
    ToolStatus {
        name: name.into(),
        purpose: purpose.into(),
        path: path.map(|p| p.to_string_lossy().into_owned()),
        version,
    }
}

pub fn list() -> Vec<ToolStatus> {
    KNOWN_TOOLS.iter().map(|(n, v, p)| status_of(n, v, p)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(unix)]
    #[test]
    fn runner_passes_arguments_without_a_shell() {
        // If a shell were involved, "$HOME" and ";" would be expanded or split.
        let echo = find("echo").expect("echo on PATH");
        let out = run_with_timeout(&echo, &["$HOME;", "two words"], Duration::from_secs(5)).unwrap();
        assert_eq!(out.stdout.trim(), "$HOME; two words");
    }

    #[cfg(unix)]
    #[test]
    fn runner_enforces_the_time_limit() {
        let sleep = find("sleep").expect("sleep on PATH");
        let out = run_with_timeout(&sleep, &["5"], Duration::from_millis(200)).unwrap();
        assert!(out.timed_out);
    }
}
