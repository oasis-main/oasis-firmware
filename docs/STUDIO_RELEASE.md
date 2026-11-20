# Oasis Studio — build and release

Oasis Studio is the desktop app in `desktop/` (Tauri 2: Rust back end in
`desktop/src-tauri`, React + Vite front end in `desktop/src`). The back end
calls the tool registry in `desktop/studio-core`, which links `oasis-core`
(the root crate) directly. The MCP server `oasis-studio-mcp` is a binary in
`desktop/studio-core`.

## Build on your computer

Needs: Rust (stable), Node.js 20 or later, and the platform packages below.

| OS | Packages |
|----|----------|
| macOS 11+ | Xcode Command Line Tools (`xcode-select --install`) |
| Windows 10/11 | Microsoft C++ Build Tools; WebView2 (included in Windows 11) |
| Ubuntu / Debian | `sudo apt install libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf libudev-dev build-essential` |
| Fedora | `sudo dnf install webkit2gtk4.1-devel libappindicator-gtk3-devel librsvg2-devel systemd-devel` |

```bash
cd desktop
npm ci
npm run tauri dev      # run the app with live reload
npm run tauri build    # make installers in desktop/src-tauri/target/release/bundle/
```

macOS note: if the build stops with `failed to run xattr: option -r not
recognized`, a Python package installed its own `xattr` ahead of
`/usr/bin/xattr` on PATH. Run the build with `PATH="/usr/bin:$PATH"`.

macOS note: on Apple silicon, check `rustc -vV | grep host`. An
`x86_64-apple-darwin` toolchain builds an Intel app that runs through
Rosetta. Use `npm run tauri build -- --target aarch64-apple-darwin` after
`rustup target add aarch64-apple-darwin`.

`npm run dev` alone opens the UI in a browser with sample data and a
"Browser preview" badge. Use the preview for UI work only. The preview has
no access to ports, tools, or files.

Tests: `cd desktop/src-tauri && cargo test --locked` and
`cd desktop/studio-core && cargo test --locked`.

## Release

1. Set the same version in `desktop/package.json`,
   `desktop/src-tauri/Cargo.toml`, and `desktop/src-tauri/tauri.conf.json`.
2. Push a tag: `git tag studio-v0.1.0 && git push origin studio-v0.1.0`.
3. The `studio-release` workflow builds on macOS (universal), Windows, and
   Linux, and attaches the installers to a **draft** release.
4. Review the draft on GitHub. Publish the draft. The download page
   (`site/download.html`) lists the newest published `studio-v*` release.

| OS | Files |
|----|-------|
| macOS | `.dmg` (universal: Apple silicon and Intel) |
| Windows | `.msi` and `-setup.exe` |
| Linux | `.AppImage`, `.deb`, `.rpm` |

## Signing (not done in v0.1)

- macOS builds are ad-hoc signed, not notarized. On first open, macOS
  blocks the app. The user opens System Settings → Privacy & Security and
  clicks "Open Anyway". Notarization needs an Apple Developer account. Add
  these repository secrets and pass them as `env` to `tauri-action`:
  `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`,
  `APPLE_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID`.
- Windows builds are not code-signed. SmartScreen shows a warning. The
  user clicks "More info", then "Run anyway". Code signing needs a
  certificate; see the Tauri 2 Windows signing guide.
- Auto-update is off. The Tauri updater needs a signing key pair and a
  published `latest.json`. Add the updater after the first signed release.

## Simulators

The Simulate page uses programs that the user installs. The app does not
include them.

| Simulator | Family | macOS | Linux | Windows |
|-----------|--------|-------|-------|---------|
| simavr | Arduino Uno (ATmega328P) | `brew tap osx-cross/avr`, then `brew install osx-cross/avr/simavr` | `sudo apt install simavr` | no official build |
| Renode 1.16 | STM32F103 | `renode_<version>.dmg` from the Renode GitHub releases | `renode-<version>.linux-portable-dotnet.tar.gz` | `renode-<version>.setup.exe` |

The app looks for each program on PATH, and on macOS also in
`/Applications/Renode.app/Contents/MacOS`. The Hardware page shows what it
found. Each run uses a new folder in the app data folder:
`sim-runs/<run id>/`.

## Linux serial access

On Linux, a user needs serial-port permission to see board details and to
flash. Debian/Ubuntu: `sudo usermod -aG dialout $USER`. Arch:
`sudo usermod -aG uucp $USER`. Log out and log in again.
