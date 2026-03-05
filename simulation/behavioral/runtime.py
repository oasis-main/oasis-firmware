"""Behavioral Runtime - Executes component models during simulation."""

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from pathlib import Path

from .schema import ComponentSchema, NoiseModel, SignalType


@dataclass
class SignalValue:
    """A value on the signal bus."""
    name: str
    value: Any
    timestamp_ms: int
    signal_type: SignalType


@dataclass
class ComponentInstance:
    """A runtime instance of a component."""
    instance_id: str
    schema: ComponentSchema
    state: dict[str, Any] = field(default_factory=dict)
    last_read_ms: int = 0
    started: bool = False
    startup_complete_ms: int = 0
    
    def __post_init__(self):
        # Initialize state with default parameter values
        for name, param in self.schema.parameters.items():
            self.state[name] = param.value


class SignalBus:
    """Shared signal bus for inter-component communication."""
    
    def __init__(self):
        self._signals: dict[str, SignalValue] = {}
        self._listeners: dict[str, list[Callable[[SignalValue], None]]] = {}
    
    def set(self, name: str, value: Any, signal_type: SignalType, timestamp_ms: int):
        """Set a signal value."""
        sv = SignalValue(name=name, value=value, timestamp_ms=timestamp_ms, signal_type=signal_type)
        self._signals[name] = sv
        
        # Notify listeners
        if name in self._listeners:
            for callback in self._listeners[name]:
                callback(sv)
    
    def get(self, name: str) -> Optional[SignalValue]:
        """Get a signal value."""
        return self._signals.get(name)
    
    def subscribe(self, name: str, callback: Callable[[SignalValue], None]):
        """Subscribe to signal changes."""
        if name not in self._listeners:
            self._listeners[name] = []
        self._listeners[name].append(callback)
    
    def get_all(self) -> dict[str, SignalValue]:
        """Get all current signal values."""
        return dict(self._signals)


class BehavioralRuntime:
    """Main runtime for behavioral simulation."""
    
    def __init__(self):
        self.signal_bus = SignalBus()
        self.components: dict[str, ComponentInstance] = {}
        self.sim_time_ms: int = 0
        self.running: bool = False
        self._component_schemas: dict[str, ComponentSchema] = {}
    
    def load_component_library(self, library_path: Path):
        """Load all component schemas from a directory."""
        for yaml_file in library_path.rglob("*.yaml"):
            try:
                schema = ComponentSchema.from_yaml(str(yaml_file))
                self._component_schemas[schema.id] = schema
            except Exception as e:
                print(f"Warning: Failed to load {yaml_file}: {e}")
    
    def get_available_components(self) -> list[str]:
        """List available component types."""
        return list(self._component_schemas.keys())
    
    def add_component(self, instance_id: str, component_id: str, **kwargs) -> ComponentInstance:
        """Add a component instance to the simulation."""
        if component_id not in self._component_schemas:
            raise ValueError(f"Unknown component type: {component_id}")
        
        schema = self._component_schemas[component_id]
        instance = ComponentInstance(instance_id=instance_id, schema=schema)
        
        # Apply any parameter overrides
        for key, value in kwargs.items():
            if key in instance.state:
                instance.state[key] = value
        
        self.components[instance_id] = instance
        return instance
    
    def remove_component(self, instance_id: str):
        """Remove a component instance."""
        if instance_id in self.components:
            del self.components[instance_id]
    
    def set_physical_input(self, instance_id: str, input_name: str, value: float):
        """Set a physical input value (e.g., actual temperature from Modelica)."""
        signal_name = f"{instance_id}.{input_name}"
        self.signal_bus.set(signal_name, value, SignalType.ANALOG, self.sim_time_ms)
    
    def get_output(self, instance_id: str, output_name: str) -> Optional[Any]:
        """Get an output value from a component."""
        signal_name = f"{instance_id}.{output_name}"
        sv = self.signal_bus.get(signal_name)
        return sv.value if sv else None
    
    def step(self, delta_ms: int):
        """Advance simulation by delta_ms milliseconds."""
        self.sim_time_ms += delta_ms
        
        for instance in self.components.values():
            self._step_component(instance, delta_ms)
    
    def _step_component(self, instance: ComponentInstance, delta_ms: int):
        """Step a single component."""
        schema = instance.schema
        behavior = schema.behavior
        
        # Handle startup delay
        if not instance.started:
            instance.started = True
            instance.startup_complete_ms = self.sim_time_ms + behavior.startup_delay_ms
        
        if self.sim_time_ms < instance.startup_complete_ms:
            return  # Still in startup
        
        # Check if it's time to produce output
        if self.sim_time_ms - instance.last_read_ms < behavior.read_interval_ms:
            return
        
        instance.last_read_ms = self.sim_time_ms
        
        # Process each output
        for output in schema.outputs:
            value = self._compute_output(instance, output.name)
            if value is not None:
                signal_name = f"{instance.instance_id}.{output.name}"
                self.signal_bus.set(signal_name, value, output.signal_type, self.sim_time_ms)
    
    def _compute_output(self, instance: ComponentInstance, output_name: str) -> Optional[Any]:
        """Compute an output value based on inputs and behavior model."""
        schema = instance.schema
        behavior = schema.behavior
        
        # Find corresponding input (convention: input_name maps to output_name)
        # e.g., temp_actual -> temperature, humidity_actual -> humidity
        input_name = f"{output_name}_actual"
        signal_name = f"{instance.instance_id}.{input_name}"
        input_signal = self.signal_bus.get(signal_name)
        
        if input_signal is None:
            # No physical input, generate synthetic value
            value = self._generate_synthetic_value(instance, output_name)
        else:
            value = float(input_signal.value)
        
        # Apply noise model
        value = self._apply_noise(value, behavior)
        
        return value
    
    def _generate_synthetic_value(self, instance: ComponentInstance, output_name: str) -> float:
        """Generate a synthetic value when no physical input exists."""
        # Use stored state or default
        if output_name in instance.state:
            return float(instance.state[output_name])
        
        # Find output definition for range
        for output in instance.schema.outputs:
            if output.name == output_name:
                # Return midpoint of range
                return (output.range_min + output.range_max) / 2
        
        return 0.0
    
    def _apply_noise(self, value: float, behavior) -> float:
        """Apply noise model to a value."""
        if behavior.noise_model == NoiseModel.GAUSSIAN:
            value += random.gauss(0, behavior.noise_stddev)
        elif behavior.noise_model == NoiseModel.UNIFORM:
            value += random.uniform(-behavior.noise_stddev, behavior.noise_stddev)
        elif behavior.noise_model == NoiseModel.DRIFT:
            # Drift accumulates over time
            drift = behavior.drift_rate * (self.sim_time_ms / 3600000)  # per hour
            value += drift
        
        return value
    
    def get_state(self) -> dict:
        """Get full simulation state."""
        return {
            "sim_time_ms": self.sim_time_ms,
            "running": self.running,
            "components": {
                iid: {
                    "schema_id": inst.schema.id,
                    "state": inst.state,
                    "started": inst.started,
                }
                for iid, inst in self.components.items()
            },
            "signals": {
                name: {"value": sv.value, "timestamp_ms": sv.timestamp_ms}
                for name, sv in self.signal_bus.get_all().items()
            },
        }
    
    def inject_fault(self, instance_id: str, fault_type: str, **params):
        """Inject a fault into a component."""
        if instance_id not in self.components:
            raise ValueError(f"Unknown component instance: {instance_id}")
        
        instance = self.components[instance_id]
        
        if fault_type == "disconnect":
            # Component stops producing outputs
            instance.started = False
        elif fault_type == "stuck":
            # Output stuck at current value
            instance.state["_stuck"] = True
        elif fault_type == "offset":
            # Add permanent offset to outputs
            instance.state["_offset"] = params.get("offset", 0.0)
        elif fault_type == "noise_increase":
            # Increase noise level
            instance.schema.behavior.noise_stddev *= params.get("factor", 2.0)
    
    def clear_fault(self, instance_id: str):
        """Clear all faults from a component."""
        if instance_id in self.components:
            instance = self.components[instance_id]
            instance.state.pop("_stuck", None)
            instance.state.pop("_offset", None)
            instance.started = True
