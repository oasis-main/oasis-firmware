"""Junction and interconnect design advisor.

Provides recommendations for intermediate junction points that bridge
SCADA logic (sensors/actuators) with physical hardware:
- Connectors
- Cables
- Enclosures
- EMI considerations
- Power distribution
"""

from pathlib import Path
from typing import Any
import yaml


class JunctionAdvisor:
    """Analyze device.yaml and recommend junction/interconnect designs."""
    
    # Connector recommendations by interface type and environment
    CONNECTOR_RECOMMENDATIONS = {
        # (interface_type, environment) -> (connector_type, notes)
        ("i2c", "indoor"): ("jst_sh_4", "Compact, 4-pin: VCC, GND, SDA, SCL"),
        ("i2c", "outdoor"): ("m8_4pin", "IP67 rated, vibration resistant"),
        ("i2c", "industrial"): ("m12_4pin", "IP68, shielded for EMI"),
        
        ("spi", "indoor"): ("jst_xh_6", "6-pin: VCC, GND, MOSI, MISO, SCK, CS"),
        ("spi", "outdoor"): ("m8_6pin", "IP67, shielded"),
        
        ("uart", "indoor"): ("jst_xh_4", "4-pin: VCC, GND, TX, RX"),
        ("uart", "outdoor"): ("m8_4pin", "IP67"),
        
        ("onewire", "indoor"): ("jst_ph_3", "3-pin: VCC, DATA, GND"),
        ("onewire", "outdoor"): ("m8_3pin", "IP67, with pullup on PCB"),
        
        ("gpio", "indoor"): ("jst_xh_2", "2-pin for single output"),
        ("gpio", "outdoor"): ("m8_2pin", "IP67"),
        
        ("analog", "indoor"): ("jst_sh_3", "3-pin: VCC, SIG, GND"),
        ("analog", "outdoor"): ("m8_3pin", "Shielded for noise immunity"),
        
        ("power_low", "indoor"): ("jst_xh_2", "< 3A"),
        ("power_low", "outdoor"): ("xt30", "< 15A, weather resistant"),
        ("power_high", "indoor"): ("xt60", "< 30A"),
        ("power_high", "outdoor"): ("anderson_pp", "< 50A, IP rated"),
        
        ("ethernet", "indoor"): ("rj45", "Standard Cat5e/6"),
        ("ethernet", "outdoor"): ("rj45_ip67", "Shielded, IP67 housing"),
        
        ("usb", "indoor"): ("usb_c", "USB 2.0 data + power"),
        ("usb", "outdoor"): ("usb_c_ip67", "Sealed USB-C"),
    }
    
    # Cable recommendations by signal type
    CABLE_RECOMMENDATIONS = {
        "i2c": {
            "type": "4-wire shielded",
            "max_length": "1m @ 400kHz, 3m @ 100kHz",
            "notes": "Keep short, use pullups at master",
        },
        "spi": {
            "type": "6-wire ribbon or shielded",
            "max_length": "30cm @ 10MHz",
            "notes": "Very sensitive to length, ground between signals",
        },
        "uart": {
            "type": "3/4-wire, can be unshielded",
            "max_length": "15m @ 115200bps",
            "notes": "RS-485 for longer runs",
        },
        "onewire": {
            "type": "2/3-wire, parasitic or powered",
            "max_length": "100m with good topology",
            "notes": "Star topology, strong pullup",
        },
        "analog": {
            "type": "Shielded twisted pair",
            "max_length": "Varies by signal level",
            "notes": "Shield to GND at one end only",
        },
        "gpio": {
            "type": "2-wire",
            "max_length": "10m for slow signals",
            "notes": "Add ESD protection for long runs",
        },
        "pwm": {
            "type": "2/3-wire",
            "max_length": "3m",
            "notes": "Keep away from analog signals",
        },
        "power": {
            "type": "2-wire, gauge by current",
            "max_length": "Based on voltage drop",
            "notes": "Calculate wire gauge: P = I²R",
        },
    }
    
    # Enclosure considerations by environment
    ENCLOSURE_GUIDELINES = {
        "indoor": [
            "ABS or polycarbonate enclosure",
            "Ventilation slots acceptable",
            "Cable glands PG7/PG9 for wire entry",
            "Consider DIN rail mounting for industrial",
        ],
        "outdoor": [
            "IP65 minimum rating (IP67 preferred)",
            "UV-stabilized material",
            "Sealed cable glands with strain relief",
            "Consider thermal management (vents with filters or heatsink)",
            "Mounting boss for wall/pole mounting",
        ],
        "industrial": [
            "IP67/IP68 rating",
            "Metal enclosure for EMI shielding",
            "M12/M8 panel-mount connectors",
            "DIN rail or flange mounting",
            "Consider explosion-proof if needed",
        ],
        "mobile": [
            "Shock and vibration resistant",
            "Lightweight (aluminum or reinforced plastic)",
            "Locking connectors (bayonet or threaded)",
            "Conformal coating on PCB",
        ],
    }
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()
        self.kicad_data = None
        
    def _load_config(self) -> dict[str, Any]:
        """Load device.yaml configuration."""
        with open(self.config_path) as f:
            return yaml.safe_load(f)
    
    def load_kicad_project(self, kicad_path: Path):
        """Load KiCAD project for cross-reference."""
        from .kicad_parser import KiCadSchematicParser, KiCadPcbParser
        
        sch_parser = KiCadSchematicParser()
        pcb_parser = KiCadPcbParser()
        
        sch_file = list(kicad_path.parent.glob("*.kicad_sch"))
        pcb_file = list(kicad_path.parent.glob("*.kicad_pcb"))
        
        self.kicad_data = {}
        if sch_file:
            self.kicad_data["schematic"] = sch_parser.parse(sch_file[0])
        if pcb_file:
            self.kicad_data["pcb"] = pcb_parser.parse(pcb_file[0])
    
    def analyze(self) -> dict[str, Any]:
        """Analyze configuration and generate recommendations."""
        environment = self._detect_environment()
        
        return {
            "connectors": self._recommend_connectors(environment),
            "cables": self._recommend_cables(),
            "enclosure": self._recommend_enclosure(environment),
            "power": self._recommend_power_distribution(),
            "warnings": self._generate_warnings(),
        }
    
    def _detect_environment(self) -> str:
        """Detect deployment environment from config hints."""
        device_name = self.config.get("device", {}).get("name", "").lower()
        device_desc = self.config.get("device", {}).get("description", "").lower()
        
        combined = device_name + " " + device_desc
        
        if any(kw in combined for kw in ["outdoor", "weather", "garden", "greenhouse"]):
            return "outdoor"
        elif any(kw in combined for kw in ["industrial", "factory", "machine"]):
            return "industrial"
        elif any(kw in combined for kw in ["drone", "robot", "vehicle", "mobile"]):
            return "mobile"
        else:
            return "indoor"
    
    def _recommend_connectors(self, environment: str) -> list[dict]:
        """Recommend connectors for each interface."""
        recommendations = []
        
        # Analyze sensors
        for sensor in self.config.get("sensors", []):
            interface = self._get_sensor_interface(sensor)
            key = (interface, environment)
            
            if key in self.CONNECTOR_RECOMMENDATIONS:
                conn_type, notes = self.CONNECTOR_RECOMMENDATIONS[key]
            else:
                # Fallback
                conn_type, notes = self.CONNECTOR_RECOMMENDATIONS.get(
                    (interface, "indoor"), ("jst_xh_4", "Generic 4-pin")
                )
            
            recommendations.append({
                "interface": f"Sensor: {sensor['name']}",
                "interface_type": interface,
                "connector_type": conn_type,
                "signal_count": self._count_signals(sensor, interface),
                "notes": notes,
            })
        
        # Analyze actuators
        for actuator in self.config.get("actuators", []):
            interface = self._get_actuator_interface(actuator)
            power_level = "power_high" if actuator["type"] in ["dc_motor", "stepper"] else "gpio"
            key = (power_level if "motor" in actuator["type"] else interface, environment)
            
            if key in self.CONNECTOR_RECOMMENDATIONS:
                conn_type, notes = self.CONNECTOR_RECOMMENDATIONS[key]
            else:
                conn_type, notes = ("jst_xh_3", "Generic 3-pin")
            
            recommendations.append({
                "interface": f"Actuator: {actuator['name']}",
                "interface_type": interface,
                "connector_type": conn_type,
                "signal_count": self._count_actuator_signals(actuator),
                "notes": notes,
            })
        
        # Power input
        power_key = ("power_high" if self._estimate_power() > 10 else "power_low", environment)
        conn_type, notes = self.CONNECTOR_RECOMMENDATIONS.get(power_key, ("xt30", "Power input"))
        recommendations.append({
            "interface": "Power Input",
            "interface_type": "power",
            "connector_type": conn_type,
            "signal_count": 2,
            "notes": f"Estimated load: {self._estimate_power():.1f}W - {notes}",
        })
        
        # Communication
        if self.config.get("connectivity", {}).get("serial"):
            recommendations.append({
                "interface": "Serial/UART",
                "interface_type": "uart",
                "connector_type": "jst_xh_4" if environment == "indoor" else "m8_4pin",
                "signal_count": 4,
                "notes": "VCC, GND, TX, RX",
            })
        
        return recommendations
    
    def _recommend_cables(self) -> list[dict]:
        """Recommend cable specifications."""
        cables = []
        
        for sensor in self.config.get("sensors", []):
            interface = self._get_sensor_interface(sensor)
            if interface in self.CABLE_RECOMMENDATIONS:
                rec = self.CABLE_RECOMMENDATIONS[interface]
                cables.append({
                    "connection": f"MCU ↔ {sensor['name']}",
                    "cable_type": rec["type"],
                    "max_length": rec["max_length"],
                    "shielding": "Shielded" if "shielded" in rec["type"].lower() else "None",
                    "notes": rec["notes"],
                })
        
        for actuator in self.config.get("actuators", []):
            interface = self._get_actuator_interface(actuator)
            rec = self.CABLE_RECOMMENDATIONS.get(interface, self.CABLE_RECOMMENDATIONS["gpio"])
            cables.append({
                "connection": f"MCU ↔ {actuator['name']}",
                "cable_type": rec["type"],
                "max_length": rec["max_length"],
                "shielding": "Shielded" if "motor" in actuator["type"] else "None",
                "notes": rec["notes"],
            })
        
        return cables
    
    def _recommend_enclosure(self, environment: str) -> list[str]:
        """Recommend enclosure specifications."""
        base_recommendations = self.ENCLOSURE_GUIDELINES.get(environment, self.ENCLOSURE_GUIDELINES["indoor"])
        
        recommendations = list(base_recommendations)
        
        # Add size estimate
        sensor_count = len(self.config.get("sensors", []))
        actuator_count = len(self.config.get("actuators", []))
        connector_count = len(self.config.get("hardware", {}).get("connectors", []))
        
        if sensor_count + actuator_count < 5:
            recommendations.append("Suggested size: ~100x68x50mm (small project box)")
        elif sensor_count + actuator_count < 10:
            recommendations.append("Suggested size: ~150x100x60mm (medium enclosure)")
        else:
            recommendations.append("Suggested size: ~200x150x75mm (large enclosure)")
        
        # Add mounting recommendations
        board = self.config.get("device", {}).get("board", {}).get("model", "")
        if "rpi" in board:
            recommendations.append("Include RPi mounting holes (58mm x 49mm pattern)")
        elif "esp32" in board:
            recommendations.append("Include ESP32 module mounting (varies by variant)")
        
        return recommendations
    
    def _recommend_power_distribution(self) -> list[str]:
        """Recommend power distribution topology."""
        recommendations = []
        
        estimated_power = self._estimate_power()
        sensor_count = len(self.config.get("sensors", []))
        actuator_count = len(self.config.get("actuators", []))
        
        # Voltage rails
        board = self.config.get("device", {}).get("board", {}).get("model", "")
        if "esp32" in board or "arduino" in board:
            recommendations.append("Primary rail: 3.3V (MCU) + 5V (sensors/peripherals)")
            recommendations.append("Add AMS1117-3.3 or similar LDO from 5V input")
        elif "rpi" in board:
            recommendations.append("Primary rail: 5V (via USB-C or GPIO header)")
            recommendations.append("Add 3.3V rail for sensors if needed")
        
        # Protection
        recommendations.append("Reverse polarity protection: Schottky diode or P-FET")
        recommendations.append(f"Overcurrent protection: Polyfuse rated for {estimated_power/5:.1f}A")
        
        # Decoupling
        recommendations.append("Bulk capacitor: 100-470µF at power input")
        recommendations.append("Decoupling: 100nF ceramic per IC")
        
        # High-power actuators
        high_power_actuators = [a for a in self.config.get("actuators", []) 
                               if a["type"] in ["dc_motor", "stepper", "relay"]]
        if high_power_actuators:
            recommendations.append("Separate power rail for motors/relays (isolate from logic)")
            recommendations.append("Add flyback diodes for inductive loads")
            recommendations.append("Consider motor driver current rating headroom (1.5x)")
        
        return recommendations
    
    def _generate_warnings(self) -> list[str]:
        """Generate design warnings based on analysis."""
        warnings = []
        
        # Check for potential issues
        sensors = self.config.get("sensors", [])
        actuators = self.config.get("actuators", [])
        
        # I2C address conflicts
        i2c_addresses = []
        for sensor in sensors:
            if sensor.get("i2c_address"):
                addr = sensor["i2c_address"]
                if addr in i2c_addresses:
                    warnings.append(f"Potential I2C address conflict at 0x{addr:02X}")
                i2c_addresses.append(addr)
        
        # Power budget
        estimated_power = self._estimate_power()
        if estimated_power > 25:
            warnings.append(f"High power consumption (~{estimated_power:.0f}W) - verify supply capacity")
        
        # PWM interference
        pwm_actuators = [a for a in actuators if a["type"] in ["pwm", "dc_motor", "servo"]]
        analog_sensors = [s for s in sensors if s["type"] in ["adc_raw", "acs712", "voltage_divider"]]
        if pwm_actuators and analog_sensors:
            warnings.append("PWM actuators may interfere with analog sensors - add filtering/separation")
        
        # Long cable runs for I2C
        i2c_sensors = [s for s in sensors if s.get("pins", {}).get("sda") is not None]
        if len(i2c_sensors) > 3:
            warnings.append("Multiple I2C devices - consider I2C buffer (PCA9515) for reliability")
        
        # Missing watchdog
        if not self.config.get("system", {}).get("watchdog", {}).get("enabled"):
            warnings.append("Watchdog not enabled - recommend enabling for production")
        
        return warnings
    
    def _get_sensor_interface(self, sensor: dict) -> str:
        """Determine interface type for sensor."""
        pins = sensor.get("pins", {})
        sensor_type = sensor.get("type", "")
        
        if "sda" in pins or "scl" in pins:
            return "i2c"
        elif "mosi" in pins or "miso" in pins:
            return "spi"
        elif "data" in pins:
            return "onewire"
        elif "adc" in pins:
            return "analog"
        elif "tx" in pins or "rx" in pins:
            return "uart"
        else:
            return "gpio"
    
    def _get_actuator_interface(self, actuator: dict) -> str:
        """Determine interface type for actuator."""
        actuator_type = actuator.get("type", "")
        
        if actuator_type in ["pca9685", "mcp23017"]:
            return "i2c"
        elif actuator_type in ["pwm", "servo", "dc_motor"]:
            return "pwm"
        else:
            return "gpio"
    
    def _count_signals(self, sensor: dict, interface: str) -> int:
        """Count signal lines for a sensor."""
        base_counts = {
            "i2c": 4,  # VCC, GND, SDA, SCL
            "spi": 6,  # VCC, GND, MOSI, MISO, SCK, CS
            "uart": 4,  # VCC, GND, TX, RX
            "onewire": 3,  # VCC, DATA, GND
            "analog": 3,  # VCC, SIG, GND
            "gpio": 3,  # VCC, SIG, GND
        }
        return base_counts.get(interface, 3)
    
    def _count_actuator_signals(self, actuator: dict) -> int:
        """Count signal lines for an actuator."""
        actuator_type = actuator.get("type", "")
        
        counts = {
            "relay": 3,  # VCC, GND, IN
            "pwm": 3,  # VCC, GND, PWM
            "servo": 3,  # VCC, GND, SIG
            "dc_motor": 4,  # VCC, GND, IN1, IN2 (or PWM)
            "stepper": 6,  # VCC, GND, STEP, DIR, EN, MS1
            "led": 2,  # Anode, Cathode (or 3 with GND)
        }
        return counts.get(actuator_type, 3)
    
    def _estimate_power(self) -> float:
        """Estimate total power consumption in watts."""
        power = 0.0
        
        # MCU power
        board = self.config.get("device", {}).get("board", {}).get("model", "")
        if "esp32" in board:
            power += 0.5  # ~100mA @ 5V typical
        elif "rpi" in board:
            power += 3.0  # ~600mA @ 5V typical
        elif "arduino" in board:
            power += 0.25  # ~50mA @ 5V
        else:
            power += 0.5
        
        # Sensor power (most are low power)
        power += len(self.config.get("sensors", [])) * 0.05
        
        # Actuator power
        for actuator in self.config.get("actuators", []):
            actuator_type = actuator.get("type", "")
            if actuator_type in ["dc_motor", "stepper"]:
                power += 5.0  # Varies widely
            elif actuator_type == "relay":
                power += 0.5  # Coil power
            elif actuator_type == "servo":
                power += 1.0
            else:
                power += 0.1
        
        return power
