"""KiCAD file parsers for schematic and PCB files."""

import re
from pathlib import Path
from typing import Any


class KiCadSchematicParser:
    """Parse KiCAD schematic files (.kicad_sch)."""
    
    def parse(self, sch_path: Path) -> dict[str, Any]:
        """Parse schematic file and extract components and nets."""
        content = sch_path.read_text()
        
        return {
            "components": self._extract_components(content),
            "nets": self._extract_nets(content),
            "sheets": self._extract_sheets(content),
        }
    
    def _extract_components(self, content: str) -> list[dict]:
        """Extract symbol instances from schematic."""
        components = []
        
        # Match symbol blocks in KiCAD 7+ format
        # (symbol (lib_id "Device:R") (at 100 50 0) (unit 1)
        #   (property "Reference" "R1" ...)
        #   (property "Value" "10k" ...)
        # )
        symbol_pattern = r'\(symbol\s+\(lib_id\s+"([^"]+)"\)\s+\(at\s+([\d.-]+)\s+([\d.-]+)'
        ref_pattern = r'\(property\s+"Reference"\s+"([^"]+)"'
        value_pattern = r'\(property\s+"Value"\s+"([^"]+)"'
        footprint_pattern = r'\(property\s+"Footprint"\s+"([^"]+)"'
        
        # Find all symbol blocks
        symbol_blocks = re.findall(r'\(symbol\s+\(lib_id[^)]+\).*?\n(?:\s+\([^)]+\)[^\n]*\n)*\s+\)', 
                                    content, re.DOTALL)
        
        for block in symbol_blocks:
            lib_match = re.search(r'\(lib_id\s+"([^"]+)"', block)
            ref_match = re.search(ref_pattern, block)
            value_match = re.search(value_pattern, block)
            fp_match = re.search(footprint_pattern, block)
            pos_match = re.search(r'\(at\s+([\d.-]+)\s+([\d.-]+)', block)
            
            if ref_match:
                components.append({
                    "lib_id": lib_match.group(1) if lib_match else "",
                    "reference": ref_match.group(1),
                    "value": value_match.group(1) if value_match else "",
                    "footprint": fp_match.group(1) if fp_match else "",
                    "position": {
                        "x": float(pos_match.group(1)) if pos_match else 0,
                        "y": float(pos_match.group(2)) if pos_match else 0,
                    }
                })
        
        return components
    
    def _extract_nets(self, content: str) -> list[dict]:
        """Extract wire/net connections from schematic."""
        nets = []
        
        # Match wire segments
        # (wire (pts (xy 100 50) (xy 150 50)) ...)
        wire_pattern = r'\(wire\s+\(pts\s+\(xy\s+([\d.-]+)\s+([\d.-]+)\)\s+\(xy\s+([\d.-]+)\s+([\d.-]+)\)'
        
        # Match labels (net names)
        # (label "NET_NAME" (at 100 50 0) ...)
        label_pattern = r'\(label\s+"([^"]+)"\s+\(at\s+([\d.-]+)\s+([\d.-]+)'
        
        labels = re.findall(label_pattern, content)
        for name, x, y in labels:
            nets.append({
                "name": name,
                "position": {"x": float(x), "y": float(y)},
                "pins": [],  # Would need more complex analysis
            })
        
        return nets
    
    def _extract_sheets(self, content: str) -> list[dict]:
        """Extract hierarchical sheet references."""
        sheets = []
        
        # Match sheet instances
        # (sheet (at 100 50) (size 30 20)
        #   (property "Sheetname" "Power" ...)
        #   (property "Sheetfile" "power.kicad_sch" ...)
        # )
        sheet_pattern = r'\(sheet\s+\(at\s+([\d.-]+)\s+([\d.-]+)\)'
        name_pattern = r'\(property\s+"Sheetname"\s+"([^"]+)"'
        file_pattern = r'\(property\s+"Sheetfile"\s+"([^"]+)"'
        
        sheet_blocks = re.findall(r'\(sheet\s+\(at[^)]+\).*?\n(?:\s+\([^)]+\)[^\n]*\n)*\s+\)', 
                                   content, re.DOTALL)
        
        for block in sheet_blocks:
            name_match = re.search(name_pattern, block)
            file_match = re.search(file_pattern, block)
            
            if name_match and file_match:
                sheets.append({
                    "name": name_match.group(1),
                    "file": file_match.group(1),
                })
        
        return sheets


class KiCadPcbParser:
    """Parse KiCAD PCB files (.kicad_pcb)."""
    
    def parse(self, pcb_path: Path) -> dict[str, Any]:
        """Parse PCB file and extract footprints and layout info."""
        content = pcb_path.read_text()
        
        return {
            "footprints": self._extract_footprints(content),
            "layers": self._extract_layers(content),
            "board_outline": self._extract_outline(content),
        }
    
    def _extract_footprints(self, content: str) -> list[dict]:
        """Extract footprint placements from PCB."""
        footprints = []
        
        # Match footprint blocks
        # (footprint "Package:SOIC-8" (at 100 50 90)
        #   (property "Reference" "U1" ...)
        # )
        fp_pattern = r'\(footprint\s+"([^"]+)"\s+\(at\s+([\d.-]+)\s+([\d.-]+)(?:\s+([\d.-]+))?'
        ref_pattern = r'\(property\s+"Reference"\s+"([^"]+)"'
        
        fp_blocks = re.findall(r'\(footprint\s+"[^"]+"\s+\(at[^)]+\).*?\n(?:\s+\([^)]+\)[^\n]*\n)*', 
                                content, re.DOTALL)
        
        for block in fp_blocks:
            fp_match = re.search(fp_pattern, block)
            ref_match = re.search(ref_pattern, block)
            
            if fp_match and ref_match:
                footprints.append({
                    "footprint": fp_match.group(1),
                    "reference": ref_match.group(1),
                    "position": {
                        "x": float(fp_match.group(2)),
                        "y": float(fp_match.group(3)),
                        "rotation": float(fp_match.group(4)) if fp_match.group(4) else 0,
                    }
                })
        
        return footprints
    
    def _extract_layers(self, content: str) -> list[str]:
        """Extract layer stack from PCB."""
        layers = []
        
        # Match layers block
        layer_pattern = r'\((\d+)\s+"([^"]+)"\s+(\w+)\)'
        matches = re.findall(layer_pattern, content)
        
        for num, name, layer_type in matches:
            if layer_type in ["signal", "power"]:
                layers.append(name)
        
        return layers
    
    def _extract_outline(self, content: str) -> dict | None:
        """Extract board outline dimensions."""
        # Look for edge cuts layer geometry
        # This is simplified - real implementation would parse actual geometry
        
        edge_pattern = r'\(gr_line\s+\(start\s+([\d.-]+)\s+([\d.-]+)\)\s+\(end\s+([\d.-]+)\s+([\d.-]+)\)\s+\(layer\s+"Edge\.Cuts"\)'
        matches = re.findall(edge_pattern, content)
        
        if matches:
            all_x = []
            all_y = []
            for x1, y1, x2, y2 in matches:
                all_x.extend([float(x1), float(x2)])
                all_y.extend([float(y1), float(y2)])
            
            return {
                "width": max(all_x) - min(all_x),
                "height": max(all_y) - min(all_y),
                "origin": {"x": min(all_x), "y": min(all_y)},
            }
        
        return None
