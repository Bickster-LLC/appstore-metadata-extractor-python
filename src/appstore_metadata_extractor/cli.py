import asyncio
import json
import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .core import CombinedExtractor, ExtractionMode, WBSConfig

console = Console()


@click.group()
def cli():
    """App Store Metadata Extractor CLI"""


@cli.command()
@click.argument("url")
@click.option("--output", "-o", help="Output file path")
@click.option("--format", "-f", type=click.Choice(["json", "pretty"]), default="pretty")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["fast", "complete", "smart"]),
    default="smart",
    help="Extraction mode",
)
@click.option("--wbs/--no-wbs", default=True, help="Enable WBS validation")
def extract(url: str, output: Optional[str], format: str, mode: str, wbs: bool):
    """Extract metadata for a single app"""
    # Create WBS config
    wbs_config = WBSConfig(
        what="Extract app metadata via CLI",
        boundaries={
            "timeout_seconds": 30,
            "required_fields": {
                "app_id",
                "name",
                "current_version",
                "developer_name",
                "icon_url",
            },
        },
    )

    # Create extractor
    extractor = CombinedExtractor(wbs_config)

    with console.status(f"Extracting metadata from {url}..."):
        try:
            # Run extraction
            # Note: Current implementation doesn't support mode parameter directly
            # Mode is handled internally by the extractor based on WBS config
            if wbs:
                result = asyncio.run(extractor.extract_with_validation(url))
            else:
                result = asyncio.run(extractor.extract(url))

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
                        (
                            "Description",
                            (
                                result.metadata.description[:100] + "..."
                                if result.metadata.description
                                and len(result.metadata.description) > 100
                                else result.metadata.description
                            ),
                        ),
                    ]

                    for field_name, value in fields:
                        if value:
                            table.add_row(field_name, str(value))

                    console.print(table)

                    # WBS compliance info
                    if wbs:
                        console.print(
                            f"\n[dim]Extraction took {result.extraction_duration_seconds:.2f}s[/dim]"
                        )
                        if result.wbs_compliant:
                            console.print("[green]✓ WBS Compliant[/green]")
                        else:
                            console.print("[yellow]⚠ WBS Violations:[/yellow]")
                            for violation in result.wbs_violations:
                                console.print(f"  - {violation}")
                else:
                    # Use model_dump_json for proper serialization
                    console.print(result.metadata.model_dump_json(indent=2))

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
                raise click.Exit(1)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)


@cli.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output file path", default="output.json")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["fast", "complete", "smart"]),
    default="smart",
    help="Extraction mode",
)
@click.option("--wbs/--no-wbs", default=True, help="Enable WBS validation")
def extract_batch(json_file: str, output: str, mode: str, wbs: bool):
    """Extract metadata from multiple apps listed in JSON file"""
    # Create WBS config
    wbs_config = WBSConfig(
        what="Extract batch app metadata via CLI",
        boundaries={
            "timeout_seconds": 30,
            "max_concurrent_requests": 5,
            "required_fields": {
                "app_id",
                "name",
                "current_version",
                "developer_name",
                "icon_url",
            },
        },
    )

    # Create extractor
    extractor = CombinedExtractor(wbs_config)
    extraction_mode = ExtractionMode(mode)

    with open(json_file, "r") as f:
        data = json.load(f)

    apps = data.get("apps", [])
    if not apps:
        console.print("[red]No apps found in JSON file[/red]")
        raise click.Exit(1)

    # Extract URLs from the JSON structure
    urls = []
    for app in apps:
        if isinstance(app, dict) and "url" in app:
            urls.append(app["url"])
        elif isinstance(app, str):
            urls.append(app)

    if not urls:
        console.print("[red]No valid URLs found in JSON file[/red]")
        raise click.Exit(1)

    console.print(f"Found {len(urls)} apps to process")

    results = []
    with console.status("Extracting metadata..."):
        # Process apps in batches
        if wbs:
            batch_results = asyncio.run(
                extractor.extract_batch_with_validation(urls, mode=extraction_mode)
            )
        else:
            batch_results = asyncio.run(
                extractor.extract_batch(urls, mode=extraction_mode)
            )

        # Convert dict results to list
        for url in urls:
            if url in batch_results:
                results.append(batch_results[url])

    table = Table(title="Extraction Results")
    table.add_column("App", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Name", style="white")
    if wbs:
        table.add_column("WBS", style="yellow")

    # Calculate summary
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total - successful
    total_duration = sum(r.extraction_duration_seconds for r in results)

    output_data = {
        "summary": {
            "total": total,
            "successful": successful,
            "failed": failed,
            "duration_seconds": total_duration,
            "wbs_compliant": all(r.wbs_compliant for r in results) if wbs else None,
        },
        "apps": [],
    }

    for i, result in enumerate(results):
        app_url = urls[i]
        app_name = (
            apps[i].get("name", app_url) if isinstance(apps[i], dict) else app_url
        )

        if result.success and result.metadata:
            status = "[green]✓ Success[/green]"
            name = result.metadata.name
            wbs_status = (
                "[green]✓[/green]" if result.wbs_compliant else "[yellow]⚠[/yellow]"
            )

            output_data["apps"].append(
                {
                    "url": app_url,
                    "name": app_name,
                    "success": True,
                    "metadata": result.metadata.model_dump(),
                    "wbs_compliant": result.wbs_compliant if wbs else None,
                    "wbs_violations": result.wbs_violations if wbs else None,
                }
            )
        else:
            status = "[red]✗ Failed[/red]"
            name = result.errors[0] if result.errors else "Unknown error"
            wbs_status = "[red]✗[/red]"

            output_data["apps"].append(
                {
                    "url": app_url,
                    "name": app_name,
                    "success": False,
                    "errors": result.errors,
                    "wbs_compliant": False if wbs else None,
                }
            )

        if wbs:
            table.add_row(app_name[:30], status, name[:40], wbs_status)
        else:
            table.add_row(app_name[:30], status, name[:40])

    console.print(table)
    console.print(
        f"\n[bold]Summary:[/bold] {successful}/{total} successful ({total_duration:.2f}s)"
    )

    if wbs:
        wbs_compliant = sum(1 for r in results if r.wbs_compliant)
        console.print(f"[bold]WBS Compliance:[/bold] {wbs_compliant}/{total} compliant")

    with open(output, "w") as f:
        json.dump(output_data, f, indent=2, default=str)
    console.print(f"\n[green]Results saved to {output}[/green]")


@cli.command()
@click.argument("url")
def validate(url: str):
    """Validate extraction against WBS constraints"""
    wbs_config = WBSConfig()
    extractor = CombinedExtractor(wbs_config)

    with console.status("Validating WBS compliance..."):
        try:
            result = asyncio.run(extractor.extract_with_validation(url))

            # Display summary
            console.print("\n[bold]WBS Validation Report[/bold]")
            console.print(f"App ID: {result.app_id}")
            console.print(f"Success: {'✓' if result.success else '✗'}")
            console.print(f"WBS Compliant: {'✓' if result.wbs_compliant else '✗'}")

            if result.wbs_violations:
                console.print("\n[yellow]Violations:[/yellow]")
                for violation in result.wbs_violations:
                    console.print(f"  - {violation}")

            # Performance metrics
            console.print("\n[bold]Performance:[/bold]")
            console.print(f"Extraction Time: {result.extraction_duration_seconds:.2f}s")
            console.print(
                f"Required Fields: {len(result.required_fields_present)}/{len(wbs_config.boundaries.required_fields)}"
            )
            console.print(
                f"Optional Fields: {len(result.optional_fields_present)}/{len(wbs_config.boundaries.optional_fields)}"
            )

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
