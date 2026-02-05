#!/usr/bin/env python3
"""
Global Dashboard for DuggerCore-Universal
Health check across all projects in the GitHub directory.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

# Add DGT to path
dgt_path = Path(__file__).parent
sys.path.insert(0, str(dgt_path))

from dgt.core.capability_cache import CapabilityCache
from dgt.core.schema import SchemaLoader
from dgt.core.universal_versioning import UniversalVersionManager


class GlobalDashboard:
    """Global health dashboard for all DuggerCore projects."""

    def __init__(self, github_root: Path) -> None:
        """Initialize global dashboard."""
        self.github_root = github_root
        self.console = Console()
        self.projects = []
        self.health_data = {}

    def scan_all_projects(self) -> None:
        """Scan all projects in GitHub directory."""
        self.console.print("[bold blue]Scanning all projects...[/bold blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task("Discovering projects...", total=None)

            # Discover projects
            project_dirs = [
                d for d in self.github_root.iterdir()
                if d.is_dir() and (d / ".git").exists()
            ]

            for project_dir in project_dirs:
                progress.update(task, description=f"Scanning {project_dir.name}...")

                try:
                    project_info = self._analyze_project(project_dir)
                    if project_info:
                        self.projects.append(project_info)
                except Exception as e:
                    self.console.print(f"[red]Error scanning {project_dir.name}: {e}[/red]")

            progress.update(task, description=f"Found {len(self.projects)} projects ✓")

    def analyze_health(self) -> None:
        """Analyze health of all projects."""
        self.console.print("[bold blue]Analyzing project health...[/bold blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task("Health analysis...", total=None)

            for project in self.projects:
                progress.update(task, description=f"Analyzing {project['name']}...")

                try:
                    health_data = self._analyze_project_health(project)
                    self.health_data[project["name"]] = health_data
                except Exception as e:
                    self.console.print(f"[red]Error analyzing {project['name']}: {e}[/red]")

            progress.update(task, description="Health analysis complete ✓")

    def display_dashboard(self) -> None:
        """Display the global dashboard."""
        # Create layout and split structure first
        layout = Layout()

        # Configure layout structure
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
        )

        layout["main"].split_row(
            Layout(name="summary", size=30),
            Layout(name="projects_section"),
        )

        layout["projects_section"].split_column(
            Layout(name="projects", ratio=3),
            Layout(name="issues", ratio=1),
        )

        # Now assign panels to named sections
        layout["header"].update(Panel(
            f"[bold blue]DuggerCore-Universal Global Dashboard[/bold blue]\n"
            f"[dim]Scanning {len(self.projects)} projects at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
            border_style="blue",
        ))

        layout["summary"].update(self._create_summary_panel())
        layout["projects"].update(self._create_projects_panel())
        layout["issues"].update(self._create_issues_panel())

        self.console.print(layout)

    def export_report(self, output_file: Path | None = None) -> None:
        """Export detailed report to file."""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.github_root / f"dgt_health_report_{timestamp}.json"

        report = {
            "timestamp": datetime.now().isoformat(),
            "total_projects": len(self.projects),
            "summary": self._generate_summary_stats(),
            "projects": self.health_data,
        }

        with output_file.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        self.console.print(f"[green]Report exported to: {output_file}[/green]")

    def _analyze_project(self, project_dir: Path) -> dict[str, Any] | None:
        """Analyze a single project."""
        try:
            # Initialize DGT config for this project
            from dgt.core.config import DGTConfig
            config = DGTConfig.from_project_root(project_dir)

            # Load schema
            schema_loader = SchemaLoader(config)
            schema = schema_loader.load_schema()

            return {
                "name": project_dir.name,
                "path": str(project_dir),
                "project_type": schema.project_type.value,
                "config": config,
                "schema": schema,
            }

        except Exception as e:
            self.console.print(f"[dim]Skipping {project_dir.name}: {e}[/dim]")
            return None

    def _analyze_project_health(self, project: dict[str, Any]) -> dict[str, Any]:
        """Analyze health of a specific project using DLT scoring."""
        health = {
            "project_name": project["name"],
            "project_type": project["project_type"],
            "overall_health": "unknown",
            "health_score": 0,
            "issues": [],
            "warnings": [],
            "info": {},
            "capabilities": {},
            "version_info": {},
            "git_status": {},
        }

        # Use DLT health scoring if available
        try:
            from duggerlink.models.project import DuggerProject
            from duggerlink.git.operations import GitOperations
            
            # Create DuggerProject instance
            project_path = Path(project["path"])
            git_ops = GitOperations(project_path)
            
            # Get Git state
            git_state = None
            if git_ops.is_git_repository():
                git_summary = git_ops.get_git_summary()
                from duggerlink.models.git import GitState
                git_state = GitState(**git_summary)
            
            # Create DuggerProject and calculate health score
            dlt_project = DuggerProject(
                name=project["name"],
                path=project_path,
                git=git_state
            )
            
            health_score = dlt_project.calculate_health_score()
            health["health_score"] = health_score
            
            # Determine overall health based on score
            if health_score >= 80:
                health["overall_health"] = "excellent"
            elif health_score >= 60:
                health["overall_health"] = "good"
            elif health_score >= 40:
                health["overall_health"] = "fair"
            else:
                health["overall_health"] = "poor"
                health["warnings"].append(f"Low health score: {health_score}/100")
            
            # Add DLT-specific info
            health["info"]["dlt_linked"] = (project_path / "dugger.yaml").exists()
            health["info"]["git_clean"] = git_state.is_clean() if git_state else False
            health["info"]["has_docs"] = (project_path / "README.md").exists() or (project_path / "ROADMAP.md").exists()
            
        except ImportError:
            health["issues"].append("DLT not available - using legacy health checks")
            # Fallback to original logic
            self._legacy_health_check(project, health)
        except Exception as e:
            health["issues"].append(f"DLT health check failed: {e}")
            # Fallback to original logic
            self._legacy_health_check(project, health)

        return health
    
    def _legacy_health_check(self, project: dict[str, Any], health: dict[str, Any]) -> None:
        """Fallback health check using original DGT logic."""

        # Git status
        try:
            from dgt.core.git_operations import GitOperations
            git_ops = GitOperations(project["config"])

            git_status = git_ops.get_status()
            health["git_status"] = {
                "is_dirty": git_status.get("is_dirty", False),
                "current_branch": git_status.get("current_branch", "unknown"),
                "has_staged_changes": git_status.get("has_staged_changes", False),
                "remote_url": git_status.get("remote_url"),
            }

            if git_status.get("is_dirty"):
                health["warnings"].append("Working directory is dirty")

        except Exception as e:
            health["issues"].append(f"Git status check failed: {e}")

        # Version management
        try:
            version_manager = UniversalVersionManager(project["config"], project["schema"])
            version_info = version_manager.get_version_info()
            health["version_info"] = version_info

            # Check version consistency
            if len(version_info.get("current_versions", {})) > 1:
                versions = list(version_info["current_versions"].values())
                if len(set(versions)) > 1:
                    health["warnings"].append("Version inconsistency across files")

        except Exception as e:
            health["issues"].append(f"Version check failed: {e}")

        # Capability checking
        try:
            cache = CapabilityCache(project["config"])
            tool_status = {}

            for tool_config in project["schema"].tools:
                cached_result = cache.get_cached_result(tool_config.name, tool_config.check.command)
                if cached_result is not None:
                    tool_status[tool_config.name] = "available" if cached_result else "unavailable"
                else:
                    tool_status[tool_config.name] = "unknown"

            health["capabilities"] = tool_status

            # Count available tools
            available_count = sum(1 for status in tool_status.values() if status == "available")
            total_count = len(tool_status)

            if available_count == 0:
                health["issues"].append("No auto-fix tools available")
            elif available_count < total_count // 2:
                health["warnings"].append("Limited auto-fix tool availability")

        except Exception as e:
            health["issues"].append(f"Capability check failed: {e}")

        # Multi-provider validation
        if project["schema"].multi_provider:
            try:
                from dgt.core.multi_provider_orchestrator import (
                    MultiProviderOrchestrator,
                )
                orchestrator = MultiProviderOrchestrator(project["config"], project["schema"])
                validation = orchestrator.validate_multi_provider_setup()

                if not validation["valid"]:
                    health["issues"].extend(validation["issues"])

                health["warnings"].extend(validation["warnings"])
                health["info"]["multi_provider"] = validation["provider_status"]

            except Exception as e:
                health["issues"].append(f"Multi-provider validation failed: {e}")

        # Determine overall health
        if health["issues"]:
            health["overall_health"] = "critical"
        elif health["warnings"]:
            health["overall_health"] = "warning"
        else:
            health["overall_health"] = "healthy"

        return health

    def _create_summary_panel(self) -> Panel:
        """Create summary panel."""
        summary_stats = self._generate_summary_stats()

        # Create summary table
        table = Table(title="Project Summary", show_header=False)
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="blue")

        table.add_row("Total Projects", str(summary_stats["total_projects"]))
        table.add_row("Healthy", f"[green]{summary_stats['healthy']}[/green]")
        table.add_row("Warnings", f"[yellow]{summary_stats['warning']}[/yellow]")
        table.add_row("Critical", f"[red]{summary_stats['critical']}[/red]")

        # Project type breakdown
        table.add_row("", "")
        table.add_row("Project Types", "")

        for project_name, health in self.health_data.items():
            for issue in health.get("issues", []):
                all_issues.append(f"[red]{project_name}:[/red] {issue}")

            for warning in health.get("warnings", []):
                all_warnings.append(f"[yellow]{project_name}:[/yellow] {warning}")

        # Create tree
        tree = Tree("Issues & Warnings")

        if all_issues:
            issues_branch = tree.add("[red]Critical Issues[/red]")
            for issue in all_issues[:10]:  # Limit to 10
                issues_branch.add(issue)
            if len(all_issues) > 10:
                issues_branch.add(f"... and {len(all_issues) - 10} more")

        if all_warnings:
            warnings_branch = tree.add("[yellow]Warnings[/yellow]")
            for warning in all_warnings[:10]:  # Limit to 10
                warnings_branch.add(warning)
            if len(all_warnings) > 10:
                warnings_branch.add(f"... and {len(all_warnings) - 10} more")

        if not all_issues and not all_warnings:
            tree.add("[green]No issues found! ✓[/green]")

        return Panel(tree, title="Issues Summary", border_style="blue")

    def _generate_summary_stats(self) -> dict[str, Any]:
        """Generate summary statistics."""
        stats = {
            "total_projects": len(self.projects),
            "healthy": 0,
            "warning": 0,
            "critical": 0,
            "project_types": {},
        }

        for health in self.health_data.values():
            # Health counts
            health_status = health["overall_health"]
            if health_status in stats:
                stats[health_status] += 1

            # Project type counts
            project_type = health["project_type"]
            if project_type not in stats["project_types"]:
                stats["project_types"][project_type] = 0
            stats["project_types"][project_type] += 1

        return stats


def main() -> None:
    """Main entry point for global dashboard."""
    import argparse

    parser = argparse.ArgumentParser(description="DuggerCore Global Dashboard")
    parser.add_argument(
        "--github-root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Path to GitHub directory",
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="Export report to file",
    )
    parser.add_argument(
        "--no-scan",
        action="store_true",
        help="Skip scanning (use cached data)",
    )

    args = parser.parse_args()

    console = Console()

    try:
        dashboard = GlobalDashboard(args.github_root)

        if not args.no_scan:
            dashboard.scan_all_projects()
            dashboard.analyze_health()

        dashboard.display_dashboard()

        if args.export:
            dashboard.export_report(args.export)

    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Dashboard error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
