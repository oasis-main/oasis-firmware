"""Map components between KiCAD and device.yaml formats."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ComponentMapping:
    """Mapping between KiCAD component and device.yaml type."""
    kicad_pattern: str
    device_type: str
    category: str  # "sensor", "actuator", "connector", "mcu", "passive"
    default_pins: dict[str, int]
    measurements: list[dict] | None = None


class ComponentMapper:
    """Map KiCAD components to device.yaml sensor/actuator types."""
    
    MAPPINGS = [
        # Temperature/Humidity sensors
        ComponentMapping("DHT11", "dht11", "sensor", {"data": 0}),
        ComponentMapping("DHT22", "dht22", "sensor", {"data": 0}),
        ComponentMapping("AM2302", "dht22", "sensor", {"data": 0}),
        ComponentMapping("BME280", "bme280", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("BME680", "bme680", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("BMP280", "bme280", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("SHT31", "sht31", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("DS18B20", "ds18b20", "sensor", {"data": 0}),
        
        # IMU sensors
        ComponentMapping("MPU6050", "mpu6050", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("MPU9250", "mpu9250", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("BNO055", "bno055", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("ICM20948", "mpu9250", "sensor", {"sda": 0, "scl": 0}),
        
        # Light sensors
        ComponentMapping("BH1750", "bh1750", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("TSL2561", "tsl2561", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("VEML7700", "veml7700", "sensor", {"sda": 0, "scl": 0}),
        
        # Distance sensors
        ComponentMapping("HC-SR04", "hcsr04", "sensor", {"trigger": 0, "echo": 0}),
        ComponentMapping("VL53L0X", "vl53l0x", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("VL53L1X", "vl53l1x", "sensor", {"sda": 0, "scl": 0}),
        
        # Current/Voltage sensors
        ComponentMapping("INA219", "ina219", "sensor", {"sda": 0, "scl": 0}),
        ComponentMapping("ACS712", "acs712", "sensor", {"adc": 0}),
        
        # Motor drivers
        ComponentMapping("L298N", "dc_motor", "actuator", {"in1": 0, "in2": 0, "en": 0}),
        ComponentMapping("DRV8825", "stepper_drv8825", "actuator", {"step": 0, "dir": 0, "en": 0}),
        ComponentMapping("A4988", "stepper_a4988", "actuator", {"step": 0, "dir": 0, "en": 0}),
        ComponentMapping("TMC2209", "stepper_tmc2209", "actuator", {"step": 0, "dir": 0, "en": 0}),
        
        # PWM/GPIO expanders
        ComponentMapping("PCA9685", "pca9685", "actuator", {"sda": 0, "scl": 0}),
        ComponentMapping("MCP23017", "mcp23017", "actuator", {"sda": 0, "scl": 0}),
        
        # Relay modules
        ComponentMapping("RELAY", "relay", "actuator", {"output": 0}),
        ComponentMapping("ULN2003", "relay", "actuator", {"output": 0}),
    ]
    
    def __init__(self):
        self._build_index()
    
    def _build_index(self):
        """Build lookup index for fast matching."""
        self.pattern_index = {}
        for mapping in self.MAPPINGS:
            self.pattern_index[mapping.kicad_pattern.upper()] = mapping
    
    def identify(self, value: str, reference: str = "") -> ComponentMapping | None:
        """Identify component type from KiCAD value/reference."""
        value_upper = value.upper()
        
        # Direct match
        for pattern, mapping in self.pattern_index.items():
            if pattern in value_upper:
                return mapping
        
        # Reference-based inference
        ref_prefix = reference[:1] if reference else ""
        if ref_prefix == "K":
            return ComponentMapping("RELAY", "relay", "actuator", {"output": 0})
        elif ref_prefix == "Q":
            return ComponentMapping("MOSFET", "pwm", "actuator", {"pwm": 0})
        
        return None
    
    def get_interface_type(self, mapping: ComponentMapping) -> str:
        """Determine interface type (I2C, SPI, GPIO, etc.) from pin config."""
        pins = mapping.default_pins
        
        if "sda" in pins and "scl" in pins:
            return "i2c"
        elif "mosi" in pins or "miso" in pins:
            return "spi"
        elif "tx" in pins or "rx" in pins:
            return "uart"
        elif "data" in pins:
            return "onewire"
        elif "adc" in pins:
            return "analog"
        else:
            return "gpio"
