#!/usr/bin/env python3
"""Enhanced status command for DGT ecosystem dashboard."""

import subprocess
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

try:
    from duggerlink.dugger_project import DuggerProject
except ImportError:
    # Fallback for development - will be removed after DLT deployment
    from pydantic import BaseModel
    from typing import Optional
    
    class DuggerProject(BaseModel):
        name: str
        path: Path
        git_branch: Optional[str] = None
        is_dirty: Optional[bool] = None
        has_dna: Optional[bool] = None
        todo_count: Optional[int] = None


console = Console()


def scan_ecosystem(github_root: Path = Path("C:/GitHub")) -> list[DuggerProject]:
    """Scan the GitHub ecosystem for Dugger projects."""
    projects = []
    
    for item in github_root.iterdir():
        if not item.is_dir() or item.name.startswith('.'):
            continue
            
        # Skip non-git directories
        if not (item / '.git').exists():
            continue
            
        project = DuggerProject(
            name=item.name,
            path=item
        )
        
        # Get Git status via DLT (fallback to direct git for now)
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "--branch"],
                cwd=item,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # Parse branch info
                for line in lines:
                    if line.startswith('## '):
                        branch_info = line[3:]
                        if '...' in branch_info:
                            branch = branch_info.split('...')[0]
                        else:
                            branch = branch_info
                        project.git_branch = branch
                        break
                
                # Check if dirty
                project.is_dirty = len(lines) > 1 or any(line.startswith('## ') and '...' in line for line in lines)
            else:
                project.git_branch = "unknown"
                project.is_dirty = None
                
        except Exception:
            project.git_branch = "error"
            project.is_dirty = None
        
        # Check for DNA (dugger.yaml)
        project.has_dna = (item / "dugger.yaml").exists()
        
        # Count TODOs (simple grep for now)
        try:
            result = subprocess.run(
                ["grep", "-r", "--include=*.py", "--include=*.md", "TODO", item],
                capture_output=True,
                text=True,
                timeout=30
            )
            project.todo_count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        except Exception:
            project.todo_count = 0
        
        projects.append(project)
    
    return projects


def display_ecosystem_dashboard(projects: list[DuggerProject]) -> None:
    """Display the ecosystem status dashboard."""
    console.print(
        Panel(
            f"[bold cyan]Dugger Ecosystem Dashboard[/bold cyan]\n"
            f"[dim]Scanning {len(projects)} projects in C:\\GitHub[/dim]",
            title="🚀 DGT Status",
            border_style="cyan"
        )
    )
    
    # Create main status table
    table = Table(title="Project Health Overview")
    table.add_column("Project", style="bold blue", no_wrap=True)
    table.add_column("Git Branch", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("DNA", style="cyan")
    table.add_column("TODOs", style="magenta")
    
    # Sort by priority (highlight active projects first)
    priority_projects = ["PhantomArbiter", "DuggerGitTools", "DuggerLinkTools", "DuggerBootTools"]
    other_projects = [p for p in projects if p.name not in priority_projects]
    priority_sorted = [p for p in priority_projects if p in projects]
    
    sorted_projects = priority_sorted + sorted(other_projects, key=lambda p: p.name)
    
    for project in sorted_projects:
        # Git status
        if project.git_branch == "error":
            git_status = "[red]Error[/red]"
        elif project.git_branch == "unknown":
            git_status = "[dim]Unknown[/dim]"
        else:
            git_status = f"[green]{project.git_branch}[/green]"
        
        # Working directory status
        if project.is_dirty is None:
            status = "[dim]?[/dim]"
        elif project.is_dirty:
            status = "[red]Dirty[/red]"
        else:
            status = "[green]Clean[/green]"
        
        # DNA status
        if project.has_dna:
            dna = "[green]✓[/green]"
        else:
            dna = "[dim]✗[/dim]"
        
        # TODO count
        todo_color = "red" if project.todo_count > 10 else "yellow" if project.todo_count > 0 else "green"
        todos = f"[{todo_color}]{project.todo_count}[/{todo_color}]"
        
        # Highlight priority projects
        project_name = f"[bold]{project.name}[/bold]" if project.name in priority_projects else project.name
        
        table.add_row(project_name, git_status, status, dna, todos)
    
    console.print(table)
    
    # Summary statistics
    clean_projects = sum(1 for p in projects if not p.is_dirty)
    dirty_projects = sum(1 for p in projects if p.is_dirty)
    projects_with_dna = sum(1 for p in projects if p.has_dna)
    total_todos = sum(p.todo_count or 0 for p in projects)
    
    console.print("\n📊 [bold]Ecosystem Summary[/bold]:")
    console.print(f"  • Clean repos: [green]{clean_projects}[/green] / [red]{dirty_projects}[/red] dirty")
    console.print(f"  • DNA enabled: [green]{projects_with_dna}[/green] / {len(projects)} projects")
    console.print(f"  • Total TODOs: [yellow]{total_todos}[/yellow] across ecosystem")
    
    # Priority projects status
    priority_status = []
    for project_name in priority_projects:
        project = next((p for p in projects if p.name == project_name), None)
        if project:
            status_icon = "🟢" if not project.is_dirty else "🔴"
            priority_status.append(f"{status_icon} {project_name}")
    
    if priority_status:
        console.print(f"\n⚡ [bold]Priority Projects[/bold]: {'  '.join(priority_status)}")


def main() -> None:
    """Main entry point for enhanced status command."""
    try:
        projects = scan_ecosystem()
        display_ecosystem_dashboard(projects)
    except Exception as e:
        console.print(f"[red]Error scanning ecosystem: {e}[/red]")


if __name__ == "__main__":
    main()