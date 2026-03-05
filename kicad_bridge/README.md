# KiCAD Bridge for Oasis Firmware

Two-way integration between `device.yaml` configurations and KiCAD PCB projects.

## Features

### 1. Import: KiCAD → device.yaml
- Parse `.kicad_sch` schematics to extract components
- Parse `.kicad_pcb` for physical layout constraints
- Generate device.yaml skeleton from existing designs

### 2. Export: device.yaml → KiCAD
- Generate KiCAD project scaffold
- Create hierarchical schematic sheets
- Add recommended connectors and junction components
- Generate BOM with supplier links

### 3. Intermediate Junction Guidance
- Connector recommendations based on signal types
- Enclosure mounting considerations
- Cable routing and strain relief
- EMI/RFI shielding suggestions
- Power distribution topology

## Installation

```bash
pip install -e .
```

Requires KiCAD 7.0+ for Python scripting support.

## Usage

### Import existing PCB
```bash
oasis-kicad import ./my-project.kicad_pro --output device.yaml
```

### Generate KiCAD scaffold
```bash
oasis-kicad scaffold --config device.yaml --output ./kicad-project/
```

### Design review
```bash
oasis-kicad review --config device.yaml --kicad ./my-project.kicad_pro
```
