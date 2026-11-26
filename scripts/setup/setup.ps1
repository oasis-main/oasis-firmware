<#
.SYNOPSIS
Oasis Studio tool setup for Windows 10 and 11 (x64).

.DESCRIPTION
Installs the programs that Oasis Studio uses to flash and simulate boards.
Oasis Studio itself is a separate installer.

Rules:
- The script installs only what is missing. It does not upgrade or remove a
  program that is already installed.
- Each program comes from a fixed release file. The script checks the
  SHA-256 hash of each file before it uses the file.
- Programs go in %LOCALAPPDATA%\OasisStudio\tools. The script adds each
  program folder to the PATH of this user. The script needs no
  administrator permission.

Run from a PowerShell window:
  powershell -ExecutionPolicy Bypass -File setup.ps1
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Tools full
  powershell -ExecutionPolicy Bypass -File setup.ps1 -DryRun

.PARAMETER Tools
flash (default): arduino-cli and the Arduino AVR core, avrdude, espflash,
probe-rs, picotool, mpremote (if Python is installed).
full: the flash tools, plus Rust and Renode. simavr has no Windows build.

.PARAMETER DryRun
Show the plan and install nothing.

.PARAMETER Yes
Do not ask before the install.
#>
[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSReviewUnusedParameter', 'Yes', Justification = 'The Ask function reads $Yes.')]
[CmdletBinding()]
param(
    [ValidateSet('flash', 'full')]
    [string]$Tools = 'flash',
    [switch]$DryRun,
    [switch]$Yes
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# ------------------------------------------------------------------ versions
# Fixed release files for Windows x64. setup.sh has the macOS and Linux rows.
# To change a version, download the new file, check the publisher's hash
# where one is published, and replace the row.
$Pins = @{
    'arduino-cli' = @{ Version = '1.6.0';  Url = 'https://github.com/arduino/arduino-cli/releases/download/v1.6.0/arduino-cli_1.6.0_Windows_64bit.zip'; Sha256 = '2769b9b282ce597db9679d8ec14d726d57004ca4205ef4d7a795bf36b6cdc9d8' }
    'avrdude'     = @{ Version = '8.3';    Url = 'https://github.com/avrdudes/avrdude/releases/download/v8.3/avrdude-v8.3-windows-x64.zip'; Sha256 = '8630c7d8bb9682a1685aaa9ad42550ae1131c9d13528f0d20975368ba615e9b0' }
    'espflash'    = @{ Version = '4.7.0';  Url = 'https://github.com/esp-rs/espflash/releases/download/v4.7.0/espflash-x86_64-pc-windows-msvc.zip'; Sha256 = '2b10333e4f4f1a26024259b0cc1942ba17f27b3c530621c6111f4c10ac70213e' }
    'probe-rs'    = @{ Version = '0.32.0'; Url = 'https://github.com/probe-rs/probe-rs/releases/download/v0.32.0/probe-rs-tools-x86_64-pc-windows-msvc.zip'; Sha256 = '56fc0564cc23d604b27dc2d57606194159c49f951999f3e47bd2cbffcba64103' }
    'picotool'    = @{ Version = '2.3.1';  Url = 'https://github.com/raspberrypi/pico-sdk-tools/releases/download/v2.3.1-0/picotool-2.3.1-x64-win.zip'; Sha256 = '68730be0813f8f35be2cca147cf7f1572662d5dcf0f5ba468e02a6dd9e85db2b' }
    'renode'      = @{ Version = '1.16.1'; Url = 'https://github.com/renode/renode/releases/download/v1.16.1/renode-1.16.1.windows-portable-dotnet.zip'; Sha256 = 'd09b7934cfd560cd06bde8f131ef78f521f10d423d5aac6096f2a583224aeb3e' }
    'rustup-init' = @{ Version = '1.28.2'; Url = 'https://static.rust-lang.org/rustup/archive/1.28.2/x86_64-pc-windows-msvc/rustup-init.exe'; Sha256 = '88d8258dcf6ae4f7a80c7d1088e1f36fa7025a1cfd1343731b4ee6f385121fc0' }
}
$ArduinoAvrCore = 'arduino:avr@1.8.6'
$MpremoteVersion = '1.29.0'
$Stm32RustTarget = 'thumbv7m-none-eabi'

# Name, kit, program, purpose, size (download size; disk size for the core and Rust)
$ToolRows = @(
    @('arduino-cli',      'flash', 'arduino-cli', 'Uploads firmware to any Arduino board, and builds Arduino sketches.', '20 MB'),
    @('arduino:avr core', 'flash', '',            'Compiler and upload tools for AVR Arduino boards (Uno, Mega, Nano).', '240 MB'),
    @('avrdude',          'flash', 'avrdude',     'Writes and reads firmware on an Arduino Uno. The Uno backup uses avrdude.', '7 MB'),
    @('espflash',         'flash', 'espflash',    'Writes firmware to ESP32 boards.', '7 MB'),
    @('probe-rs',         'flash', 'probe-rs',    'Writes firmware to STM32 chips through a debug probe (ST-LINK).', '11 MB'),
    @('picotool',         'flash', 'picotool',    'Writes and reads firmware on RP2040 boards in BOOTSEL mode.', '2 MB'),
    @('mpremote',         'flash', 'mpremote',    'Copies files to MicroPython boards. Needs Python 3.', 'small'),
    @('rust',             'full',  'cargo',       'Rust compiler. Builds firmware and the Oasis Studio MCP server.', '1.6 GB'),
    @('renode',           'full',  'renode',      'Simulates STM32 chips with no board.', '112 MB')
)

$ToolDir = Join-Path $env:LOCALAPPDATA 'OasisStudio\tools'
$Work = Join-Path ([IO.Path]::GetTempPath()) ('oasis-setup-' + [Guid]::NewGuid().ToString('N'))

function Say([string]$Text) { Write-Host $Text }
function Step([string]$Text) { Write-Host ''; Write-Host "==> $Text" }

function Ask([string]$Question) {
    if ($Yes) { return $true }
    $reply = Read-Host "$Question [y/N]"
    return ($reply -match '^(y|yes)$')
}

function Find-Program([string]$Name) {
    $cmd = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    return $null
}

function Test-CoreInstalled {
    # Windows PowerShell 5.1 stops on redirected stderr when the preference is Stop.
    $ErrorActionPreference = 'Continue'
    if (-not (Find-Program 'arduino-cli')) { return $false }
    $list = & arduino-cli core list 2>$null
    return [bool]($list | Where-Object { ($_ -split '\s+')[0] -eq 'arduino:avr' })
}

function Get-Found([object[]]$Row) {
    if ($Row[0] -eq 'arduino:avr core') {
        if (Test-CoreInstalled) { return 'installed' }
        return $null
    }
    return (Find-Program $Row[2])
}

function Get-PythonCommand {
    foreach ($c in @('py', 'python', 'python3')) {
        $p = Find-Program $c
        # Skip the Microsoft Store placeholder in WindowsApps.
        if ($p -and $p -notmatch '\\WindowsApps\\') { return $p }
    }
    return $null
}

function Add-UserPath([string]$Folder) {
    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not $current) { $current = '' }
    $parts = $current.Split(';') | Where-Object { $_ -ne '' }
    if ($parts -notcontains $Folder) {
        [Environment]::SetEnvironmentVariable('Path', (($parts + $Folder) -join ';'), 'User')
        Say "    added to the user PATH: $Folder"
    }
    if (($env:Path.Split(';')) -notcontains $Folder) { $env:Path = "$Folder;$env:Path" }
}

function Get-CheckedFile([string]$Tool) {
    $pin = $Pins[$Tool]
    New-Item -ItemType Directory -Force -Path $Work | Out-Null
    $file = Join-Path $Work ([IO.Path]::GetFileName($pin.Url))
    Say "    download $($pin.Url)"
    Invoke-WebRequest -UseBasicParsing -Uri $pin.Url -OutFile $file
    $got = (Get-FileHash -Algorithm SHA256 -Path $file).Hash.ToLowerInvariant()
    if ($got -ne $pin.Sha256) {
        Remove-Item -Force $file
        throw "SHA-256 check failed for $([IO.Path]::GetFileName($pin.Url)). Expected $($pin.Sha256), got $got. The file was deleted."
    }
    Say '    sha256 ok'
    return $file
}

function Install-Release([string]$Tool, [string]$Program) {
    $pin = $Pins[$Tool]
    $file = Get-CheckedFile $Tool
    $dir = Join-Path $ToolDir "$Tool-$($pin.Version)"
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
    Expand-Archive -Path $file -DestinationPath $dir -Force
    # The file nearest to the top of the folder wins.
    $exe = Get-ChildItem -Path $dir -Recurse -File -Filter "$Program.exe" |
        Sort-Object { $_.FullName.Length } | Select-Object -First 1
    if (-not $exe) { throw "$Program.exe not found in $dir." }
    Add-UserPath $exe.DirectoryName
    Say "    $($exe.FullName)"
}

function Test-InKit([string]$Kit) { return ($Tools -eq 'full' -or $Kit -eq 'flash') }

# ------------------------------------------------------------------ plan
if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
    throw 'This script supports Windows on x64 processors only. Use docs/INSTALL_TOOLCHAINS.md.'
}
Step "Oasis Studio tool setup: Windows (x64), tools: $Tools"
Say ''
Say ('{0,-18} {1,-10} {2}' -f 'Program', 'Size', 'Status')
$missing = @()
foreach ($row in $ToolRows) {
    if (-not (Test-InKit $row[1])) { continue }
    $at = Get-Found $row
    if ($at) {
        Say ('{0,-18} {1,-10} found: {2}' -f $row[0], '-', $at)
    } else {
        Say ('{0,-18} {1,-10} will install' -f $row[0], $row[4])
        $missing += $row[0]
    }
    Say ('{0,-18} {1}' -f '', $row[3])
}
if ($Tools -eq 'full') {
    Say ''
    Say 'simavr (Arduino Uno simulation) has no Windows build. Use WSL 2 with setup.sh for Uno simulation.'
}
Say ''
Say "Programs go in $ToolDir. The script adds each program folder to the PATH of this user."

if ($DryRun) {
    Say ''
    Say 'Dry run: nothing was installed.'
    exit 0
}
if ($missing.Count -eq 0) {
    Say ''
    Say "All programs for '$Tools' are installed."
} elseif (-not (Ask 'Install the missing programs?')) {
    Say 'Nothing was installed.'
    exit 0
}

# ------------------------------------------------------------------ install
try {
    foreach ($t in @('arduino-cli', 'avrdude', 'espflash', 'probe-rs', 'picotool', 'renode')) {
        if ($missing -contains $t) {
            Step "$t $($Pins[$t].Version)"
            Install-Release $t $t
        }
    }

    if ($missing -contains 'mpremote') {
        $py = Get-PythonCommand
        if ($py) {
            Step "mpremote $MpremoteVersion (pip, this user only)"
            & $py -m pip install --user --disable-pip-version-check "mpremote==$MpremoteVersion"
            if ($LASTEXITCODE -ne 0) { throw 'pip could not install mpremote.' }
            $scripts = & $py -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"
            Add-UserPath $scripts.Trim()
        } else {
            Step 'mpremote'
            Say 'Python 3 is not installed, so the script skips mpremote. mpremote is needed only for MicroPython boards.'
            Say 'To add mpremote later: winget install Python.Python.3.12, then run this script again.'
        }
    }

    if ($missing -contains 'rust') {
        Step "Rust (rustup $($Pins['rustup-init'].Version), stable toolchain)"
        Say 'Rust on Windows needs the Microsoft C++ Build Tools. If rustup reports that they are missing, install them and run this script again.'
        $init = Get-CheckedFile 'rustup-init'
        & $init -y --profile minimal --default-toolchain stable
        if ($LASTEXITCODE -ne 0) { throw 'rustup-init failed.' }
        Add-UserPath (Join-Path $env:USERPROFILE '.cargo\bin')
    }
    if ($Tools -eq 'full' -and (Find-Program 'rustup')) {
        Step "Rust target $Stm32RustTarget (STM32F103)"
        & rustup target add $Stm32RustTarget
        if ($LASTEXITCODE -ne 0) { throw 'rustup target add failed.' }
    }

    if ((Find-Program 'arduino-cli') -and -not (Test-CoreInstalled)) {
        Step "Arduino core $ArduinoAvrCore"
        & arduino-cli core update-index
        if ($LASTEXITCODE -ne 0) { throw 'arduino-cli core update-index failed.' }
        & arduino-cli core install $ArduinoAvrCore
        if ($LASTEXITCODE -ne 0) { throw 'arduino-cli core install failed.' }
    }
} finally {
    if (Test-Path $Work) { Remove-Item -Recurse -Force $Work }
}

# ------------------------------------------------------------------ check
Step 'Check'
function Get-VersionText([string]$Name) {
    $ErrorActionPreference = 'Continue'
    switch ($Name) {
        'arduino-cli'      { return (& arduino-cli version 2>&1 | Select-Object -First 1) }
        'arduino:avr core' { return (& arduino-cli core list 2>$null | Where-Object { $_ -match '^arduino:avr\s' } | Select-Object -First 1) }
        'avrdude'          { return (& avrdude --version 2>&1 | Where-Object { "$_" -match '\d+\.\d+' } | Select-Object -First 1) }
        'espflash'         { return (& espflash --version 2>&1 | Select-Object -First 1) }
        'probe-rs'         { return (& probe-rs --version 2>&1 | Select-Object -First 1) }
        'picotool'         { return (& picotool version 2>&1 | Select-Object -First 1) }
        'mpremote'         { return (Find-Program 'mpremote') }
        'rust'             { return (& cargo --version 2>&1 | Select-Object -First 1) }
        'renode'           { return (& renode --version 2>&1 | Select-Object -First 1) }
    }
}
$fail = $false
foreach ($row in $ToolRows) {
    if (-not (Test-InKit $row[1])) { continue }
    $v = $null
    if (Get-Found $row) { try { $v = Get-VersionText $row[0] } catch { $v = $null } }
    if ($v) {
        Say ('  ok       {0,-18} {1}' -f $row[0], "$v".Trim())
    } elseif ($row[0] -eq 'mpremote' -and -not (Get-PythonCommand)) {
        Say ('  skipped  {0,-18} Python 3 is not installed' -f $row[0])
    } else {
        Say "  MISSING  $($row[0])"
        $fail = $true
    }
}

Say ''
Say 'Notes:'
Say '- Open a new terminal, and restart Oasis Studio, so that the new PATH applies.'
Say '- A board with a CH340 or CP210x USB-UART chip can need a driver from the chip vendor before it gets a COM port.'
Say '- picotool needs the WinUSB driver for an RP2040 in BOOTSEL mode. Install the driver with Zadig (https://zadig.akeo.ie).'
if ($fail) {
    Say 'Some programs are missing. The steps for each program are in docs/INSTALL_TOOLCHAINS.md.'
    exit 1
}
Say 'Done. Open Oasis Studio. The Hardware page lists these programs.'
# An explicit exit code. Without it, a caller can read $LASTEXITCODE of the
# last program that the check ran.
exit 0
