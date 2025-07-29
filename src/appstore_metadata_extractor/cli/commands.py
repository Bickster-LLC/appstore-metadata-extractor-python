"""Enhanced CLI commands for AppStore Metadata Extractor."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from appstore_metadata_extractor.core import CombinedExtractor, WBSConfig, WBSValidator
from appstore_metadata_extractor.core.models import WBSBoundaries

console = Console()


@click.group()
def cli() -> None:
    """AppStore Metadata Extractor CLI - Enhanced with WBS Framework"""


@cli.group()
def extract() -> None:
    """Extraction commands"""


@extract.command()
@click.argument("url")
@click.option("--output", "-o", help="Output file path")
@click.option("--format", "-f", type=click.Choice(["json", "pretty"]), default="pretty")
@click.option(
    "--mode", "-m", type=click.Choice(["fast", "complete", "smart"]), default="smart"
)
def url(url: str, output: Optional[str], format: str, mode: str) -> None:
    """Extract metadata from a single App Store URL."""
    # Create WBS config
    wbs_config = WBSConfig(
        what="Extract app metadata via CLI",
        boundaries=WBSBoundaries(
            timeout_seconds=30,
            required_fields={
                "app_id",
                "name",
                "current_version",
                "developer_name",
                "icon_url",
            },
        ),
    )

    # Create extractor
    extractor = CombinedExtractor(wbs_config)

    with console.status(f"Extracting metadata from {url}..."):
        try:
            result = asyncio.run(extractor.extract_with_validation(url))

            if result.success and result.metadata:
                if format == "pretty":
                    table = Table(title=f"App Metadata: {result.metadata.name}")
                    table.add_column("Field", style="cyan")
                    table.add_column("Value", style="white")

                    # Display key fields
                    fields = [
                        ("App ID", result.metadata.app_id),
                        ("Name", result.metadata.name),
                        ("Developer", result.metadata.developer_name),
                        ("Version", result.metadata.current_version),
                        ("Price", result.metadata.formatted_price),
                        (
                            "Rating",
                            (
                                f"{result.metadata.average_rating:.2f}"
                                if result.metadata.average_rating
                                else "N/A"
                            ),
                        ),
                        ("Category", result.metadata.category),
                    ]

                    for field_name, value in fields:
                        table.add_row(field_name, str(value))

                    console.print(table)

                    # WBS compliance info
                    if result.wbs_compliant:
                        console.print("\n[green]✓ WBS Compliant[/green]")
                    else:
                        console.print("\n[yellow]⚠ WBS Violations:[/yellow]")
                        for violation in result.wbs_violations:
                            console.print(f"  - {violation}")
                else:
                    console.print_json(result.metadata.model_dump_json())

                if output:
                    with open(output, "w") as f:
                        json.dump(
                            result.metadata.model_dump(), f, indent=2, default=str
                        )
                    console.print(f"\n[green]Saved to {output}[/green]")
            else:
                console.print(
                    f"[red]Extraction failed: {', '.join(result.errors)}[/red]"
                )

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.group()
def lint() -> None:
    """Code quality and linting commands"""


@lint.command()
@click.option("--fix", is_flag=True, help="Fix issues automatically where possible")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def check(fix: bool, verbose: bool) -> None:
    """Run WBS-compliant lint checking."""
    project_root = Path(__file__).parent.parent.parent.parent
    lint_script = project_root / "scripts" / "lint.py"

    if not lint_script.exists():
        console.print("[red]Lint script not found. Run from project root.[/red]")
        sys.exit(1)

    cmd = [sys.executable, str(lint_script)]
    if fix:
        cmd.append("--fix")
    if verbose:
        cmd.append("--verbose")

    console.print("[bold]Running WBS-compliant lint check...[/bold]")

    try:
        result = subprocess.run(cmd, cwd=project_root)
        sys.exit(result.returncode)
    except Exception as e:
        console.print(f"[red]Error running lint: {e}[/red]")
        sys.exit(1)


@lint.command()
def report() -> None:
    """Generate and display lint report."""
    project_root = Path(__file__).parent.parent.parent.parent
    report_path = project_root / "lint_report.json"

    if not report_path.exists():
        console.print(
            "[yellow]No lint report found. Run 'lint check --verbose' first.[/yellow]"
        )
        return

    with open(report_path) as f:
        report = json.load(f)

    # Display summary table
    table = Table(title="Lint Report Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    summary = report.get("summary", {})
    table.add_row("Total Duration", f"{summary.get('total_duration', 0):.2f}s")
    table.add_row("Total Errors", str(summary.get("total_errors", 0)))
    table.add_row("Tools Passed", str(summary.get("tools_passed", 0)))
    table.add_row("Tools Failed", str(summary.get("tools_failed", 0)))

    console.print(table)

    # Display individual tool results
    if report.get("results"):
        console.print("\n[bold]Tool Results:[/bold]")
        for result in report["results"]:
            status = "[green]PASS[/green]" if result["success"] else "[red]FAIL[/red]"
            console.print(f"  {result['tool']:10} {status} ({result['duration']:.2f}s)")
            if result["error_count"] > 0:
                console.print(f"    Errors: {result['error_count']}")


@cli.group()
def wbs() -> None:
    """WBS framework commands"""


@wbs.command()
@click.argument("url")
def validate(url: str) -> None:
    """Validate extraction against WBS constraints."""
    wbs_config = WBSConfig(what="Validate extraction WBS compliance")
    extractor = CombinedExtractor(wbs_config)
    validator = WBSValidator(wbs_config)

    with console.status("Validating WBS compliance..."):
        try:
            result = asyncio.run(extractor.extract_with_validation(url))
            report = validator.get_wbs_report(result)

            # Display report
            console.print_json(data=report)

            if result.wbs_compliant:
                console.print("\n[green]✓ Fully WBS Compliant[/green]")
            else:
                console.print("\n[red]✗ WBS Violations Detected[/red]")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@wbs.command()
def explain() -> None:
    """Explain WBS framework and current configuration."""
    console.print("[bold]WBS Framework (What-Boundaries-Success)[/bold]\n")

    console.print("The WBS framework ensures reliable software through:")
    console.print("  • [cyan]WHAT[/cyan]: Clear definition of intent")
    console.print("  • [cyan]BOUNDARIES[/cyan]: Explicit constraints")
    console.print("  • [cyan]SUCCESS[/cyan]: Measurable criteria\n")

    console.print("[bold]Current Configuration:[/bold]")

    # Show default WBS config
    config = WBSConfig(what="Default WBS configuration")

    table = Table(title="WBS Boundaries")
    table.add_column("Boundary", style="cyan")
    table.add_column("Value", style="white")

    boundaries = config.boundaries.model_dump()
    for key, value in boundaries.items():
        if isinstance(value, set):
            value = ", ".join(value)
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)


@cli.command()
def version() -> None:
    """Show version information."""
    from appstore_metadata_extractor import __version__

    console.print(f"AppStore Metadata Extractor v{__version__}")
    console.print("WBS Framework Enhanced")


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
