"""Component YAML Generator - Convert extracted datasheet to component model.

Takes ExtractedDatasheet and generates a YAML component model that can be
used in the behavioral simulation runtime.
"""

import yaml
from pathlib import Path
from typing import Optional

from .parser import ExtractedDatasheet


def generate_component_yaml(
    extracted: ExtractedDatasheet,
    output_path: Optional[str] = None,
) -> str:
    """Generate component YAML from extracted datasheet data."""
    
    # Build component structure
    component = {
        "component": {
            "id": _generate_id(extracted),
            "name": extracted.component_name,
            "type": extracted.component_type,
            "description": extracted.description or f"{extracted.component_name} {extracted.category}",
            "manufacturer": extracted.manufacturer,
            "datasheet_url": extracted.datasheet_url,
        }
    }
    
    # Add I2C address if present
    if extracted.i2c_address:
        component["component"]["i2c_address"] = f"0x{extracted.i2c_address:02X}"
    
    # Build inputs based on component type
    inputs = []
    if extracted.component_type == "sensor":
        # Sensors receive physical inputs
        if "temperature" in extracted.category:
            inputs.append({
                "name": "temp_actual",
                "type": "analog",
                "unit": "°C",
                "range_min": extracted.measurement_range_min or -40,
                "range_max": extracted.measurement_range_max or 85,
            })
        if "humidity" in extracted.category:
            inputs.append({
                "name": "humidity_actual",
                "type": "analog",
                "unit": "%",
                "range_min": 0,
                "range_max": 100,
            })
        if "pressure" in extracted.category:
            inputs.append({
                "name": "pressure_actual",
                "type": "analog",
                "unit": "hPa",
                "range_min": 300,
                "range_max": 1100,
            })
        if "light" in extracted.category:
            inputs.append({
                "name": "lux_actual",
                "type": "analog",
                "unit": "lux",
                "range_min": 0,
                "range_max": 65535,
            })
        if "gas" in extracted.category or "co2" in extracted.category.lower():
            inputs.append({
                "name": "co2_actual",
                "type": "analog",
                "unit": "ppm",
                "range_min": 400,
                "range_max": 5000,
            })
    
    if inputs:
        component["component"]["inputs"] = inputs
    
    # Build outputs
    outputs = []
    if extracted.component_type == "sensor":
        # Sensors output measured values
        interface_type = _get_interface_type(extracted)
        
        if "temperature" in extracted.category:
            outputs.append({
                "name": "temperature",
                "type": interface_type,
                "unit": "°C",
                "resolution_bits": int(extracted.resolution) if extracted.resolution else 16,
            })
        if "humidity" in extracted.category:
            outputs.append({
                "name": "humidity",
                "type": interface_type,
                "unit": "%",
                "resolution_bits": int(extracted.resolution) if extracted.resolution else 16,
            })
        if "pressure" in extracted.category:
            outputs.append({
                "name": "pressure",
                "type": interface_type,
                "unit": "hPa",
                "resolution_bits": int(extracted.resolution) if extracted.resolution else 20,
            })
        if "light" in extracted.category:
            outputs.append({
                "name": "lux",
                "type": interface_type,
                "unit": "lux",
                "resolution_bits": 16,
            })
        if "gas" in extracted.category or "co2" in extracted.category.lower():
            outputs.append({
                "name": "co2",
                "type": interface_type,
                "unit": "ppm",
                "resolution_bits": 16,
            })
    elif extracted.component_type == "actuator":
        # Actuators receive control signals and output state
        outputs.append({
            "name": "state",
            "type": "digital",
            "description": "Current actuator state",
        })
    
    if outputs:
        component["component"]["outputs"] = outputs
    
    # Build parameters
    parameters = {}
    
    if extracted.accuracy:
        parameters["accuracy"] = {
            "value": extracted.accuracy,
            "unit": "%" if extracted.accuracy < 10 else "units",
            "description": "Measurement accuracy",
        }
    
    if extracted.supply_voltage_min and extracted.supply_voltage_max:
        parameters["operating_voltage"] = {
            "value": (extracted.supply_voltage_min + extracted.supply_voltage_max) / 2,
            "unit": "V",
            "description": f"Operating voltage ({extracted.supply_voltage_min}-{extracted.supply_voltage_max}V)",
        }
    elif extracted.supply_voltage_typical:
        parameters["operating_voltage"] = {
            "value": extracted.supply_voltage_typical,
            "unit": "V",
        }
    
    if extracted.current_consumption:
        parameters["current_consumption"] = {
            "value": extracted.current_consumption,
            "unit": "mA",
        }
    
    if parameters:
        component["component"]["parameters"] = parameters
    
    # Build behavior
    behavior = {
        "model": "gaussian",
        "noise_stddev": _estimate_noise_stddev(extracted),
        "startup_delay_ms": int(extracted.startup_time_ms or 100),
        "read_interval_ms": int(extracted.sampling_rate_ms or extracted.response_time_ms or 1000),
    }
    
    if extracted.response_time_ms:
        behavior["response_time_ms"] = int(extracted.response_time_ms)
    
    component["component"]["behavior"] = behavior
    
    # Generate YAML
    yaml_content = yaml.dump(component, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    # Write to file if path provided
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(yaml_content)
    
    return yaml_content


def _generate_id(extracted: ExtractedDatasheet) -> str:
    """Generate component ID from extracted data."""
    if extracted.part_number:
        return extracted.part_number.lower().replace("-", "_")
    
    name = extracted.component_name.lower()
    # Remove common suffixes
    for suffix in ["sensor", "module", "breakout"]:
        name = name.replace(suffix, "").strip()
    
    return name.replace(" ", "_").replace("-", "_")


def _get_interface_type(extracted: ExtractedDatasheet) -> str:
    """Determine interface type from extracted interfaces."""
    if "I2C" in extracted.interfaces:
        return "i2c"
    elif "SPI" in extracted.interfaces:
        return "spi"
    elif "1-Wire" in extracted.interfaces:
        return "single_wire"
    elif "UART" in extracted.interfaces:
        return "uart"
    elif "Analog" in extracted.interfaces:
        return "analog"
    return "digital"


def _estimate_noise_stddev(extracted: ExtractedDatasheet) -> float:
    """Estimate noise standard deviation from accuracy."""
    if extracted.accuracy:
        # Assume accuracy is ~2 sigma
        return extracted.accuracy / 2
    return 0.5  # Default


class ComponentGenerator:
    """Generator for component YAML files with AI assistance."""
    
    def __init__(self, output_dir: str = "./components"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_from_datasheet(
        self,
        extracted: ExtractedDatasheet,
        category: Optional[str] = None,
    ) -> str:
        """Generate component YAML from extracted datasheet."""
        # Determine output subdirectory
        if category:
            subdir = category
        elif extracted.component_type == "sensor":
            subdir = "sensors"
        elif extracted.component_type == "actuator":
            subdir = "actuators"
        else:
            subdir = "misc"
        
        # Generate output path
        component_id = _generate_id(extracted)
        output_path = self.output_dir / subdir / f"{component_id}.yaml"
        
        # Generate YAML
        yaml_content = generate_component_yaml(extracted, str(output_path))
        
        return yaml_content
    
    def generate_from_pdf(self, pdf_path: str, category: Optional[str] = None) -> str:
        """Parse PDF and generate component YAML."""
        from .parser import DatasheetParser
        
        parser = DatasheetParser()
        extracted = parser.parse_pdf(pdf_path)
        
        return self.generate_from_datasheet(extracted, category)
    
    def generate_with_ai_assist(
        self,
        pdf_path: str,
        ai_callback: callable,
        category: Optional[str] = None,
    ) -> str:
        """Generate component with AI-assisted parameter extraction.
        
        Args:
            pdf_path: Path to PDF datasheet
            ai_callback: Function that takes extracted text and returns enhanced ExtractedDatasheet
            category: Optional category override
        """
        from .parser import DatasheetParser
        
        parser = DatasheetParser()
        extracted = parser.parse_pdf(pdf_path)
        
        # If confidence is low, use AI to enhance
        if extracted.extraction_confidence < 0.7:
            # Get first few pages of text for AI
            text_sample = parser._pdf_text[:8000]
            
            # Call AI for enhancement
            enhanced = ai_callback(text_sample, extracted)
            if enhanced:
                extracted = enhanced
        
        return self.generate_from_datasheet(extracted, category)
