#!/usr/bin/env python3
"""DuggerCore-Universal CLI - Language-Agnostic DevOps Orchestration."""

import sys
from pathlib import Path

# Add DGT to path
dgt_path = Path(__file__).parent
sys.path.insert(0, str(dgt_path))

from typing import Optional

import typer
from rich.console import Console

from dgt.core.config import DGTConfig
from dgt.core.orchestrator import DGTOrchestrator
from dgt.core.multi_provider_orchestrator import MultiProviderOrchestrator
from dgt.core.schema import SchemaLoader

# Import init CLI
from .cli_init import app as init_app

console = Console()
app = typer.Typer(
    name="dgt",
    help="DuggerCore-Universal CLI - Language-Agnostic DevOps Orchestration",
    no_args_is_help=True,
    rich_markup_mode="rich"
)

# Add init as a subcommand
app.add_typer(init_app, name="init", help="Initialize new DuggerCore projects")

@app.command()
def commit(
    message: str = typer.Option(..., "-m", "--message", help="Commit message"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run in dry-run mode"),
    no_add: bool = typer.Option(False, "--no-add", help="Don't automatically add changes"),
    no_push: bool = typer.Option(False, "--no-push", help="Don't automatically push to remote"),
    project_root: Optional[Path] = typer.Option(None, "--root", help="Project root directory")
) -> None:
    """Run the complete commit workflow."""
    try:
        # Load configuration
        config = DGTConfig.from_project_root(project_root)
        config.dry_run = dry_run
        config.auto_push = not no_push
        
        # Initialize orchestrator
        orchestrator = DGTOrchestrator(config)
        
        if dry_run:
            result = orchestrator.run_dry_run(message)
            _display_dry_run_result(result)
        else:
            result = orchestrator.run_commit_workflow(message, auto_add=not no_add)
            _display_commit_result(result)
        
        # Exit with appropriate code
        sys.exit(0 if result["success"] else 1)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@app.command()
def status(
    project_root: Optional[Path] = typer.Option(None, "--root", help="Project root directory")
) -> None:
    """Display project and Git status."""
    try:
        config = DGTConfig.from_project_root(project_root)
        orchestrator = DGTOrchestrator(config)
        
        _display_status(orchestrator.get_project_info())
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@app.command()
def info(
    project_root: Optional[Path] = typer.Option(None, "--root", help="Project root directory")
) -> None:
    """Display detailed project information."""
    try:
        config = DGTConfig.from_project_root(project_root)
        orchestrator = DGTOrchestrator(config)
        
        _display_project_info(orchestrator.get_project_info())
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@app.command()
def init(
    project_root: Path = typer.Argument(..., help="Project root directory to initialize"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing configuration")
) -> None:
    """Initialize DGT configuration for a project."""
    try:
        config_file = project_root / "dgt.toml"
        
        if config_file.exists() and not force:
            console.print(f"[yellow]Configuration file already exists: {config_file}[/yellow]")
            console.print("Use --force to overwrite")
            sys.exit(1)
        
        # Create default configuration
        default_config = """[logging]
level = "INFO"

[providers.python]
enabled = true

[providers.rust]
enabled = true

[providers.chrome_extension]
enabled = true
"""
        
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with config_file.open("w") as f:
            f.write(default_config)
        
        console.print(f"[green]Configuration initialized: {config_file}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def _display_commit_result(result: dict) -> None:
    """Display commit workflow result."""
    if result["success"]:
        console.print(Panel(
            f"[green]✓ {result['message']}[/green]",
            title="Commit Successful",
            border_style="green"
        ))
        
        if result["pre_flight_results"]:
            table = Table(title="Pre-flight Checks")
            table.add_column("Check", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Time", style="blue")
            
            for check_result in result["pre_flight_results"]:
                status = "✓" if check_result["success"] else "✗"
                time_str = f"{check_result['execution_time']:.2f}s" if check_result["execution_time"] else "N/A"
                table.add_row(check_result["message"], status, time_str)
            
            console.print(table)
        
        if result["commit_hash"]:
            console.print(f"[dim]Commit hash: {result['commit_hash']}[/dim]")
        
        console.print(f"[dim]Total execution time: {result['execution_time']:.2f}s[/dim]")
        
    else:
        console.print(Panel(
            f"[red]✗ {result['message']}[/red]",
            title="Commit Failed",
            border_style="red"
        ))
        
        if result["pre_flight_results"]:
            failed_checks = [r for r in result["pre_flight_results"] if not r["success"]]
            if failed_checks:
                console.print("\n[red]Failed checks:[/red]")
                for check in failed_checks:
                    console.print(f"  • {check['message']}")


def _display_dry_run_result(result: dict) -> None:
    """Display dry-run result."""
    console.print(Panel(
        "[yellow]Dry run mode - no changes made[/yellow]",
        title="Dry Run Results",
        border_style="yellow"
    ))
    
    if result["success"]:
        console.print(f"\n[green]Would commit with message:[/green] {result['formatted_commit_message']}")
        
        if result["would_commit_files"]:
            console.print("\n[blue]Files that would be committed:[/blue]")
            for file_path in result["would_commit_files"]:
                console.print(f"  • {file_path}")
        
        if result["pre_flight_results"]:
            console.print("\n[cyan]Pre-flight check results:[/cyan]")
            for check_result in result["pre_flight_results"]:
                status = "✓" if check_result["success"] else "✗"
                color = "green" if check_result["success"] else "red"
                console.print(f"  {status} [{color}]{check_result['message']}[/{color}]")
        
        console.print(f"\n[dim]Execution time: {result['execution_time']:.2f}s[/dim]")
        
    else:
        console.print(f"[red]Dry run failed: {result['message']}[/red]")


def _display_status(info: dict) -> None:
    """Display Git status."""
    git_status = info["git_status"]
    
    if git_status.get("error"):
        console.print(f"[red]Error getting Git status: {git_status['error']}[/red]")
        return
    
    # Create status tree
    tree = Tree("📁 Git Status")
    
    # Branch info
    branch = tree.add(f"🌿 Branch: {git_status.get('current_branch', 'unknown')}")
    
    # Clean/dirty status
    if git_status.get("is_dirty", False):
        dirty = branch.add("🔴 Working directory dirty")
        
        # Staged files
        staged = git_status.get("staged_files", [])
        if staged:
            staged_node = dirty.add(f"📋 Staged files ({len(staged)})")
            for file_path in staged:
                staged_node.add(f"  {file_path}")
        
        # Changed files
        changed = git_status.get("changed_files", [])
        if changed:
            changed_node = dirty.add(f"📝 Changed files ({len(changed)})")
            for file_path in changed:
                changed_node.add(f"  {file_path}")
        
        # Untracked files
        untracked = git_status.get("untracked_files", [])
        if untracked:
            untracked_node = dirty.add(f"❓ Untracked files ({len(untracked)})")
            for file_path in untracked:
                untracked_node.add(f"  {file_path}")
    else:
        branch.add("🟢 Working directory clean")
    
    console.print(tree)


def _display_project_info(info: dict) -> None:
    """Display detailed project information."""
    # Project overview
    console.print(Panel(
        f"📁 {info['project_root']}",
        title="Project Overview",
        border_style="blue"
    ))
    
    # Provider information
    console.print("\n🔧 Provider Information:")
    console.print(f"  Active: {info['active_provider'] or 'None'}")
    console.print(f"  Available: {', '.join(p.value for p in info['available_providers'])}")
    
    if info.get("provider_metadata"):
        console.print("\n📊 Provider Metadata:")
        for key, value in info["provider_metadata"].items():
            console.print(f"  {key}: {value}")
    
    # Configuration
    config = info["config"]
    console.print("\n⚙️  Configuration:")
    console.print(f"  Auto-push: {config['auto_push']}")
    console.print(f"  Dry-run: {config['dry_run']}")
    console.print(f"  Commit template: {config['commit_message_template']}")
    
    # Git status
    console.print("\n📋 Git Status:")
    _display_status(info)


if __name__ == "__main__":
    app()
