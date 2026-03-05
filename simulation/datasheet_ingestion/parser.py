"""Datasheet PDF Parser - Extract component specifications from datasheets.

Parses PDF datasheets to extract:
- Electrical characteristics (voltage, current, power)
- Operating ranges (temperature, humidity)
- Pin configurations
- Timing specifications
- Communication protocols
- Accuracy/resolution specifications

Uses multiple extraction strategies:
1. Table extraction (camelot/tabula)
2. Text pattern matching (regex)
3. AI-assisted extraction (optional, via API)
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path


@dataclass
class ElectricalSpec:
    """Electrical specifications."""
    parameter: str
    min_value: Optional[float] = None
    typical_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: str = ""
    condition: str = ""


@dataclass
class PinSpec:
    """Pin specification."""
    number: int
    name: str
    function: str
    type: str = ""  # input, output, power, etc.


@dataclass
class TimingSpec:
    """Timing specification."""
    parameter: str
    value: float
    unit: str = "ms"
    condition: str = ""


@dataclass
class ExtractedDatasheet:
    """Extracted datasheet information."""
    component_name: str
    manufacturer: str = ""
    part_number: str = ""
    description: str = ""
    
    # Classifications
    component_type: str = ""  # sensor, actuator, mcu, etc.
    category: str = ""  # temperature, humidity, motor, etc.
    
    # Electrical
    supply_voltage_min: Optional[float] = None
    supply_voltage_max: Optional[float] = None
    supply_voltage_typical: Optional[float] = None
    current_consumption: Optional[float] = None
    
    # Operating ranges
    operating_temp_min: Optional[float] = None
    operating_temp_max: Optional[float] = None
    
    # Measurement specs (for sensors)
    measurement_range_min: Optional[float] = None
    measurement_range_max: Optional[float] = None
    accuracy: Optional[float] = None
    resolution: Optional[float] = None
    
    # Communication
    interfaces: list[str] = field(default_factory=list)  # I2C, SPI, UART, etc.
    i2c_address: Optional[int] = None
    
    # Timing
    startup_time_ms: Optional[float] = None
    sampling_rate_ms: Optional[float] = None
    response_time_ms: Optional[float] = None
    
    # Pin configuration
    pins: list[PinSpec] = field(default_factory=list)
    
    # Raw extracted specs
    electrical_specs: list[ElectricalSpec] = field(default_factory=list)
    timing_specs: list[TimingSpec] = field(default_factory=list)
    
    # Metadata
    datasheet_url: str = ""
    extraction_confidence: float = 0.0


class DatasheetParser:
    """Parse PDF datasheets to extract component specifications."""
    
    # Common patterns for parameter extraction
    PATTERNS = {
        "voltage": [
            r"(?:supply|operating|input)\s*voltage[:\s]+(\d+\.?\d*)\s*(?:to|-)\s*(\d+\.?\d*)\s*V",
            r"V(?:CC|DD|IN)[:\s]+(\d+\.?\d*)\s*V",
            r"(\d+\.?\d*)\s*V\s*(?:to|-)\s*(\d+\.?\d*)\s*V",
        ],
        "current": [
            r"(?:supply|operating|input)\s*current[:\s]+(\d+\.?\d*)\s*(?:mA|µA|uA)",
            r"I(?:CC|DD)[:\s]+(\d+\.?\d*)\s*(?:mA|µA|uA)",
        ],
        "temperature_range": [
            r"(?:operating|ambient)\s*temperature[:\s]+(-?\d+\.?\d*)\s*(?:°?C|to|-)\s*(-?\d+\.?\d*)\s*°?C",
            r"(-?\d+)\s*°?C\s*(?:to|-)\s*(\+?\d+)\s*°?C",
        ],
        "accuracy": [
            r"accuracy[:\s]+[±]?(\d+\.?\d*)\s*(%|°C|°|ppm|%RH)",
            r"[±](\d+\.?\d*)\s*(%|°C|ppm|%RH)\s*(?:accuracy|typical)?",
        ],
        "resolution": [
            r"resolution[:\s]+(\d+\.?\d*)\s*(?:bit|bits)",
            r"(\d+)[- ]?bit\s*(?:resolution|ADC|DAC)?",
        ],
        "i2c_address": [
            r"(?:I2C|slave)\s*address[:\s]+0x([0-9A-Fa-f]+)",
            r"address[:\s]+([0-9A-Fa-f]{2})h",
        ],
        "response_time": [
            r"response\s*time[:\s]+(\d+\.?\d*)\s*(ms|s|µs|us)",
            r"(?:conversion|sampling)\s*time[:\s]+(\d+\.?\d*)\s*(ms|s|µs|us)",
        ],
        "measurement_range": [
            r"(?:measurement|sensing)\s*range[:\s]+(-?\d+\.?\d*)\s*(?:to|-)\s*(-?\d+\.?\d*)",
        ],
    }
    
    # Component type detection keywords
    COMPONENT_KEYWORDS = {
        "temperature_sensor": ["temperature", "thermistor", "thermocouple", "temp sensor"],
        "humidity_sensor": ["humidity", "relative humidity", "RH sensor", "hygrometer"],
        "pressure_sensor": ["pressure", "barometer", "barometric", "altimeter"],
        "light_sensor": ["light", "ambient light", "lux", "luminosity", "photodiode"],
        "gas_sensor": ["CO2", "VOC", "gas", "air quality", "O2", "methane"],
        "accelerometer": ["accelerometer", "acceleration", "g-sensor", "motion"],
        "gyroscope": ["gyroscope", "angular rate", "gyro"],
        "magnetometer": ["magnetometer", "magnetic", "compass"],
        "proximity_sensor": ["proximity", "distance", "ultrasonic", "ToF", "LIDAR"],
        "motor_driver": ["motor driver", "H-bridge", "stepper driver", "DC motor"],
        "relay": ["relay", "solid state relay", "SSR"],
        "led_driver": ["LED driver", "PWM controller", "RGB driver"],
    }
    
    def __init__(self):
        self._pdf_text: str = ""
        self._tables: list[list[list[str]]] = []
    
    def parse_pdf(self, pdf_path: str) -> ExtractedDatasheet:
        """Parse a PDF datasheet and extract specifications."""
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        # Extract text from PDF
        self._pdf_text = self._extract_text(pdf_path)
        
        # Extract tables if possible
        self._tables = self._extract_tables(pdf_path)
        
        # Build extracted datasheet
        result = ExtractedDatasheet(
            component_name=self._extract_component_name(),
            datasheet_url=str(path.absolute()),
        )
        
        # Extract manufacturer and part number
        result.manufacturer = self._extract_manufacturer()
        result.part_number = self._extract_part_number()
        
        # Classify component type
        result.component_type, result.category = self._classify_component()
        
        # Extract electrical specs
        self._extract_electrical_specs(result)
        
        # Extract operating ranges
        self._extract_operating_ranges(result)
        
        # Extract measurement specs
        self._extract_measurement_specs(result)
        
        # Extract interfaces
        result.interfaces = self._extract_interfaces()
        result.i2c_address = self._extract_i2c_address()
        
        # Extract timing
        self._extract_timing_specs(result)
        
        # Extract pins
        result.pins = self._extract_pins()
        
        # Calculate confidence
        result.extraction_confidence = self._calculate_confidence(result)
        
        return result
    
    def _extract_text(self, pdf_path: str) -> str:
        """Extract text from PDF using available libraries."""
        try:
            # Try PyMuPDF (fitz) first
            import fitz
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except ImportError:
            pass
        
        try:
            # Fall back to pdfplumber
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
            return text
        except ImportError:
            pass
        
        try:
            # Fall back to PyPDF2
            from PyPDF2 import PdfReader
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        except ImportError:
            pass
        
        raise RuntimeError("No PDF library available. Install: pip install pymupdf pdfplumber PyPDF2")
    
    def _extract_tables(self, pdf_path: str) -> list[list[list[str]]]:
        """Extract tables from PDF."""
        tables = []
        
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
        except ImportError:
            pass
        
        return tables
    
    def _extract_component_name(self) -> str:
        """Extract component name from first page."""
        lines = self._pdf_text.split('\n')[:20]
        
        # Look for part number pattern
        for line in lines:
            # Common patterns: DHT22, BME280, SCD40, etc.
            match = re.search(r'\b([A-Z]{2,4}\d{2,4}[A-Z]?)\b', line)
            if match:
                return match.group(1)
        
        # Return first non-empty line as fallback
        for line in lines:
            if line.strip() and len(line.strip()) < 50:
                return line.strip()
        
        return "Unknown"
    
    def _extract_manufacturer(self) -> str:
        """Extract manufacturer name."""
        manufacturers = [
            "Sensirion", "Bosch", "Texas Instruments", "STMicroelectronics",
            "Analog Devices", "Maxim", "Microchip", "NXP", "Infineon",
            "ROHM", "Vishay", "ON Semiconductor", "Espressif", "Nordic",
        ]
        
        for mfg in manufacturers:
            if mfg.lower() in self._pdf_text.lower():
                return mfg
        
        return ""
    
    def _extract_part_number(self) -> str:
        """Extract part number."""
        # Look for common part number patterns
        patterns = [
            r'\b([A-Z]{2,4}\d{2,4}[A-Z]{0,2})\b',  # DHT22, BME280
            r'\b([A-Z]{3,6}-\d{3,5})\b',  # TMP-123
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, self._pdf_text[:500])
            if matches:
                return matches[0]
        
        return ""
    
    def _classify_component(self) -> tuple[str, str]:
        """Classify component type and category."""
        text_lower = self._pdf_text.lower()
        
        for category, keywords in self.COMPONENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    comp_type = "sensor" if "sensor" in category else "actuator"
                    return comp_type, category
        
        return "unknown", "unknown"
    
    def _extract_electrical_specs(self, result: ExtractedDatasheet):
        """Extract electrical specifications."""
        # Voltage
        for pattern in self.PATTERNS["voltage"]:
            match = re.search(pattern, self._pdf_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    result.supply_voltage_min = float(groups[0])
                    result.supply_voltage_max = float(groups[1])
                elif len(groups) == 1:
                    result.supply_voltage_typical = float(groups[0])
                break
        
        # Current
        for pattern in self.PATTERNS["current"]:
            match = re.search(pattern, self._pdf_text, re.IGNORECASE)
            if match:
                result.current_consumption = float(match.group(1))
                break
    
    def _extract_operating_ranges(self, result: ExtractedDatasheet):
        """Extract operating temperature range."""
        for pattern in self.PATTERNS["temperature_range"]:
            match = re.search(pattern, self._pdf_text, re.IGNORECASE)
            if match:
                result.operating_temp_min = float(match.group(1))
                result.operating_temp_max = float(match.group(2))
                break
    
    def _extract_measurement_specs(self, result: ExtractedDatasheet):
        """Extract measurement specifications (for sensors)."""
        # Accuracy
        for pattern in self.PATTERNS["accuracy"]:
            match = re.search(pattern, self._pdf_text, re.IGNORECASE)
            if match:
                result.accuracy = float(match.group(1))
                break
        
        # Resolution
        for pattern in self.PATTERNS["resolution"]:
            match = re.search(pattern, self._pdf_text, re.IGNORECASE)
            if match:
                result.resolution = float(match.group(1))
                break
        
        # Measurement range
        for pattern in self.PATTERNS["measurement_range"]:
            match = re.search(pattern, self._pdf_text, re.IGNORECASE)
            if match:
                result.measurement_range_min = float(match.group(1))
                result.measurement_range_max = float(match.group(2))
                break
    
    def _extract_interfaces(self) -> list[str]:
        """Extract communication interfaces."""
        interfaces = []
        
        interface_patterns = {
            "I2C": [r'\bI2C\b', r'\bI²C\b', r'\bIIC\b'],
            "SPI": [r'\bSPI\b'],
            "UART": [r'\bUART\b', r'\bserial\b'],
            "1-Wire": [r'\b1-Wire\b', r'\bOneWire\b', r'\bsingle-wire\b'],
            "PWM": [r'\bPWM\b'],
            "Analog": [r'\banalog\s*output\b', r'\bADC\b'],
        }
        
        for interface, patterns in interface_patterns.items():
            for pattern in patterns:
                if re.search(pattern, self._pdf_text, re.IGNORECASE):
                    interfaces.append(interface)
                    break
        
        return interfaces
    
    def _extract_i2c_address(self) -> Optional[int]:
        """Extract I2C address."""
        for pattern in self.PATTERNS["i2c_address"]:
            match = re.search(pattern, self._pdf_text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1), 16)
                except ValueError:
                    pass
        return None
    
    def _extract_timing_specs(self, result: ExtractedDatasheet):
        """Extract timing specifications."""
        for pattern in self.PATTERNS["response_time"]:
            match = re.search(pattern, self._pdf_text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                unit = match.group(2).lower()
                
                # Convert to ms
                if unit == 's':
                    value *= 1000
                elif unit in ['µs', 'us']:
                    value /= 1000
                
                result.response_time_ms = value
                break
    
    def _extract_pins(self) -> list[PinSpec]:
        """Extract pin configuration from tables or text."""
        pins = []
        
        # Look for pin table in extracted tables
        for table in self._tables:
            if not table or not table[0]:
                continue
            
            # Check if this looks like a pin table
            header = ' '.join(str(cell) for cell in table[0]).lower()
            if 'pin' in header or 'name' in header:
                for row in table[1:]:
                    if len(row) >= 2:
                        try:
                            pin_num = int(row[0])
                            pin_name = str(row[1])
                            function = str(row[2]) if len(row) > 2 else ""
                            pins.append(PinSpec(
                                number=pin_num,
                                name=pin_name,
                                function=function,
                            ))
                        except (ValueError, IndexError):
                            pass
        
        return pins
    
    def _calculate_confidence(self, result: ExtractedDatasheet) -> float:
        """Calculate extraction confidence score."""
        score = 0.0
        max_score = 0.0
        
        checks = [
            (result.component_name != "Unknown", 10),
            (result.manufacturer != "", 10),
            (result.component_type != "unknown", 15),
            (result.supply_voltage_min is not None, 10),
            (result.operating_temp_min is not None, 5),
            (result.accuracy is not None, 10),
            (len(result.interfaces) > 0, 15),
            (len(result.pins) > 0, 10),
            (result.response_time_ms is not None, 5),
            (result.description != "", 5),
        ]
        
        for check, weight in checks:
            max_score += weight
            if check:
                score += weight
        
        return score / max_score if max_score > 0 else 0.0
