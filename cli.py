import json
import logging
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

app = typer.Typer(
    name="candidate-transformer",
    help="Multi-source candidate data transformer pipeline",
    add_completion=False,
)
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)


@app.command()
def transform(
    csv: Optional[Path] = typer.Option(None, "--csv", help="Path to recruiter CSV file"),
    ats: Optional[Path] = typer.Option(None, "--ats", help="Path to ATS JSON file"),
    github: Optional[str] = typer.Option(None, "--github", help="GitHub username or URL"),
    notes: Optional[Path] = typer.Option(None, "--notes", help="Path to recruiter notes .txt file"),
    config: Path = typer.Option(
        Path("configs/default_config.json"),
        "--config",
        help="Path to output config JSON",
    ),
    output: Optional[Path] = typer.Option(None, "--output", help="Write JSON to file"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output"),
):
    """
    Transform candidate data from multiple sources into a unified profile.
    """
    sources = []
    if csv:
        sources.append({"type": "csv", "path": str(csv)})
    if ats:
        sources.append({"type": "ats_json", "path": str(ats)})
    if github:
        sources.append({"type": "github", "path": github})
    if notes:
        sources.append({"type": "llm_text", "path": str(notes)})

    if not sources:
        console.print("[bold red]Error:[/] No sources provided. Use --csv, --ats, --github, or --notes.")
        raise typer.Exit(code=1)

    console.print(f"[bold cyan]Candidate Transformer Pipeline v1.0.0[/]")
    console.print(f"Config: [green]{config}[/]")
    console.print(f"Sources: [yellow]{len(sources)}[/]\n")

    # Import here to defer heavy initialization (sentence-transformers)
    from pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(config_path=str(config))
    result = orchestrator.run(sources)

    # Print extraction stats table
    stats = result.get("meta", {}).get("extraction_stats", [])
    if stats:
        table = Table(title="Pipeline Extraction Summary", show_header=True, header_style="bold magenta")
        table.add_column("Source", style="cyan", no_wrap=True)
        table.add_column("Type", style="yellow")
        table.add_column("Records", justify="right", style="green")
        table.add_column("Status", style="bold")
        for stat in stats:
            status_color = "green" if stat["status"] == "OK" else "red"
            table.add_row(
                stat["source"],
                stat["type"],
                str(stat["records"]),
                f"[{status_color}]{stat['status']}[/{status_color}]",
            )
        console.print(table)

    meta = result.get("meta", {})
    console.print(
        f"\n[bold]Results:[/] {meta.get('total_profiles', 0)} profile(s) from "
        f"{meta.get('total_raw_records', 0)} raw records\n"
    )

    # Serialize output
    indent = 2 if pretty else None
    json_output = json.dumps(result, indent=indent, default=str)

    if output:
        output.write_text(json_output, encoding="utf-8")
        console.print(f"[bold green]Output written to:[/] {output}")
    else:
        print(json_output)


@app.command(name="validate-config")
def validate_config(
    config: Path = typer.Option(..., "--config", help="Path to config JSON file"),
):
    """
    Validate a config file and print what output fields it will produce.
    """
    if not config.exists():
        console.print(f"[bold red]Error:[/] Config file not found: {config}")
        raise typer.Exit(code=1)

    try:
        with open(config, encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error:[/] Invalid JSON: {e}")
        raise typer.Exit(code=1)

    fields = cfg.get("fields", [])
    console.print(f"[bold cyan]Config:[/] {config}")
    console.print(f"[bold]Fields ({len(fields)}):[/]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Output Key", style="cyan")
    table.add_column("Source Path", style="yellow")
    table.add_column("Type", style="green")
    table.add_column("Required", style="bold")

    for field in fields:
        required = "✓" if field.get("required") else ""
        table.add_row(
            field.get("path", "?"),
            field.get("from", "?"),
            field.get("type", "string"),
            required,
        )
    console.print(table)

    options_table = Table(title="Output Options", show_header=False)
    options_table.add_column("Option", style="cyan")
    options_table.add_column("Value", style="yellow")
    options_table.add_row("include_confidence", str(cfg.get("include_confidence", True)))
    options_table.add_row("include_provenance", str(cfg.get("include_provenance", True)))
    options_table.add_row("on_missing", cfg.get("on_missing", "null"))
    console.print(options_table)


@app.command(name="show-schema")
def show_schema():
    """
    Print the default canonical output schema as JSON.
    """
    from schemas.canonical import CanonicalProfile
    schema = CanonicalProfile.model_json_schema()
    print(json.dumps(schema, indent=2))


if __name__ == "__main__":
    app()
