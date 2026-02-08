"""CLI entry point for aco."""

import os
import sys
import webbrowser
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
app = typer.Typer(
    name="aco",
    help="aco - Agentic Sequencing Quality Control\n\nAutomate sequencing QC with LLM-driven experiment understanding.",
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def get_aco_config_dir() -> Path:
    """Get or create the global aco config directory."""
    config_dir = Path.home() / ".aco"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def load_saved_api_key() -> str | None:
    """Load API key from aco config if saved."""
    config_file = get_aco_config_dir() / "config"
    if config_file.exists():
        try:
            for line in config_file.read_text().splitlines():
                if line.startswith("GOOGLE_API_KEY="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            pass
    return None


def save_api_key_to_config(api_key: str) -> bool:
    """Save API key to aco config directory."""
    try:
        config_file = get_aco_config_dir() / "config"
        config_file.write_text(f"GOOGLE_API_KEY={api_key}\n")
        return True
    except Exception:
        return False


def get_or_prompt_api_key() -> str | None:
    """Get API key from environment, saved config, or prompt user."""
    # Check environment first (support both common env var names)
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        env_var = "GOOGLE_API_KEY" if os.getenv("GOOGLE_API_KEY") else "GEMINI_API_KEY"
        console.print(f"[dim]Using API key from {env_var} environment variable[/dim]")
        os.environ["GOOGLE_API_KEY"] = api_key  # Ensure it's set for google-genai SDK
        return api_key
    
    # Check saved config
    api_key = load_saved_api_key()
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
        console.print("[dim]Using saved API key from ~/.aco/config[/dim]")
        return api_key
    
    console.print()
    console.print(
        Panel(
            "[yellow]Google API key not found[/yellow]\n\n"
            "aco uses Google Gemini for experiment understanding.\n"
            "Get a free API key at: [link=https://aistudio.google.com/apikey]https://aistudio.google.com/apikey[/link]",
            title="[yellow]API Key Required[/yellow]",
            border_style="yellow",
        )
    )
    console.print()
    
    # Prompt for key
    api_key = typer.prompt(
        typer.style("Enter your Google API key", fg=typer.colors.CYAN),
        hide_input=True,
        default="",
        show_default=False,
    )
    
    if not api_key.strip():
        console.print("[dim]Skipping API key setup. LLM features will not work.[/dim]")
        return None
    
    api_key = api_key.strip()
    
    # Set for current process
    os.environ["GOOGLE_API_KEY"] = api_key
    
    # Save to aco config (always works, doesn't need shell permissions)
    console.print()
    if save_api_key_to_config(api_key):
        console.print(f"[green]✓[/green] API key saved to ~/.aco/config")
    else:
        console.print("[yellow]Could not save API key[/yellow]")
    
    console.print()
    return api_key


@app.command()
def init(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to run the server on")] = 7878,
    host: Annotated[str, typer.Option("--host", "-h", help="Host to bind the server to")] = "127.0.0.1",
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Don't automatically open the browser")] = False,
    scan_depth: Annotated[int, typer.Option("--scan-depth", help="Maximum directory depth for file scanning")] = 10,
):
    """Initialize aco in the current directory.
    
    This command will:
    1. Scan the current directory for sequencing files
    2. Start the aco server
    3. Open the UI in your browser
    
    Run this command from the directory containing your sequencing data.
    """
    cwd = Path.cwd()
    
    # Check for Google API key - prompt if not set
    get_or_prompt_api_key()
    
    # Display header
    console.print()
    console.print(
        Panel(
            "[bold]aco[/bold] - Agentic Sequencing Quality Control\n"
            f"[dim]Working directory: {cwd}[/dim]",
            border_style="blue",
        )
    )
    console.print()
    
    # Quick scan preview
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning for sequencing files...", total=None)
        
        from aco.manifest.scanner import scan_directory
        
        try:
            result = scan_directory(cwd, max_depth=scan_depth)
            progress.update(task, completed=True)
        except Exception as e:
            console.print(f"[red]Error scanning directory: {e}[/red]")
            raise typer.Exit(1)
    
    # Display scan results
    console.print()
    console.print("[bold]Discovered Files:[/bold]")
    console.print(f"  • FASTQ files: [green]{result.fastq_count}[/green]")
    console.print(f"  • BAM/SAM/CRAM files: [blue]{result.bam_count}[/blue]")
    console.print(f"  • CellRanger outputs: [yellow]{result.cellranger_count}[/yellow]")
    console.print(f"  • Other files: [dim]{result.other_count}[/dim]")
    console.print(f"  • Total size: [bold]{result.total_size_human}[/bold]")
    console.print()
    
    if result.total_files == 0:
        console.print(
            "[yellow]No sequencing files found in this directory.[/yellow]\n"
            "Make sure you're in the correct directory containing your data."
        )
    
    # Set up storage in current directory
    storage_dir = cwd / ".aco"
    os.environ["ACO_STORAGE_DIR"] = str(storage_dir)
    os.environ["ACO_WORKING_DIR"] = str(cwd)
    
    # Create aco_runs directory if it doesn't exist (in current working directory)
    (cwd / "aco_runs").mkdir(parents=True, exist_ok=True)
    
    # Check if frontend is built
    # Check in package (installed mode)
    frontend_dist = Path(__file__).parent / "static"
    if not (frontend_dist.exists() and (frontend_dist / "index.html").exists()):
        # Check relative to repo (development mode)
        frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    
    if not (frontend_dist.exists() and (frontend_dist / "index.html").exists()):
        console.print(
            Panel(
                "[yellow]Frontend not found[/yellow]\n\n"
                "The web UI is not available. This might mean:\n"
                "• The package was not installed correctly\n"
                "• You're running from source without building\n\n"
                "If running from source, build the frontend:\n"
                "[dim]cd frontend && npm install && npm run build[/dim]\n"
                "[dim]cp -r frontend/dist aco/static[/dim]",
                title="[yellow]Setup Required[/yellow]",
                border_style="yellow",
            )
        )
        
        # Ask if user wants to continue with API only
        continue_anyway = typer.confirm(
            typer.style("Continue with API-only mode (no UI)?", fg=typer.colors.YELLOW),
            default=False,
        )
        if not continue_anyway:
            raise typer.Exit(0)
        console.print()
    
    # Start server info - use localhost for display
    display_host = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    url = f"http://{display_host}:{port}"
    
    # Pass startup details to the API process so it can print the ready message
    os.environ["ACO_CLI_URL"] = url
    
    console.print()
    
    # Open browser
    if not no_browser:
        webbrowser.open(url)
    
    # Start the server
    import uvicorn
    
    # Suppress verbose uvicorn logs
    import logging
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    uvicorn.run(
        "aco.api.main:app",
        host=host,
        port=port,
        log_level="warning",
    )


@app.command()
def scan(
    path: Annotated[str, typer.Argument(help="Directory to scan")] = ".",
    depth: Annotated[int, typer.Option("--depth", "-d", help="Maximum directory depth")] = 10,
):
    """Scan a directory for sequencing files.
    
    This is a quick way to see what files aco can discover
    without starting the full server.
    """
    from aco.manifest.scanner import scan_directory
    
    target = Path(path).resolve()
    
    if not target.exists():
        console.print(f"[red]Error: Path does not exist: {target}[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold]Scanning:[/bold] {target}\n")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning...", total=None)
        result = scan_directory(target, max_depth=depth)
        progress.update(task, completed=True)
    
    console.print("\n[bold]Results:[/bold]")
    console.print(f"  Total files: {result.total_files}")
    console.print(f"  FASTQ files: [green]{result.fastq_count}[/green]")
    console.print(f"  BAM/SAM/CRAM: [blue]{result.bam_count}[/blue]")
    console.print(f"  CellRanger: [yellow]{result.cellranger_count}[/yellow]")
    console.print(f"  Other: {result.other_count}")
    console.print(f"  Total size: [bold]{result.total_size_human}[/bold]")
    
    if result.directories:
        console.print("\n[bold]Special Directories:[/bold]")
        for d in result.directories:
            console.print(f"  • {d.name} ({d.dir_type}) - {d.total_size_human}")
    
    if result.files:
        console.print("\n[bold]Sample Files:[/bold]")
        for f in result.files[:10]:
            console.print(f"  • {f.filename} [{f.file_type}] - {f.size_human}")
        if len(result.files) > 10:
            console.print(f"  [dim]... and {len(result.files) - 10} more[/dim]")
    
    console.print()


@app.command()
def version():
    """Show version information."""
    console.print("aco v0.1.0")
    console.print("Agentic Sequencing Quality Control")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
