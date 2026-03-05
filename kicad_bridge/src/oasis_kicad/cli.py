"""CLI for oasis-kicad tool."""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from .importer import KiCadImporter
from .exporter import KiCadExporter
from .junction_advisor import JunctionAdvisor

console = Console()


@click.group()
@click.version_option()
def main():
    """Oasis KiCAD Bridge - Two-way PCB/firmware integration."""
    pass


@main.command()
@click.argument("kicad_project", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default="device.yaml",
              help="Output device.yaml path")
@click.option("--include-footprints/--no-footprints", default=True,
              help="Include footprint information")
def import_pcb(kicad_project: str, output: str, include_footprints: bool):
    """Import existing KiCAD project to device.yaml.
    
    Parses schematic and PCB files to extract:
    - Component list (ICs, sensors, actuators)
    - Pin assignments
    - Connector definitions
    - Power topology
    """
    console.print(f"[bold blue]Importing KiCAD project:[/] {kicad_project}")
    
    importer = KiCadImporter(Path(kicad_project))
    
    try:
        device_config = importer.import_project(include_footprints=include_footprints)
        importer.write_device_yaml(device_config, Path(output))
        
        console.print(f"[bold green]✓[/] Generated {output}")
        console.print(f"  Sensors: {len(device_config.get('sensors', []))}")
        console.print(f"  Actuators: {len(device_config.get('actuators', []))}")
        console.print(f"  Connectors: {len(device_config.get('hardware', {}).get('connectors', []))}")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise click.Abort()


@main.command()
@click.option("--config", "-c", type=click.Path(exists=True), required=True,
              help="Input device.yaml path")
@click.option("--output", "-o", type=click.Path(), required=True,
              help="Output KiCAD project directory")
@click.option("--template", "-t", type=click.Choice(["minimal", "full", "modular"]),
              default="modular", help="Project template style")
def scaffold(config: str, output: str, template: str):
    """Generate KiCAD project scaffold from device.yaml.
    
    Creates:
    - Project file (.kicad_pro)
    - Hierarchical schematic sheets
    - Symbol library with component mappings
    - Recommended connectors and junction components
    """
    console.print(f"[bold blue]Generating KiCAD scaffold from:[/] {config}")
    
    exporter = KiCadExporter(Path(config))
    
    try:
        output_path = Path(output)
        exporter.generate_project(output_path, template=template)
        
        console.print(f"[bold green]✓[/] Generated KiCAD project at {output}")
        console.print("\n[bold]Created files:[/]")
        for f in output_path.glob("**/*"):
            if f.is_file():
                console.print(f"  {f.relative_to(output_path)}")
                
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise click.Abort()


@main.command()
@click.option("--config", "-c", type=click.Path(exists=True), required=True,
              help="device.yaml path")
@click.option("--kicad", "-k", type=click.Path(exists=True),
              help="Optional: existing KiCAD project to cross-reference")
def review(config: str, kicad: str | None):
    """Review design and get junction/interconnect recommendations.
    
    Analyzes device.yaml (and optionally KiCAD project) to suggest:
    - Connector types for each interface
    - Cable specifications
    - Enclosure mounting
    - EMI considerations
    - Power distribution
    """
    console.print(f"[bold blue]Design Review for:[/] {config}")
    
    advisor = JunctionAdvisor(Path(config))
    if kicad:
        advisor.load_kicad_project(Path(kicad))
    
    recommendations = advisor.analyze()
    
    # Display recommendations
    console.print("\n[bold]== Connector Recommendations ==[/]")
    _print_connector_table(recommendations.get("connectors", []))
    
    console.print("\n[bold]== Cable Specifications ==[/]")
    _print_cable_table(recommendations.get("cables", []))
    
    console.print("\n[bold]== Enclosure Considerations ==[/]")
    for item in recommendations.get("enclosure", []):
        console.print(f"  • {item}")
    
    console.print("\n[bold]== Power Distribution ==[/]")
    for item in recommendations.get("power", []):
        console.print(f"  • {item}")
    
    console.print("\n[bold]== Design Warnings ==[/]")
    for warning in recommendations.get("warnings", []):
        console.print(f"  [yellow]⚠[/] {warning}")


def _print_connector_table(connectors: list):
    table = Table(show_header=True, header_style="bold")
    table.add_column("Interface")
    table.add_column("Recommended")
    table.add_column("Signals")
    table.add_column("Notes")
    
    for conn in connectors:
        table.add_row(
            conn["interface"],
            conn["connector_type"],
            str(conn["signal_count"]),
            conn.get("notes", "")
        )
    
    console.print(table)


def _print_cable_table(cables: list):
    table = Table(show_header=True, header_style="bold")
    table.add_column("Connection")
    table.add_column("Cable Type")
    table.add_column("Max Length")
    table.add_column("Shielding")
    
    for cable in cables:
        table.add_row(
            cable["connection"],
            cable["cable_type"],
            cable["max_length"],
            cable.get("shielding", "None")
        )
    
    console.print(table)


if __name__ == "__main__":
    main()
