"""Export device.yaml to KiCAD project scaffold."""

import json
from pathlib import Path
from typing import Any
import yaml

from .junction_advisor import JunctionAdvisor


class KiCadExporter:
    """Generate KiCAD project scaffold from device.yaml configuration."""
    
    # KiCAD symbol library mappings
    SENSOR_SYMBOLS = {
        "dht11": ("Sensor:DHT11", "Sensor_Temp_DHT11"),
        "dht22": ("Sensor:DHT22", "Sensor_Temp_DHT22"),
        "bme280": ("Sensor_Pressure:BME280", "Package_LGA:Bosch_LGA-8_2.5x2.5mm_P0.65mm"),
        "bme680": ("Sensor_Pressure:BME680", "Package_LGA:Bosch_LGA-8_2.5x2.5mm_P0.65mm"),
        "mpu6050": ("Sensor_Motion:MPU-6050", "Sensor_Motion:InvenSense_QFN-24_4x4mm_P0.5mm"),
        "mpu9250": ("Sensor_Motion:MPU-9250", "Sensor_Motion:InvenSense_QFN-24_3x3mm_P0.4mm"),
        "bno055": ("Sensor_Motion:BNO055", "Sensor_Motion:Bosch_BNO055"),
        "bh1750": ("Sensor_Optical:BH1750FVI", "Package_SO:WSOF-6_1.5x1.6mm_P0.5mm"),
        "hcsr04": ("Sensor_Distance:HC-SR04", "Module:HC-SR04"),
        "ina219": ("Sensor_Current:INA219", "Package_SO:MSOP-8_3x3mm_P0.65mm"),
    }
    
    ACTUATOR_SYMBOLS = {
        "relay": ("Relay:RELAY-SPDT", "Relay_THT:Relay_SPDT_Finder_32.21-x000"),
        "pwm": ("Device:Q_NMOS_GSD", "Package_TO_SOT_SMD:SOT-23"),
        "dc_motor": ("Motor:Motor_DC", ""),
        "servo": ("Motor:Motor_Servo", ""),
        "stepper_a4988": ("Driver_Motor:A4988", "Module:Pololu_Breakout-16_15.2x20.3mm"),
        "led": ("Device:LED", "LED_THT:LED_D3.0mm"),
    }
    
    CONNECTOR_SYMBOLS = {
        "jst_xh": "Connector:Conn_01x{n}_Pin",
        "jst_ph": "Connector:Conn_01x{n}_Pin",
        "jst_sh": "Connector:Conn_01x{n}_Pin",
        "screw_terminal": "Connector:Screw_Terminal_01x{n}",
        "header": "Connector:Conn_01x{n}_Pin",
        "usb_c": "Connector:USB_C_Receptacle_USB2.0",
        "usb_micro": "Connector:USB_Micro-B",
        "rj45": "Connector:RJ45_Amphenol_RJHSE5380",
        "barrel_jack": "Connector:Barrel_Jack",
        "xt60": "Connector:XT60",
    }
    
    MCU_SYMBOLS = {
        "esp32_devkit": ("RF_Module:ESP32-WROOM-32", "RF_Module:ESP32-WROOM-32"),
        "esp32_c3": ("RF_Module:ESP32-C3-WROOM-02", "RF_Module:ESP32-C3-WROOM-02"),
        "esp32_s3": ("RF_Module:ESP32-S3-WROOM-1", "RF_Module:ESP32-S3-WROOM-1"),
        "arduino_nano": ("MCU_Module:Arduino_Nano_v3.x", "Module:Arduino_Nano"),
        "stm32_bluepill": ("MCU_ST_STM32F1:STM32F103C8Tx", "Package_QFP:LQFP-48_7x7mm_P0.5mm"),
        "rpi_4b": ("", ""),  # RPi usually external
    }
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()
        self.advisor = JunctionAdvisor(config_path)
        
    def _load_config(self) -> dict[str, Any]:
        """Load device.yaml configuration."""
        with open(self.config_path) as f:
            return yaml.safe_load(f)
    
    def generate_project(self, output_dir: Path, template: str = "modular"):
        """Generate complete KiCAD project."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        project_name = self.config["device"]["id"].replace("-", "_")
        
        # Generate project file
        self._generate_project_file(output_dir, project_name)
        
        # Generate schematic(s) based on template
        if template == "modular":
            self._generate_modular_schematic(output_dir, project_name)
        else:
            self._generate_flat_schematic(output_dir, project_name)
        
        # Generate custom symbol library
        self._generate_symbol_library(output_dir, project_name)
        
        # Generate BOM template
        self._generate_bom(output_dir, project_name)
        
        # Generate design notes with junction recommendations
        self._generate_design_notes(output_dir)
    
    def _generate_project_file(self, output_dir: Path, name: str):
        """Generate .kicad_pro project file."""
        project = {
            "meta": {
                "filename": f"{name}.kicad_pro",
                "version": 1
            },
            "project": {
                "name": name,
                "schematic": {
                    "legacy_lib_dir": "",
                    "legacy_lib_list": []
                },
                "sheets": [],
                "text_variables": {
                    "DEVICE_ID": self.config["device"]["id"],
                    "DEVICE_NAME": self.config["device"]["name"],
                    "VERSION": self.config["device"].get("version", "0.1.0"),
                }
            }
        }
        
        with open(output_dir / f"{name}.kicad_pro", "w") as f:
            json.dump(project, f, indent=2)
    
    def _generate_modular_schematic(self, output_dir: Path, name: str):
        """Generate hierarchical schematic with sheets for each subsystem."""
        
        # Main schematic (top-level)
        main_sch = self._create_schematic_header(name)
        
        # Add hierarchical sheets
        sheets = [
            ("MCU", "mcu.kicad_sch", "MCU and core components"),
            ("Sensors", "sensors.kicad_sch", "All sensor interfaces"),
            ("Actuators", "actuators.kicad_sch", "Motor drivers, relays, outputs"),
            ("Power", "power.kicad_sch", "Power distribution and regulation"),
            ("Connectors", "connectors.kicad_sch", "External connectors and interfaces"),
        ]
        
        y_offset = 50
        for sheet_name, sheet_file, desc in sheets:
            main_sch += self._create_sheet_block(sheet_name, sheet_file, 50, y_offset)
            y_offset += 40
            
            # Generate sub-schematic
            self._generate_subsystem_schematic(output_dir, sheet_file, sheet_name)
        
        main_sch += ")"  # Close main schematic
        
        with open(output_dir / f"{name}.kicad_sch", "w") as f:
            f.write(main_sch)
    
    def _generate_flat_schematic(self, output_dir: Path, name: str):
        """Generate single flat schematic with all components."""
        sch = self._create_schematic_header(name)
        
        # Add MCU
        board = self.config["device"]["board"]["model"]
        if board in self.MCU_SYMBOLS:
            lib_id, fp = self.MCU_SYMBOLS[board]
            sch += self._create_symbol("U1", lib_id, fp, 100, 100, "MCU")
        
        # Add sensors
        y_offset = 50
        for i, sensor in enumerate(self.config.get("sensors", []), 1):
            sensor_type = sensor["type"]
            if sensor_type in self.SENSOR_SYMBOLS:
                lib_id, fp = self.SENSOR_SYMBOLS[sensor_type]
                ref = f"U{i+1}"
                sch += self._create_symbol(ref, lib_id, fp, 200, y_offset, sensor["name"])
                y_offset += 30
        
        # Add actuators
        for i, actuator in enumerate(self.config.get("actuators", []), 1):
            actuator_type = actuator["type"]
            if actuator_type in self.ACTUATOR_SYMBOLS:
                lib_id, fp = self.ACTUATOR_SYMBOLS[actuator_type]
                ref = f"Q{i}" if actuator_type == "pwm" else f"K{i}"
                sch += self._create_symbol(ref, lib_id, fp, 300, y_offset, actuator["name"])
                y_offset += 30
        
        sch += ")"
        
        with open(output_dir / f"{name}.kicad_sch", "w") as f:
            f.write(sch)
    
    def _generate_subsystem_schematic(self, output_dir: Path, filename: str, subsystem: str):
        """Generate schematic for a specific subsystem."""
        sch = self._create_schematic_header(subsystem)
        
        if subsystem == "MCU":
            board = self.config["device"]["board"]["model"]
            if board in self.MCU_SYMBOLS:
                lib_id, fp = self.MCU_SYMBOLS[board]
                sch += self._create_symbol("U1", lib_id, fp, 100, 100, "MCU")
            
            # Add decoupling caps, reset circuit, etc.
            sch += self._create_symbol("C1", "Device:C", "Capacitor_SMD:C_0603", 80, 150, "100nF")
            sch += self._create_symbol("C2", "Device:C", "Capacitor_SMD:C_0603", 120, 150, "100nF")
            
        elif subsystem == "Sensors":
            y_offset = 50
            for i, sensor in enumerate(self.config.get("sensors", []), 1):
                sensor_type = sensor["type"]
                if sensor_type in self.SENSOR_SYMBOLS:
                    lib_id, fp = self.SENSOR_SYMBOLS[sensor_type]
                    sch += self._create_symbol(f"U{i}", lib_id, fp, 100, y_offset, sensor["name"])
                    y_offset += 40
                    
        elif subsystem == "Actuators":
            y_offset = 50
            for i, actuator in enumerate(self.config.get("actuators", []), 1):
                actuator_type = actuator["type"]
                if actuator_type in self.ACTUATOR_SYMBOLS:
                    lib_id, fp = self.ACTUATOR_SYMBOLS[actuator_type]
                    ref = f"Q{i}" if actuator_type == "pwm" else f"K{i}"
                    sch += self._create_symbol(ref, lib_id, fp, 100, y_offset, actuator["name"])
                    y_offset += 40
                    
        elif subsystem == "Power":
            # Add voltage regulator, protection, etc.
            sch += self._create_symbol("U_REG", "Regulator_Linear:AMS1117-3.3", 
                                        "Package_TO_SOT_SMD:SOT-223-3", 100, 100, "3.3V Reg")
            sch += self._create_symbol("D1", "Device:D_Schottky", 
                                        "Diode_SMD:D_SMA", 60, 100, "Reverse Protection")
            sch += self._create_symbol("F1", "Device:Polyfuse", 
                                        "Fuse:Fuse_1210_3225Metric", 40, 100, "500mA")
                    
        elif subsystem == "Connectors":
            y_offset = 50
            for conn in self.config.get("hardware", {}).get("connectors", []):
                conn_type = conn["connector_type"]
                pin_count = len(conn.get("signals", []))
                
                # Find matching symbol
                for prefix, symbol_template in self.CONNECTOR_SYMBOLS.items():
                    if prefix in conn_type:
                        symbol = symbol_template.format(n=pin_count)
                        sch += self._create_symbol(conn["name"], symbol, "", 100, y_offset, 
                                                    ", ".join(conn.get("signals", [])))
                        y_offset += 30 + (pin_count * 2.54)
                        break
        
        sch += ")"
        
        with open(output_dir / filename, "w") as f:
            f.write(sch)
    
    def _create_schematic_header(self, name: str) -> str:
        """Create KiCAD schematic file header."""
        return f'''(kicad_sch (version 20230121) (generator oasis_kicad)
  (uuid "{self._generate_uuid()}")
  (paper "A4")
  (title_block
    (title "{name}")
    (company "Oasis")
    (comment 1 "Generated by oasis-kicad")
    (comment 2 "Device: {self.config['device']['id']}")
  )
'''
    
    def _create_symbol(self, ref: str, lib_id: str, footprint: str, 
                       x: float, y: float, value: str) -> str:
        """Create a symbol instance."""
        uuid = self._generate_uuid()
        return f'''
  (symbol (lib_id "{lib_id}") (at {x} {y} 0) (unit 1)
    (uuid "{uuid}")
    (property "Reference" "{ref}" (at {x} {y-5} 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{value}" (at {x} {y+5} 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "{footprint}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))
  )
'''
    
    def _create_sheet_block(self, name: str, filename: str, x: float, y: float) -> str:
        """Create a hierarchical sheet block."""
        uuid = self._generate_uuid()
        return f'''
  (sheet (at {x} {y}) (size 30 15)
    (uuid "{uuid}")
    (property "Sheetname" "{name}" (at {x} {y-2} 0) (effects (font (size 1.5 1.5))))
    (property "Sheetfile" "{filename}" (at {x} {y+17} 0) (effects (font (size 1.27 1.27))))
  )
'''
    
    def _generate_uuid(self) -> str:
        """Generate a UUID for KiCAD."""
        import uuid
        return str(uuid.uuid4())
    
    def _generate_symbol_library(self, output_dir: Path, name: str):
        """Generate custom symbol library with project-specific symbols."""
        lib_content = f'''(kicad_symbol_lib (version 20220914) (generator oasis_kicad)
  ; Custom symbols for {name}
  ; Add project-specific symbols here
)
'''
        with open(output_dir / f"{name}.kicad_sym", "w") as f:
            f.write(lib_content)
    
    def _generate_bom(self, output_dir: Path, name: str):
        """Generate BOM template with component recommendations."""
        bom = {
            "project": name,
            "generated_by": "oasis-kicad",
            "components": []
        }
        
        # MCU
        board = self.config["device"]["board"]["model"]
        bom["components"].append({
            "reference": "U1",
            "type": "MCU",
            "value": board,
            "quantity": 1,
            "suggested_suppliers": ["DigiKey", "Mouser", "LCSC"],
        })
        
        # Sensors
        for i, sensor in enumerate(self.config.get("sensors", []), 2):
            bom["components"].append({
                "reference": f"U{i}",
                "type": "Sensor",
                "value": sensor["type"],
                "quantity": 1,
                "notes": sensor.get("name", ""),
            })
        
        # Connectors
        for conn in self.config.get("hardware", {}).get("connectors", []):
            bom["components"].append({
                "reference": conn["name"],
                "type": "Connector",
                "value": conn["connector_type"],
                "quantity": 1,
                "signals": conn.get("signals", []),
            })
        
        with open(output_dir / f"{name}_bom.json", "w") as f:
            json.dump(bom, f, indent=2)
    
    def _generate_design_notes(self, output_dir: Path):
        """Generate design notes with junction recommendations."""
        recommendations = self.advisor.analyze()
        
        notes = f"""# Design Notes for {self.config['device']['name']}

Generated by oasis-kicad from device.yaml

## Connector Recommendations

| Interface | Recommended Type | Pin Count | Notes |
|-----------|------------------|-----------|-------|
"""
        for conn in recommendations.get("connectors", []):
            notes += f"| {conn['interface']} | {conn['connector_type']} | {conn['signal_count']} | {conn.get('notes', '')} |\n"
        
        notes += """

## Cable Specifications

| Connection | Type | Max Length | Shielding |
|------------|------|------------|-----------|
"""
        for cable in recommendations.get("cables", []):
            notes += f"| {cable['connection']} | {cable['cable_type']} | {cable['max_length']} | {cable.get('shielding', 'None')} |\n"
        
        notes += """

## Enclosure Considerations

"""
        for item in recommendations.get("enclosure", []):
            notes += f"- {item}\n"
        
        notes += """

## Power Distribution

"""
        for item in recommendations.get("power", []):
            notes += f"- {item}\n"
        
        if recommendations.get("warnings"):
            notes += """

## Design Warnings

"""
            for warning in recommendations.get("warnings", []):
                notes += f"⚠️ {warning}\n"
        
        with open(output_dir / "DESIGN_NOTES.md", "w") as f:
            f.write(notes)
