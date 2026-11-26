# Tool setup scripts

| File | System |
|------|--------|
| `setup.sh` | macOS (with Homebrew) and Ubuntu 22.04 or later (x86_64, aarch64) |
| `setup.ps1` | Windows 10 and 11 (x64) |
| `check_pins.py` | Checks that both scripts pin the same versions |

User steps: [docs/INSTALL_TOOLCHAINS.md](../../docs/INSTALL_TOOLCHAINS.md).
CI: [.github/workflows/setup-scripts.yml](../../.github/workflows/setup-scripts.yml)
runs each script on clean Ubuntu 22.04 and 24.04 containers, Ubuntu 24.04
on ARM, macOS, Windows PowerShell 5.1, and PowerShell 7.

## Change a pinned version

The Ubuntu and Windows rows pin a release file and its SHA-256 value
(`PINS` in `setup.sh`, `$Pins` in `setup.ps1`). macOS uses Homebrew for the
flash tools, so only Renode and rustup have macOS rows.

1. Download the new release file.
2. Compute the hash: `shasum -a 256 <file>` (macOS) or `sha256sum <file>`
   (Linux).
3. If the publisher gives a hash file (arduino-cli `checksums.txt`, probe-rs
   `.sha256`, rustup `.sha256`), compare the two values. Stop if they
   differ.
4. Replace the version, URL, and hash in every row for that tool, in both
   scripts.
5. Run `python3 scripts/setup/check_pins.py`.
6. Open a pull request. The `setup-scripts` workflow installs the new
   version on each system.
