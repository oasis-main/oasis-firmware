"""Component YAML Schema - Defines the structure for behavioral component models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import yaml


class SignalType(Enum):
    DIGITAL = "digital"
    ANALOG = "analog"
    I2C = "i2c"
    SPI = "spi"
    UART = "uart"
    SINGLE_WIRE = "single_wire"
    PWM = "pwm"


class ComponentType(Enum):
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    MCU = "mcu"
    PASSIVE = "passive"


class NoiseModel(Enum):
    NONE = "none"
    GAUSSIAN = "gaussian"
    UNIFORM = "uniform"
    DRIFT = "drift"


@dataclass
class SignalPort:
    """A signal input or output port on a component."""
    name: str
    signal_type: SignalType
    unit: str = ""
    range_min: float = 0.0
    range_max: float = 1.0
    resolution_bits: int = 12
    protocol: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "SignalPort":
        return cls(
            name=data["name"],
            signal_type=SignalType(data.get("type", "analog")),
            unit=data.get("unit", ""),
            range_min=data.get("range_min", 0.0),
            range_max=data.get("range_max", 1.0),
            resolution_bits=data.get("resolution_bits", 12),
            protocol=data.get("protocol"),
        )


@dataclass
class Parameter:
    """A configurable parameter of a component."""
    name: str
    value: Any
    unit: str = ""
    description: str = ""
    
    @classmethod
    def from_dict(cls, name: str, data: Any) -> "Parameter":
        if isinstance(data, dict):
            return cls(
                name=name,
                value=data.get("value", data.get("default")),
                unit=data.get("unit", ""),
                description=data.get("description", ""),
            )
        return cls(name=name, value=data)


@dataclass
class BehaviorModel:
    """Defines how a component behaves during simulation."""
    noise_model: NoiseModel = NoiseModel.NONE
    noise_stddev: float = 0.0
    drift_rate: float = 0.0
    startup_delay_ms: int = 0
    read_interval_ms: int = 1000
    response_time_ms: int = 0
    custom_behavior: Optional[str] = None  # Python function name
    
    @classmethod
    def from_dict(cls, data: dict) -> "BehaviorModel":
        return cls(
            noise_model=NoiseModel(data.get("model", "none")),
            noise_stddev=data.get("noise_stddev", data.get("stddev", 0.0)),
            drift_rate=data.get("drift_rate", 0.0),
            startup_delay_ms=data.get("startup_delay_ms", 0),
            read_interval_ms=data.get("read_interval_ms", 1000),
            response_time_ms=data.get("response_time_ms", 0),
            custom_behavior=data.get("custom_behavior"),
        )


@dataclass
class ComponentSchema:
    """Full schema for a behavioral component model."""
    id: str
    name: str
    component_type: ComponentType
    description: str = ""
    manufacturer: str = ""
    datasheet_url: str = ""
    
    inputs: list[SignalPort] = field(default_factory=list)
    outputs: list[SignalPort] = field(default_factory=list)
    parameters: dict[str, Parameter] = field(default_factory=dict)
    behavior: BehaviorModel = field(default_factory=BehaviorModel)
    
    # Protocol-specific config
    i2c_address: Optional[int] = None
    spi_mode: Optional[int] = None
    uart_baud: Optional[int] = None
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> "ComponentSchema":
        """Load a component schema from a YAML file."""
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ComponentSchema":
        """Parse a component schema from a dictionary."""
        component = data.get("component", data)
        
        inputs = [
            SignalPort.from_dict(p) 
            for p in component.get("inputs", [])
        ]
        outputs = [
            SignalPort.from_dict(p) 
            for p in component.get("outputs", [])
        ]
        parameters = {
            k: Parameter.from_dict(k, v)
            for k, v in component.get("parameters", {}).items()
        }
        behavior = BehaviorModel.from_dict(component.get("behavior", {}))
        
        return cls(
            id=component["id"],
            name=component.get("name", component["id"]),
            component_type=ComponentType(component.get("type", "sensor")),
            description=component.get("description", ""),
            manufacturer=component.get("manufacturer", ""),
            datasheet_url=component.get("datasheet_url", ""),
            inputs=inputs,
            outputs=outputs,
            parameters=parameters,
            behavior=behavior,
            i2c_address=component.get("i2c_address"),
            spi_mode=component.get("spi_mode"),
            uart_baud=component.get("uart_baud"),
        )
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "component": {
                "id": self.id,
                "name": self.name,
                "type": self.component_type.value,
                "description": self.description,
                "manufacturer": self.manufacturer,
                "datasheet_url": self.datasheet_url,
                "inputs": [
                    {
                        "name": p.name,
                        "type": p.signal_type.value,
                        "unit": p.unit,
                        "range_min": p.range_min,
                        "range_max": p.range_max,
                    }
                    for p in self.inputs
                ],
                "outputs": [
                    {
                        "name": p.name,
                        "type": p.signal_type.value,
                        "unit": p.unit,
                        "protocol": p.protocol,
                    }
                    for p in self.outputs
                ],
                "parameters": {
                    k: {"value": v.value, "unit": v.unit}
                    for k, v in self.parameters.items()
                },
                "behavior": {
                    "model": self.behavior.noise_model.value,
                    "noise_stddev": self.behavior.noise_stddev,
                    "read_interval_ms": self.behavior.read_interval_ms,
                },
            }
        }
