"""Import KiCAD projects to device.yaml format."""

import re
from pathlib import Path
from typing import Any
import yaml

from .kicad_parser import KiCadSchematicParser, KiCadPcbParser
from .component_mapper import ComponentMapper


class KiCadImporter:
    """Import existing KiCAD projects into device.yaml configuration."""
    
    # Known sensor ICs and their types
    SENSOR_ICS = {
        "DHT11": "dht11",
        "DHT22": "dht22",
        "AM2302": "dht22",
        "BME280": "bme280",
        "BME680": "bme680",
        "BMP280": "bme280",
        "SHT31": "sht31",
        "DS18B20": "ds18b20",
        "MPU6050": "mpu6050",
        "MPU9250": "mpu9250",
        "BNO055": "bno055",
        "BH1750": "bh1750",
        "TSL2561": "tsl2561",
        "VEML7700": "veml7700",
        "HC-SR04": "hcsr04",
        "VL53L0X": "vl53l0x",
        "INA219": "ina219",
        "ACS712": "acs712",
        "HX711": "hx711",
        "NEO-6M": "bno055",  # GPS modules map to orientation for now
        "NEO-M8N": "bno055",
    }
    
    # Known actuator ICs
    ACTUATOR_ICS = {
        "ULN2003": "relay",
        "L298N": "dc_motor",
        "DRV8825": "stepper_drv8825",
        "A4988": "stepper_a4988",
        "TMC2209": "stepper_tmc2209",
        "PCA9685": "pca9685",
        "MCP23017": "mcp23017",
    }
    
    # Known MCU/SBC footprints
    BOARD_FOOTPRINTS = {
        "ESP32-DEVKIT": ("mcu", "esp32_devkit"),
        "ESP32-C3": ("mcu", "esp32_c3"),
        "ESP32-S3": ("mcu", "esp32_s3"),
        "ARDUINO-UNO": ("mcu", "arduino_uno"),
        "ARDUINO-NANO": ("mcu", "arduino_nano"),
        "ARDUINO-MEGA": ("mcu", "arduino_mega"),
        "STM32F103": ("mcu", "stm32_bluepill"),
        "STM32F411": ("mcu", "stm32_blackpill"),
        "TEENSY-4.0": ("mcu", "teensy_40"),
        "TEENSY-4.1": ("mcu", "teensy_41"),
        "RASPBERRY-PI": ("rpi", "rpi_4b"),
        "RPI-PICO": ("mcu", "rpi_pico"),
    }
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.project_dir = project_path.parent if project_path.suffix else project_path
        self.project_name = project_path.stem
        
        self.sch_parser = KiCadSchematicParser()
        self.pcb_parser = KiCadPcbParser()
        self.component_mapper = ComponentMapper()
        
    def import_project(self, include_footprints: bool = True) -> dict[str, Any]:
        """Parse KiCAD project and generate device.yaml structure."""
        
        # Find schematic and PCB files
        sch_file = self._find_file(".kicad_sch")
        pcb_file = self._find_file(".kicad_pcb")
        
        components = []
        nets = []
        
        if sch_file:
            sch_data = self.sch_parser.parse(sch_file)
            components = sch_data.get("components", [])
            nets = sch_data.get("nets", [])
            
        if pcb_file and include_footprints:
            pcb_data = self.pcb_parser.parse(pcb_file)
            # Merge footprint info into components
            self._merge_footprints(components, pcb_data.get("footprints", []))
        
        # Build device.yaml structure
        return self._build_device_config(components, nets)
    
    def _find_file(self, extension: str) -> Path | None:
        """Find file with given extension in project directory."""
        matches = list(self.project_dir.glob(f"*{extension}"))
        if matches:
            return matches[0]
        # Check for hierarchical sheets
        matches = list(self.project_dir.glob(f"**/*{extension}"))
        return matches[0] if matches else None
    
    def _merge_footprints(self, components: list, footprints: list):
        """Merge PCB footprint data into component list."""
        fp_map = {fp["reference"]: fp for fp in footprints}
        for comp in components:
            ref = comp.get("reference", "")
            if ref in fp_map:
                comp["footprint"] = fp_map[ref].get("footprint")
                comp["position"] = fp_map[ref].get("position")
    
    def _build_device_config(self, components: list, nets: list) -> dict[str, Any]:
        """Build device.yaml structure from parsed data."""
        
        config = {
            "device": self._extract_device_info(components),
            "connectivity": {"mode": "direct_mqtt"},
            "auth": {"method": "api_key", "api_key": "${OASIS_DEVICE_API_KEY}"},
            "sensors": [],
            "actuators": [],
            "control_loops": [],
            "hardware": {
                "kicad_project": str(self.project_path),
                "symbols": [],
                "connectors": [],
            }
        }
        
        # Categorize components
        for comp in components:
            ref = comp.get("reference", "")
            value = comp.get("value", "").upper()
            
            # Check if it's a sensor
            sensor_type = self._identify_sensor(value, comp)
            if sensor_type:
                sensor = self._build_sensor(comp, sensor_type)
                config["sensors"].append(sensor)
                config["hardware"]["symbols"].append({
                    "component": sensor["name"],
                    "symbol_ref": ref,
                    "footprint": comp.get("footprint"),
                })
                continue
            
            # Check if it's an actuator driver
            actuator_type = self._identify_actuator(value, comp)
            if actuator_type:
                actuator = self._build_actuator(comp, actuator_type)
                config["actuators"].append(actuator)
                config["hardware"]["symbols"].append({
                    "component": actuator["name"],
                    "symbol_ref": ref,
                    "footprint": comp.get("footprint"),
                })
                continue
            
            # Check if it's a connector
            if ref.startswith("J") or ref.startswith("P"):
                connector = self._build_connector(comp, nets)
                if connector:
                    config["hardware"]["connectors"].append(connector)
        
        return config
    
    def _extract_device_info(self, components: list) -> dict:
        """Extract device/board info from components."""
        device_info = {
            "id": self.project_name.lower().replace(" ", "-"),
            "name": self.project_name,
            "version": "0.1.0",
            "board": {
                "platform": "mcu",
                "model": "esp32_devkit",  # Default
            }
        }
        
        # Look for MCU/SBC in components
        for comp in components:
            value = comp.get("value", "").upper()
            for pattern, (platform, model) in self.BOARD_FOOTPRINTS.items():
                if pattern in value:
                    device_info["board"]["platform"] = platform
                    device_info["board"]["model"] = model
                    break
        
        return device_info
    
    def _identify_sensor(self, value: str, comp: dict) -> str | None:
        """Identify sensor type from component value."""
        for pattern, sensor_type in self.SENSOR_ICS.items():
            if pattern in value:
                return sensor_type
        return None
    
    def _identify_actuator(self, value: str, comp: dict) -> str | None:
        """Identify actuator type from component value."""
        for pattern, actuator_type in self.ACTUATOR_ICS.items():
            if pattern in value:
                return actuator_type
        # Check for generic MOSFETs/transistors used as switches
        if comp.get("reference", "").startswith("Q"):
            return "pwm"
        # Check for relays
        if comp.get("reference", "").startswith("K"):
            return "relay"
        return None
    
    def _build_sensor(self, comp: dict, sensor_type: str) -> dict:
        """Build sensor configuration from component."""
        ref = comp.get("reference", "")
        name = f"sensor_{ref.lower()}"
        
        sensor = {
            "name": name,
            "type": sensor_type,
            "pins": self._extract_pins(comp, is_sensor=True),
            "sampling": {"interval_ms": 1000},
            "output": {
                "measurements": self._get_default_measurements(sensor_type)
            }
        }
        
        return sensor
    
    def _build_actuator(self, comp: dict, actuator_type: str) -> dict:
        """Build actuator configuration from component."""
        ref = comp.get("reference", "")
        name = f"actuator_{ref.lower()}"
        
        actuator = {
            "name": name,
            "type": actuator_type,
            "pins": self._extract_pins(comp, is_sensor=False),
        }
        
        return actuator
    
    def _build_connector(self, comp: dict, nets: list) -> dict | None:
        """Build connector configuration from component."""
        ref = comp.get("reference", "")
        value = comp.get("value", "")
        
        # Extract pin count from value (e.g., "Conn_01x04" -> 4)
        pin_match = re.search(r"(\d+)x(\d+)", value)
        if not pin_match:
            return None
        
        pin_count = int(pin_match.group(2))
        
        # Try to identify connector type
        conn_type = self._identify_connector_type(value, pin_count)
        
        # Find connected signals from nets
        signals = self._find_connector_signals(ref, nets, pin_count)
        
        return {
            "name": ref,
            "connector_type": conn_type,
            "signals": signals,
            "symbol_ref": ref,
        }
    
    def _identify_connector_type(self, value: str, pin_count: int) -> str:
        """Identify connector type from value string."""
        value_upper = value.upper()
        
        if "JST" in value_upper:
            if "XH" in value_upper:
                return f"jst_xh_{pin_count}"
            elif "PH" in value_upper:
                return f"jst_ph_{pin_count}"
            elif "SH" in value_upper:
                return f"jst_sh_{pin_count}"
            return f"jst_{pin_count}"
        elif "SCREW" in value_upper:
            return f"screw_terminal_{pin_count}p"
        elif "RJ45" in value_upper:
            return "rj45"
        elif "USB" in value_upper:
            return "usb_c" if "C" in value_upper else "usb_micro"
        elif "XT60" in value_upper:
            return "xt60"
        elif "XT30" in value_upper:
            return "xt30"
        elif "BARREL" in value_upper:
            return "barrel_jack"
        else:
            return f"header_{pin_count}p"
    
    def _find_connector_signals(self, ref: str, nets: list, pin_count: int) -> list[str]:
        """Find signal names connected to a connector."""
        signals = ["NC"] * pin_count
        
        for net in nets:
            for pin in net.get("pins", []):
                if pin.get("ref") == ref:
                    pin_num = pin.get("pin", 1)
                    if 1 <= pin_num <= pin_count:
                        signals[pin_num - 1] = net.get("name", "NC")
        
        return signals
    
    def _extract_pins(self, comp: dict, is_sensor: bool) -> dict:
        """Extract pin assignments from component."""
        pins = {}
        
        # This would need net connectivity info to be accurate
        # For now, return empty pins to be filled manually
        if is_sensor:
            pins = {"sda": 0, "scl": 0}  # Default I2C
        else:
            pins = {"output": 0}  # Default GPIO
            
        return pins
    
    def _get_default_measurements(self, sensor_type: str) -> list[dict]:
        """Get default measurements for a sensor type."""
        measurements_map = {
            "dht11": [
                {"name": "temperature", "unit": "°C"},
                {"name": "humidity", "unit": "%"},
            ],
            "dht22": [
                {"name": "temperature", "unit": "°C"},
                {"name": "humidity", "unit": "%"},
            ],
            "bme280": [
                {"name": "temperature", "unit": "°C"},
                {"name": "humidity", "unit": "%"},
                {"name": "pressure", "unit": "hPa"},
            ],
            "bme680": [
                {"name": "temperature", "unit": "°C"},
                {"name": "humidity", "unit": "%"},
                {"name": "pressure", "unit": "hPa"},
                {"name": "gas", "unit": "Ω"},
            ],
            "mpu6050": [
                {"name": "accel_x", "unit": "m/s²"},
                {"name": "accel_y", "unit": "m/s²"},
                {"name": "accel_z", "unit": "m/s²"},
                {"name": "gyro_x", "unit": "rad/s"},
                {"name": "gyro_y", "unit": "rad/s"},
                {"name": "gyro_z", "unit": "rad/s"},
            ],
            "mpu9250": [
                {"name": "accel_x", "unit": "m/s²"},
                {"name": "accel_y", "unit": "m/s²"},
                {"name": "accel_z", "unit": "m/s²"},
                {"name": "gyro_x", "unit": "rad/s"},
                {"name": "gyro_y", "unit": "rad/s"},
                {"name": "gyro_z", "unit": "rad/s"},
                {"name": "mag_x", "unit": "µT"},
                {"name": "mag_y", "unit": "µT"},
                {"name": "mag_z", "unit": "µT"},
            ],
            "bh1750": [{"name": "illuminance", "unit": "lux"}],
            "hcsr04": [{"name": "distance", "unit": "cm"}],
            "ina219": [
                {"name": "voltage", "unit": "V"},
                {"name": "current", "unit": "A"},
                {"name": "power", "unit": "W"},
            ],
        }
        
        return measurements_map.get(sensor_type, [{"name": "value", "unit": ""}])
    
    def write_device_yaml(self, config: dict, output_path: Path):
        """Write device configuration to YAML file."""
        with open(output_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
