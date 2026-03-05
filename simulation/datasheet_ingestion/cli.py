"""CLI for datasheet ingestion."""

import argparse
import json
import sys
from pathlib import Path

from .parser import DatasheetParser
from .generator import ComponentGenerator, generate_component_yaml


def main():
    parser = argparse.ArgumentParser(
        description="Generate component YAML from datasheet PDFs"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Parse command
    parse_cmd = subparsers.add_parser("parse", help="Parse a datasheet PDF")
    parse_cmd.add_argument("pdf", help="Path to PDF datasheet")
    parse_cmd.add_argument("--json", action="store_true", help="Output as JSON")
    
    # Generate command
    gen_cmd = subparsers.add_parser("generate", help="Generate component YAML from PDF")
    gen_cmd.add_argument("pdf", help="Path to PDF datasheet")
    gen_cmd.add_argument("-o", "--output", help="Output YAML file path")
    gen_cmd.add_argument("-c", "--category", help="Component category (sensors, actuators)")
    
    # Batch command
    batch_cmd = subparsers.add_parser("batch", help="Process multiple PDFs")
    batch_cmd.add_argument("directory", help="Directory containing PDF files")
    batch_cmd.add_argument("-o", "--output-dir", default="./components", help="Output directory")
    
    args = parser.parse_args()
    
    if args.command == "parse":
        parser_obj = DatasheetParser()
        try:
            result = parser_obj.parse_pdf(args.pdf)
            
            if args.json:
                # Convert to dict for JSON output
                output = {
                    "component_name": result.component_name,
                    "manufacturer": result.manufacturer,
                    "part_number": result.part_number,
                    "component_type": result.component_type,
                    "category": result.category,
                    "supply_voltage": {
                        "min": result.supply_voltage_min,
                        "max": result.supply_voltage_max,
                        "typical": result.supply_voltage_typical,
                    },
                    "operating_temp": {
                        "min": result.operating_temp_min,
                        "max": result.operating_temp_max,
                    },
                    "measurement": {
                        "range_min": result.measurement_range_min,
                        "range_max": result.measurement_range_max,
                        "accuracy": result.accuracy,
                        "resolution": result.resolution,
                    },
                    "interfaces": result.interfaces,
                    "i2c_address": f"0x{result.i2c_address:02X}" if result.i2c_address else None,
                    "timing": {
                        "response_time_ms": result.response_time_ms,
                        "startup_time_ms": result.startup_time_ms,
                    },
                    "pins": [{"number": p.number, "name": p.name, "function": p.function} 
                             for p in result.pins],
                    "confidence": result.extraction_confidence,
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"Component: {result.component_name}")
                print(f"Manufacturer: {result.manufacturer}")
                print(f"Type: {result.component_type} / {result.category}")
                print(f"Interfaces: {', '.join(result.interfaces)}")
                if result.i2c_address:
                    print(f"I2C Address: 0x{result.i2c_address:02X}")
                print(f"Voltage: {result.supply_voltage_min}-{result.supply_voltage_max}V")
                print(f"Accuracy: {result.accuracy}")
                print(f"Confidence: {result.extraction_confidence:.1%}")
                
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    elif args.command == "generate":
        try:
            generator = ComponentGenerator()
            parser_obj = DatasheetParser()
            
            extracted = parser_obj.parse_pdf(args.pdf)
            
            if args.output:
                yaml_content = generate_component_yaml(extracted, args.output)
                print(f"Generated: {args.output}")
            else:
                yaml_content = generator.generate_from_datasheet(extracted, args.category)
                print(yaml_content)
                
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    elif args.command == "batch":
        directory = Path(args.directory)
        if not directory.is_dir():
            print(f"Error: {args.directory} is not a directory", file=sys.stderr)
            sys.exit(1)
        
        generator = ComponentGenerator(args.output_dir)
        parser_obj = DatasheetParser()
        
        pdf_files = list(directory.glob("*.pdf"))
        print(f"Found {len(pdf_files)} PDF files")
        
        for pdf_path in pdf_files:
            try:
                print(f"Processing: {pdf_path.name}")
                extracted = parser_obj.parse_pdf(str(pdf_path))
                yaml_content = generator.generate_from_datasheet(extracted)
                print(f"  -> Generated (confidence: {extracted.extraction_confidence:.1%})")
            except Exception as e:
                print(f"  -> Error: {e}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
