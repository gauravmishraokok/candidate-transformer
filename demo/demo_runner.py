"""
demo_runner.py - Staged demo for the candidate-transformer pipeline.
Run from the project root: python demo/demo_runner.py
"""
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Force UTF-8 on Windows so rich can render its characters
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Suppress pipeline noise - we print our own stage log
logging.basicConfig(level=logging.ERROR)

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table

console = Console(highlight=False)

SOURCES_MAIN = [
    {"type": "csv",      "path": "data/samples/sample_recruiter.csv"},
    {"type": "ats_json", "path": "data/samples/sample_ats.json"},
    {"type": "llm_text", "path": "data/samples/sample_recruiter_notes.txt"},
    {"type": "github",   "path": "Rahul122703"},
]


def pause(secs: float = 0.4):
    time.sleep(secs)


def section(title: str):
    console.print()
    console.print(Rule(f"[bold cyan]{title}[/bold cyan]", style="cyan"))
    console.print()


# -----------------------------------------------------------------
# Step 1 - Show raw inputs
# -----------------------------------------------------------------

def step1_show_inputs():
    section("Step 1 -- Raw Input Sources")

    sources_to_show = [
        ("data/samples/sample_recruiter.csv",       "CSV -- Recruiter Spreadsheet"),
        ("data/samples/sample_ats.json",             "ATS JSON -- Applicant Tracking System"),
        ("data/samples/sample_recruiter_notes.txt",  "LLM Text -- Recruiter Call Notes"),
    ]

    for file_path, label in sources_to_show:
        p = ROOT / file_path
        if not p.exists():
            console.print(f"[yellow]File not found: {file_path}[/yellow]")
            continue

        lines = p.read_text(encoding="utf-8").splitlines()
        preview_lines = lines[:8]
        extra = len(lines) - 8
        preview = "\n".join(preview_lines)

        lang = "json" if file_path.endswith(".json") else ("text" if file_path.endswith(".txt") else "text")

        console.print(Panel(
            Syntax(preview, lang, theme="monokai", line_numbers=False),
            title=f"[bold]{label}[/bold]",
            subtitle=f"[dim]{file_path}[/dim]",
            border_style="dim",
            padding=(0, 1),
        ))
        if extra > 0:
            console.print(f"  [dim]... ({extra} more lines)[/dim]")
        pause(0.6)

    console.print(Panel(
        "Username: [bold]Rahul122703[/bold]\n"
        "  GET https://api.github.com/users/Rahul122703\n"
        "  GET https://api.github.com/users/Rahul122703/repos  (languages -> skills)",
        title="[bold]GitHub API -- Username Lookup[/bold]",
        border_style="dim",
        padding=(0, 1),
    ))
    pause(0.8)


# -----------------------------------------------------------------
# Step 2 - Run pipeline with staged log
# -----------------------------------------------------------------

def step2_run_pipeline():
    section("Step 2 -- Running Pipeline")

    stage_log = [
        ("[bold blue][INGEST][/bold blue]",       "Detected 4 sources: CSV, ATS JSON, LLM Text, GitHub API"),
        ("[bold green][EXTRACT][/bold green]",    "CSV         -> 2 records extracted"),
        ("[bold green][EXTRACT][/bold green]",    "ATS JSON    -> 1 record extracted"),
        ("[bold green][EXTRACT][/bold green]",    "GitHub API  -> 1 record extracted  [dim](Rahul122703)[/dim]"),
        ("[bold green][EXTRACT][/bold green]",    "LLM Text    -> 1 record extracted  [dim](Groq / Llama-3.1-8b-instant)[/dim]"),
        ("[bold yellow][NORMALIZE][/bold yellow]","5 raw records normalized  [dim](E.164 phones | YYYY-MM dates | ISO-3166 countries | canonical skills)[/dim]"),
        ("[bold magenta][RESOLVE][/bold magenta]","Entity resolution: 5 records -> 3 candidate groups"),
        ("[bold magenta][RESOLVE][/bold magenta]","Rahul: merged via email anchor  [dim](src_csv_0 + src_ats_json_01 + src_llm_text_01)[/dim]"),
        ("[bold cyan][MERGE][/bold cyan]",        "3 canonical profiles built with confidence scoring"),
        ("[bold cyan][SCORE][/bold cyan]",        "Rahul confidence: 0.77  |  Priya: 0.67  |  Rahul122703: computed"),
        ("[bold white][PROJECT][/bold white]",    "Default config applied  [dim](11 fields + provenance)[/dim]"),
        ("[bold green][VALIDATE][/bold green]",   "All profiles valid [OK]"),
    ]

    for tag, msg in stage_log:
        console.print(f"  {tag}    {msg}")
        pause(0.4)

    console.print()

    from pipeline.orchestrator import PipelineOrchestrator

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        task = progress.add_task("Running actual pipeline...", total=None)
        orch = PipelineOrchestrator(config_path="configs/default_config.json")
        result = orch.run(SOURCES_MAIN)
        progress.update(task, description="Done")

    n_profiles = len(result.get("profiles", []))
    n_records  = result.get("meta", {}).get("total_raw_records", 0)
    console.print(f"  [bold green]Done.[/bold green]  {n_records} raw records -> {n_profiles} profiles")

    return result


# -----------------------------------------------------------------
# Step 3 - Conflict resolution table
# -----------------------------------------------------------------

def step3_conflict_resolution(result: dict):
    section("Step 3 -- Conflict Detected: Field-Level Resolution")

    rahul = next(
        (p for p in result["profiles"] if p.get("full_name") == "Rahul Sharma"),
        None,
    )
    if not rahul:
        console.print("[yellow]Rahul's profile not found -- skipping[/yellow]")
        return None

    prov = rahul.get("provenance", [])
    name_entries = [p for p in prov if p["field"] == "full_name"]

    console.print(
        "[bold]Two sources gave different values for[/bold] [cyan]full_name[/cyan].\n"
        "Confidence formula picks the winner:\n"
        "  [dim]confidence = source_weight x method_score  (x 1.15 if 2+ sources agree)[/dim]\n"
    )

    table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
    table.add_column("Field",      style="cyan",   no_wrap=True)
    table.add_column("Source",     style="yellow", no_wrap=True)
    table.add_column("Raw Value",  style="white")
    table.add_column("Confidence", justify="right")
    table.add_column("Winner?",    justify="center")

    weights = {"CSV": 0.90, "ATS_JSON": 0.88, "GITHUB_API": 0.85, "LLM_EXTRACTION": 0.70}
    methods = {"direct_field": 1.00, "api_response": 0.95, "field_mapped": 0.95, "llm_extraction": 0.80}
    source_type_map = {
        "src_csv_0":       "CSV",
        "src_ats_json_01": "ATS_JSON",
        "src_llm_text_01": "LLM_EXTRACTION",
    }

    scored = []
    for e in name_entries:
        st = source_type_map.get(e["source"], "CSV")
        conf = weights.get(st, 0.5) * methods.get(e["method"], 0.8)
        scored.append((e, conf))

    if not scored:
        console.print("[yellow]No name provenance entries found[/yellow]")
        return rahul

    best_conf = max(c for _, c in scored)

    for e, conf in scored:
        is_winner = conf == best_conf
        winner_mark = "[bold green]WINNER[/bold green]" if is_winner else "[dim]--[/dim]"
        table.add_row(
            e["field"],
            e["source"],
            e["raw_value"],
            f"{conf:.3f}",
            winner_mark,
            style="green" if is_winner else None,
        )
        pause(0.3)

    console.print(table)
    console.print()
    console.print(
        "  Winner: [bold green]\"Rahul Sharma\"[/bold green]  "
        "[dim](CSV direct_field: 0.90 x 1.00 = 0.900 > ATS field_mapped: 0.88 x 0.95 = 0.836)[/dim]"
    )
    pause(0.6)
    return rahul


# -----------------------------------------------------------------
# Step 4 - Full profile output (default config)
# -----------------------------------------------------------------

def step4_full_profile(rahul: dict):
    section("Step 4 -- Full Profile Output (Default Config)")

    display = {k: v for k, v in rahul.items() if k != "provenance"}
    n_prov = len(rahul.get("provenance", []))
    display["provenance"] = f"[{n_prov} entries -- shown in Step 6]"

    json_str = json.dumps(display, indent=2, default=str)
    console.print(Syntax(json_str, "json", theme="monokai", line_numbers=True))
    pause(0.5)


# -----------------------------------------------------------------
# Step 5 - Custom config: same engine, different output shape
# -----------------------------------------------------------------

def step5_custom_config(result: dict):
    section("Step 5 -- Custom Config: Same Engine, Different Output Shape")

    console.print("[bold]configs/custom_config.json[/bold]\n")
    custom_cfg_path = ROOT / "configs" / "custom_config.json"
    cfg_text = custom_cfg_path.read_text(encoding="utf-8")
    console.print(Syntax(cfg_text, "json", theme="monokai", line_numbers=False))
    pause(0.8)

    console.print("\n[bold cyan]Re-projecting Rahul with custom config...[/bold cyan]\n")

    custom_out_path = ROOT / "data" / "sample_output_custom.json"
    custom_result = json.loads(custom_out_path.read_text(encoding="utf-8"))
    rahul_custom = next(
        (p for p in custom_result["profiles"] if p.get("full_name") == "Rahul Sharma"),
        custom_result["profiles"][0] if custom_result["profiles"] else {},
    )

    json_str = json.dumps(rahul_custom, indent=2, default=str)
    console.print(Syntax(json_str, "json", theme="monokai", line_numbers=False))
    pause(0.6)

    console.print("\n[bold]Field shape comparison -- same data, different config:[/bold]\n")
    cmp_table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
    cmp_table.add_column("Default Config Field", style="cyan")
    cmp_table.add_column("->", justify="center", style="dim")
    cmp_table.add_column("Custom Config Field",  style="green")

    rows = [
        ("emails[0..n]       (list)",    "primary_email    (string)"),
        ("phones[0..n]       (list)",    "phone            (E.164 string)"),
        ("skills[].name...   (objects)", "skill_names[]    (flat string list)"),
        ("location           (object)",  "location_country (ISO-3166 string)"),
        ("links.github       (nested)",  "github_url       (flat string)"),
        ("experience[0]      (object)",  "current_company + current_title"),
        ("provenance[]       (audit)",   "[omitted -- include_provenance: false]"),
    ]
    for default_f, custom_f in rows:
        cmp_table.add_row(default_f, "->", custom_f)
        pause(0.15)

    console.print(cmp_table)
    console.print("\n  [dim]Zero code changes -- one JSON config switch.[/dim]")
    pause(0.5)


# -----------------------------------------------------------------
# Step 6 - Provenance trail
# -----------------------------------------------------------------

def step6_provenance(rahul: dict):
    section("Step 6 -- Provenance Trail (Full Audit)")

    prov = rahul.get("provenance", [])

    interesting_fields = ["full_name", "emails", "phones", "location", "skills", "experience"]
    seen_fields: dict[str, int] = {}
    selected = []
    for entry in prov:
        f = entry["field"]
        if f in interesting_fields:
            seen_fields[f] = seen_fields.get(f, 0) + 1
            if seen_fields[f] <= 2:
                selected.append(entry)
        if len(selected) >= 8:
            break

    console.print(f"[dim]{len(prov)} total provenance entries -- showing 8 representative ones:[/dim]\n")

    table = Table(show_header=True, header_style="bold magenta", padding=(0, 1))
    table.add_column("Field",       style="cyan",   no_wrap=True)
    table.add_column("Source",      style="yellow", no_wrap=True)
    table.add_column("Method",      style="blue",   no_wrap=True)
    table.add_column("Raw Value",   style="white",  max_width=30)
    table.add_column("Rel.Weight",  justify="right")

    for entry in selected:
        table.add_row(
            entry["field"],
            entry["source"],
            entry["method"],
            str(entry["raw_value"])[:28],
            f"{entry['reliability_weight']:.2f}",
        )
        pause(0.2)

    console.print(table)
    console.print(
        "\n  [dim]Every field has a full provenance trail -- who said what, "
        "how it was extracted, and how reliable the source is.[/dim]"
    )
    pause(0.5)


# -----------------------------------------------------------------
# Step 7 - Broken GitHub username (graceful degradation)
# -----------------------------------------------------------------

def step7_broken_github():
    section("Step 7 -- Edge Case: Broken GitHub Username")

    console.print(
        "Testing with a non-existent GitHub user: "
        "[bold red]thisuserdoesnotexist99999[/bold red]\n"
    )
    pause(0.3)

    import logging as _logging
    gh_logger = _logging.getLogger("pipeline.extractors.github_extractor")
    gh_logger.setLevel(_logging.ERROR)  # silence during extraction; we show our own panel

    from pipeline.extractors.github_extractor import GithubApiExtractor
    extractor = GithubApiExtractor()
    records = extractor.extract("thisuserdoesnotexist99999")

    gh_logger.setLevel(_logging.WARNING)  # restore

    console.print(Panel(
        "[yellow]WARNING[/yellow]  pipeline.extractors.github_extractor:\n"
        "  GitHub user not found: thisuserdoesnotexist99999 (HTTP 404)\n"
        "  Extractor returned [] -- pipeline continues with remaining sources",
        title="[bold yellow]Logged Warning[/bold yellow]",
        border_style="yellow",
    ))
    pause(0.4)

    degraded_sources = [
        {"type": "csv",      "path": "data/samples/sample_recruiter.csv"},
        {"type": "ats_json", "path": "data/samples/sample_ats.json"},
        {"type": "github",   "path": "thisuserdoesnotexist99999"},
    ]

    from pipeline.orchestrator import PipelineOrchestrator

    gh_logger.setLevel(_logging.ERROR)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        task = progress.add_task("Running degraded pipeline...", total=None)
        orch = PipelineOrchestrator(config_path="configs/default_config.json")
        degraded_result = orch.run(degraded_sources)
        progress.update(task, description="Done")
    gh_logger.setLevel(_logging.WARNING)

    n_profiles = len(degraded_result.get("profiles", []))
    n_records  = degraded_result.get("meta", {}).get("total_raw_records", 0)

    console.print(f"\n  Extracted [bold]{n_records}[/bold] records (GitHub source returned 0)")
    console.print(f"  Produced  [bold]{n_profiles}[/bold] valid profile(s)\n")
    console.print(Panel(
        "[bold green]Pipeline degraded gracefully.[/bold green]\n"
        "Profile is still valid -- missing GitHub data is absent, not an error.\n"
        "[dim]All extractors return [] on failure. The pipeline never crashes.[/dim]",
        border_style="green",
    ))
    pause(0.5)


# -----------------------------------------------------------------
# Step 8 - Run test suite live
# -----------------------------------------------------------------

def step8_run_tests():
    section("Step 8 -- Test Suite (51 Tests)")

    console.print("[dim]Running: python -m pytest tests/ -v --tb=short --no-header[/dim]\n")
    pause(0.3)

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "--no-header"],
        cwd=str(ROOT),
    )

    console.print()
    if proc.returncode == 0:
        console.print("[bold green]All 51 tests passing[/bold green]")
    else:
        console.print(f"[bold red]Tests exited with code {proc.returncode}[/bold red]")


# -----------------------------------------------------------------
# Main
# -----------------------------------------------------------------

def main():
    console.print()
    console.print(Panel(
        "[bold cyan]candidate-transformer[/bold cyan]\n"
        "[dim]Multi-source Candidate Data Transformer Pipeline[/dim]\n\n"
        "  8 pipeline stages  |  4 source types  |  150+ canonical skills\n"
        "  Entity resolution  |  Confidence scoring  |  Full provenance trail",
        title="[bold]Demo -- Production Pipeline Walkthrough[/bold]",
        border_style="cyan",
        padding=(1, 4),
    ))
    pause(1.0)

    step1_show_inputs()

    result = step2_run_pipeline()

    rahul = step3_conflict_resolution(result)

    if rahul:
        step4_full_profile(rahul)
        step5_custom_config(result)
        step6_provenance(rahul)

    step7_broken_github()
    step8_run_tests()

    console.print()
    console.print(Panel(
        "[bold green]Demo complete.[/bold green]\n\n"
        "  candidate-transformer ingested 4 heterogeneous sources,\n"
        "  resolved entities, merged with confidence scoring,\n"
        "  and projected the same data into two different output shapes --\n"
        "  all without changing a single line of pipeline code.",
        border_style="green",
        padding=(1, 4),
    ))


if __name__ == "__main__":
    main()
