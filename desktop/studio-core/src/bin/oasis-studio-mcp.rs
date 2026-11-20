//! `oasis-studio-mcp`: the Oasis Studio MCP server (stdio transport).
//!
//! An MCP client starts this program and sends one JSON-RPC message on each
//! line of stdin. The program writes one message on each line of stdout.
//! Diagnostic text goes to stderr only. The program ends at the end of stdin.

use oasis_studio_core::{mcp, Paths, Studio};
use std::io::{BufRead, Write};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

const USAGE: &str = "\
oasis-studio-mcp: Oasis Studio MCP server (stdio)

USAGE:
    oasis-studio-mcp [--data-dir <dir>] [--projects-dir <dir>]
    oasis-studio-mcp --list-tools
    oasis-studio-mcp --version

An MCP client starts this program. The program reads JSON-RPC messages on
stdin and writes responses on stdout, one message on each line.

OPTIONS:
    --data-dir <dir>      Owned-device list, action log, simulation runs.
                          Default: the Oasis Studio app data folder, or
                          $OASIS_STUDIO_DATA_DIR.
    --projects-dir <dir>  Generated firmware. Default: Documents/Oasis Studio,
                          or $OASIS_STUDIO_PROJECTS_DIR.
    --list-tools          Print the tool names and classes, then exit.
    --version             Print the version, then exit.
";

fn main() {
    let mut paths = match Paths::from_env() {
        Ok(p) => p,
        Err(e) => {
            eprintln!("oasis-studio-mcp: {e}");
            std::process::exit(2);
        }
    };
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--version" | "-V" => {
                println!("oasis-studio-mcp {}", env!("CARGO_PKG_VERSION"));
                return;
            }
            "--help" | "-h" => {
                print!("{USAGE}");
                return;
            }
            "--list-tools" => {
                for t in oasis_studio_core::catalog::tools() {
                    let class = serde_json::to_value(t.class).ok().and_then(|v| v.as_str().map(String::from)).unwrap_or_default();
                    println!("{:<18} {:<8} {}", t.name, class, t.summary);
                }
                return;
            }
            "--data-dir" | "--projects-dir" => {
                let Some(v) = args.next() else {
                    eprintln!("oasis-studio-mcp: {a} needs a folder\n\n{USAGE}");
                    std::process::exit(2);
                };
                if a == "--data-dir" {
                    paths.data_dir = PathBuf::from(v);
                } else {
                    paths.projects_dir = PathBuf::from(v);
                }
            }
            other => {
                eprintln!("oasis-studio-mcp: unknown option {other}\n\n{USAGE}");
                std::process::exit(2);
            }
        }
    }

    eprintln!(
        "oasis-studio-mcp {}: data {}, projects {}",
        env!("CARGO_PKG_VERSION"),
        paths.data_dir.display(),
        paths.projects_dir.display()
    );
    let studio = Arc::new(Studio::new(paths));
    let stdout = Mutex::new(std::io::stdout());
    let out: mcp::Out = Arc::new(move |msg| {
        let mut o = stdout.lock().unwrap_or_else(|p| p.into_inner());
        // One message on one line. serde_json escapes line breaks in strings.
        let _ = writeln!(o, "{msg}");
        let _ = o.flush();
    });
    let server = mcp::Server::new(studio, out);
    let mut stdin = std::io::stdin().lock();
    let mut buf = Vec::new();
    loop {
        buf.clear();
        match stdin.read_until(b'\n', &mut buf) {
            Ok(0) => break,
            // Bytes that are not UTF-8 become U+FFFD. The line then fails to parse.
            Ok(_) => server.handle_line(&String::from_utf8_lossy(&buf)),
            Err(e) => {
                eprintln!("oasis-studio-mcp: stdin: {e}");
                break;
            }
        }
    }
    server.shutdown();
}
