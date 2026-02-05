#!/usr/bin/env python3
"""
DuggerCore Project Initialization CLI
Initialize new projects with full DuggerCore-Universal capabilities.
"""

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

# Add DGT to path
dgt_path = Path(__file__).parent
sys.path.insert(0, str(dgt_path))

from dgt.core.config import DGTConfig
from dgt.core.schema import ProjectType
from dgt.core.template_engine import TemplateEngine

console = Console()
app = typer.Typer(help="Initialize new DuggerCore projects")


@app.command()
def init(
    project_name: str = typer.Argument(..., help="Name of the project to initialize"),
    path: Path | None = typer.Option(None, "--path", "-p", help="Path where to create the project"),
    project_type: str | None = typer.Option(None, "--type", "-t", help="Project type (rust, python, chrome-extension, etc.)"),
    template: str | None = typer.Option(None, "--template", help="Specific template to use"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Interactive mode"),
) -> None:
    """Initialize a new DuggerCore project."""

    console.print(f"[bold blue]🚀 Initializing DuggerCore project: {project_name}[/bold blue]")

    # Determine project path
    if path is None:
        path = Path.cwd() / project_name

    # Interactive mode
    if interactive:
        project_type = _interactive_project_type(project_type)
        template = _interactive_template(template)

    # Validate project type
    if project_type:
        try:
            project_type_enum = ProjectType(project_type.lower())
        except ValueError:
            console.print(f"[red]Invalid project type: {project_type}[/red]")
            console.print(f"Available types: {[pt.value for pt in ProjectType]}")
            raise typer.Exit(1)
    else:
        project_type_enum = None

    # Initialize template engine
    config = DGTConfig.from_project_root(Path.cwd())
    template_engine = TemplateEngine(config)

    # Check if project already exists
    if path.exists() and any(path.iterdir()):
        if not Confirm.ask(f"Directory {path} is not empty. Continue?"):
            console.print("[yellow]Project initialization cancelled[/yellow]")
            raise typer.Exit(0)

    # Initialize project
    success = template_engine.init_project(
        project_name=project_name,
        project_path=path,
        project_type=project_type_enum,
        template_name=template,
    )

    if success:
        console.print(f"[green]✅ Successfully initialized DuggerCore project: {project_name}[/green]")
        console.print(f"[blue]📁 Project location: {path}[/blue]")

        # Show next steps
        _show_next_steps(project_name, path, project_type_enum)
    else:
        console.print(f"[red]❌ Failed to initialize project: {project_name}[/red]")
        raise typer.Exit(1)


@app.command()
def list_templates() -> None:
    """List all available templates."""
    console.print("[bold blue]📋 Available DuggerCore Templates[/bold blue]")

    config = DGTConfig.from_project_root(Path.cwd())
    template_engine = TemplateEngine(config)

    templates = template_engine.list_templates()

    if not templates:
        console.print("[yellow]No templates found[/yellow]")
        return

    table = Table(title="Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Description", style="white")
    table.add_column("Version", style="green")

    for template in templates:
        table.add_row(
            template["name"],
            template["project_type"],
            template["description"],
            template["version"],
        )

    console.print(table)


@app.command()
def create_template(
    name: str = typer.Argument(..., help="Template name"),
    project_type: str = typer.Argument(..., help="Project type"),
    description: str = typer.Option(..., "--description", "-d", help="Template description"),
    source: Path | None = typer.Option(None, "--source", "-s", help="Source directory to create template from"),
) -> None:
    """Create a custom template."""
    console.print(f"[bold blue]📝 Creating custom template: {name}[/bold blue]")

    try:
        project_type_enum = ProjectType(project_type.lower())
    except ValueError:
        console.print(f"[red]Invalid project type: {project_type}[/red]")
        console.print(f"Available types: {[pt.value for pt in ProjectType]}")
        raise typer.Exit(1)

    config = DGTConfig.from_project_root(Path.cwd())
    template_engine = TemplateEngine(config)

    success = template_engine.create_custom_template(
        template_name=name,
        project_type=project_type_enum,
        description=description,
        source_dir=source,
    )

    if success:
        console.print(f"[green]✅ Successfully created template: {name}[/green]")
    else:
        console.print(f"[red]❌ Failed to create template: {name}[/red]")
        raise typer.Exit(1)


def _interactive_project_type(current_type: str | None) -> str | None:
    """Interactive project type selection."""
    if current_type:
        if Confirm.ask(f"Use project type '{current_type}'?"):
            return current_type

    console.print("\n[bold]Select project type:[/bold]")

    project_types = [
        ("rust", "Rust project with Cargo"),
        ("python", "Python project with pyproject.toml"),
        ("chrome-extension", "Chrome Extension with manifest.json"),
        ("nodejs", "Node.js project with package.json"),
        ("solana", "Solana project (Rust + Python)"),
        ("unknown", "Generic project"),
    ]

    for i, (ptype, description) in enumerate(project_types, 1):
        console.print(f"  {i}. {ptype:15} - {description}")

    while True:
        choice = Prompt.ask("Enter choice (1-6)", default="1")

        try:
            index = int(choice) - 1
            if 0 <= index < len(project_types):
                return project_types[index][0]
        except ValueError:
            pass

        console.print("[red]Invalid choice. Please enter 1-6.[/red]")


def _interactive_template(current_template: str | None) -> str | None:
    """Interactive template selection."""
    # List available templates
    config = DGTConfig.from_project_root(Path.cwd())
    template_engine = TemplateEngine(config)
    templates = template_engine.list_templates()

    if not templates:
        return current_template

    if current_template:
        if Confirm.ask(f"Use template '{current_template}'?"):
            return current_template

    console.print("\n[bold]Available templates:[/bold]")

    for i, template in enumerate(templates, 1):
        console.print(f"  {i}. {template['name']:15} - {template['description']}")

    console.print(f"  {len(templates) + 1}. Use default template")

    while True:
        choice = Prompt.ask(f"Enter choice (1-{len(templates) + 1})", default=str(len(templates) + 1))

        try:
            index = int(choice) - 1
            if 0 <= index < len(templates):
                return templates[index]["name"]
            if index == len(templates):
                return None
        except ValueError:
            pass

        console.print(f"[red]Invalid choice. Please enter 1-{len(templates) + 1}.[/red]")


def _show_next_steps(project_name: str, project_path: Path, project_type: ProjectType | None) -> None:
    """Show next steps after project initialization."""
    console.print("\n[bold blue]🎯 Next Steps:[/bold blue]")

    console.print(f"1. [cyan]cd {project_path}[/cyan]")
    console.print("2. Review and customize [yellow]dugger.yaml[/yellow] configuration")

    if project_type == ProjectType.RUST:
        console.print("3. Add your dependencies to [yellow]Cargo.toml[/yellow]")
        console.print("4. Start coding in [yellow]src/[/yellow]")
        console.print("5. Run [cyan]dgt commit[/cyan] when ready to commit")

    elif project_type == ProjectType.PYTHON:
        console.print("3. Set up virtual environment: [cyan]python -m venv venv[/cyan]")
        console.print("4. Install dependencies: [cyan]pip install -e .[/cyan]")
        console.print("5. Start coding in [yellow]src/[/yellow]")
        console.print("6. Run [cyan]dgt commit[/cyan] when ready to commit")

    elif project_type == ProjectType.CHROME_EXTENSION:
        console.print("3. Customize [yellow]manifest.json[/yellow] permissions")
        console.print("4. Edit [yellow]popup/popup.html[/yellow] and [yellow]content/[/yellow] scripts")
        console.print("5. Load extension in Chrome for testing")
        console.print("6. Run [cyan]dgt commit[/cyan] when ready to commit")

    else:
        console.print("3. Add your project files")
        console.print("4. Customize [yellow]dugger.yaml[/yellow] for your needs")
        console.print("5. Run [cyan]dgt commit[/cyan] when ready to commit")

    console.print(f"\n[bold green]🚀 Your DuggerCore project '{project_name}' is ready![/bold green]")
    console.print("[dim]Run 'dgt --help' to see all available commands[/dim]")


if __name__ == "__main__":
    app()
