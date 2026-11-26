#!/usr/bin/env python3
"""Check that setup.sh and setup.ps1 pin the same tool versions.

Each pinned URL must contain its version, and each SHA-256 value must have
64 hex characters. Exit code 1 lists each difference.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SH = (HERE / "setup.sh").read_text(encoding="utf-8")
PS = (HERE / "setup.ps1").read_text(encoding="utf-8")

errors = []
versions = {}  # tool -> {source: version}


def add(tool, source, version, url, sha):
    versions.setdefault(tool, {})[source] = version
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        errors.append(f"{source} {tool}: SHA-256 value is not 64 hex characters")
    if not url.startswith("https://"):
        errors.append(f"{source} {tool}: URL is not https")
    if not tool.startswith("udev-") and version not in url:
        errors.append(f"{source} {tool}: URL does not contain version {version}")


pins = SH.split("PINS='", 1)[1].split("'", 1)[0]
for line in pins.strip().splitlines():
    tool, platform, version, url, sha = line.split("\t")
    add(tool, f"setup.sh[{platform}]", version, url, sha)

for m in re.finditer(r"'([\w-]+)'\s*=\s*@\{\s*Version = '([^']+)';\s*Url = '([^']+)';\s*Sha256 = '([^']+)'", PS):
    tool, version, url, sha = m.groups()
    add(tool, "setup.ps1", version, url, sha)

for name, sh_re, ps_re in [
    ("arduino:avr core", r'ARDUINO_AVR_CORE="([^"]+)"', r"\$ArduinoAvrCore = '([^']+)'"),
    ("mpremote", r'MPREMOTE_VERSION="([^"]+)"', r"\$MpremoteVersion = '([^']+)'"),
    ("rust target", r'STM32_RUST_TARGET="([^"]+)"', r"\$Stm32RustTarget = '([^']+)'"),
]:
    a, b = re.search(sh_re, SH), re.search(ps_re, PS)
    if not a or not b:
        errors.append(f"{name}: value not found in both scripts")
    elif a.group(1) != b.group(1):
        errors.append(f"{name}: setup.sh has {a.group(1)}, setup.ps1 has {b.group(1)}")

for tool, by_source in sorted(versions.items()):
    if len(set(by_source.values())) > 1:
        errors.append(f"{tool}: versions differ: {by_source}")

if not any(s == "setup.ps1" for v in versions.values() for s in v):
    errors.append("no pins found in setup.ps1")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"ok: {sum(len(v) for v in versions.values())} pinned files, {len(versions)} tools, versions agree")
