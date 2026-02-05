"""Core orchestration logic for DGT."""

import time
from pathlib import Path
from typing import Any

from git import InvalidGitRepositoryError, Repo
from loguru import logger
from rich.console import Console
from rich.progress import (Progress, SpinnerColumn, TextColumn,
                           TimeElapsedColumn)

from ..providers.base import BaseProvider, ProviderType
from ..providers.chrome import ChromeExtensionProvider
from ..providers.python import PythonProvider
from ..providers.rust import RustProvider
from .auto_fixer import AutoFixer
from .config import DGTConfig
from .git_operations import GitOperations
from .message_generator import MessageGenerator
from .versioning import VersionManager


class DGTOrchestrator:
    """Main orchestrator for DuggerCore Git Tools."""

    def __init__(self, config: DGTConfig | None = None) -> None:
        """Initialize orchestrator with configuration."""
        self.config = config or DGTConfig.from_project_root()
        self.config.logging.configure()

        self.logger = logger.bind(orchestrator=True)
        self.console = Console()

        # Initialize core components
        self.git_ops = GitOperations(self.config)
        self.message_generator = MessageGenerator(self.config)
        self.auto_fixer = AutoFixer(self.config)
        self.version_manager = VersionManager(self.config)

        # Initialize Git repository
        try:
            self.repo = Repo(self.config.project_root)
            self.logger.info(f"Git repository initialized: {self.repo.git_dir}")
        except InvalidGitRepositoryError:
            raise ValueError(f"Not a Git repository: {self.config.project_root}")

        # Register providers
        self.providers = self._register_providers()
        self.active_provider = self._detect_active_provider()

        if self.active_provider:
            self.logger.info(
                f"Active provider: {self.active_provider.provider_type.value}"
            )
        else:
            self.logger.warning("No suitable provider detected for this project")

    def _register_providers(self) -> dict[ProviderType, BaseProvider]:
        """Register all available providers."""
        providers = {}

        # Register built-in providers
        provider_classes = [
            (ProviderType.PYTHON, PythonProvider),
            (ProviderType.RUST, RustProvider),
            (ProviderType.CHROME_EXTENSION, ChromeExtensionProvider),
        ]

        for provider_type, provider_class in provider_classes:
            provider_config = self.config.get_provider_config(provider_type.value)
            if provider_config.enabled:
                provider = provider_class(self.config, provider_config)
                providers[provider_type] = provider
                self.logger.debug(f"Registered provider: {provider}")

        return providers

    def _detect_active_provider(self) -> BaseProvider | None:
        """Detect the appropriate provider for the current project."""
        for provider in self.providers.values():
            if provider.detect_project(self.config.project_root):
                return provider
        return None

    def get_git_status(self) -> dict[str, Any]:
        """Get current Git status using enhanced GitOperations."""
        try:
            # Use enhanced GitOperations for comprehensive status
            is_dirty = self.git_ops.is_dirty()
            has_staged = self.git_ops.has_staged_changes()

            if is_dirty:
                changed_files = self.git_ops.get_changed_files(staged=False)
                staged_files = self.git_ops.get_changed_files(staged=True)
                current_branch = self.git_ops.get_current_branch()

                return {
                    "is_dirty": True,
                    "changed_files": changed_files,
                    "staged_files": staged_files,
                    "current_branch": current_branch,
                    "has_staged_changes": has_staged,
                    "remote_url": self.git_ops.get_remote_url(),
                }
            return {
                "is_dirty": False,
                "current_branch": self.git_ops.get_current_branch(),
                "has_staged_changes": False,
                "remote_url": self.git_ops.get_remote_url(),
            }
        except Exception as e:
            self.logger.error(f"Failed to get Git status: {e}")
            return {"error": str(e)}

    def run_commit_workflow(
        self, message: str, auto_add: bool = True
    ) -> dict[str, Any]:
        """Run the complete commit workflow."""
        workflow_result = {
            "success": False,
            "message": "",
            "pre_flight_results": [],
            "commit_hash": None,
            "post_flight_results": [],
            "execution_time": 0.0,
        }

        start_time = time.time()

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=self.console,
            ) as progress:
                # Step 1: Validate environment
                if not self.active_provider:
                    raise ValueError("No active provider detected")

                task = progress.add_task("Validating environment...", total=None)
                env_validation = self.active_provider.validate_environment()
                if not env_validation.success:
                    raise ValueError(
                        f"Environment validation failed: {env_validation.message}"
                    )
                progress.update(task, description="Environment validated ✓")

                # Step 2: Get Git status and stage files
                task = progress.add_task("Checking Git status...", total=None)
                git_status = self.get_git_status()

                if auto_add and git_status.get("is_dirty", False):
                    # Add all changes using enhanced GitOperations
                    self.git_ops.stage_all()
                    git_status = self.get_git_status()  # Refresh status

                staged_files = [Path(f) for f in git_status.get("staged_files", [])]

                if not staged_files:
                    raise ValueError("No staged changes to commit")

                progress.update(
                    task, description=f"Found {len(staged_files)} staged files ✓"
                )

                # Step 3: Run auto-fixes (enhanced from Brownbook pattern)
                task = progress.add_task("Running auto-fixes...", total=None)
                fixes_applied = self.auto_fixer.run_all_fixes(staged_files)

                if fixes_applied:
                    # Re-stage files after fixes
                    self.git_ops.stage_all()
                    staged_files = [
                        Path(f) for f in self.git_ops.get_changed_files(staged=True)
                    ]
                    progress.update(task, description="Auto-fixes applied ✓")
                else:
                    progress.update(task, description="No fixes needed ✓")

                # Step 4: Run pre-flight checks
                task = progress.add_task("Running pre-flight checks...", total=None)
                pre_flight_results = self.active_provider.run_pre_flight_checks(
                    staged_files
                )

                failed_checks = [r for r in pre_flight_results if not r.success]
                if failed_checks:
                    error_messages = [f.message for f in failed_checks]
                    raise ValueError(
                        f"Pre-flight checks failed: {'; '.join(error_messages)}"
                    )

                workflow_result["pre_flight_results"] = [
                    {
                        "success": r.success,
                        "message": r.message,
                        "execution_time": r.execution_time,
                    }
                    for r in pre_flight_results
                ]
                progress.update(task, description="Pre-flight checks passed ✓")

                # Step 5: Generate enhanced commit message
                task = progress.add_task("Generating commit message...", total=None)
                line_numbers = self.git_ops.get_changed_line_numbers()
                commit_message = self.message_generator.generate_smart_message(
                    [str(f) for f in staged_files],
                    line_numbers,
                    use_llm=self.config.provider_config.get("use_llm", False),
                )

                # Apply provider-specific formatting
                formatted_message = self.active_provider.format_commit_message(
                    commit_message
                )
                progress.update(task, description="Commit message generated ✓")

                # Step 6: Commit changes
                task = progress.add_task("Committing changes...", total=None)
                commit = self.git_ops.commit(formatted_message, no_verify=True)
                if not commit:
                    raise ValueError("Git commit failed")

                commit_hash = self.git_ops.get_last_commit_hash()
                workflow_result["commit_hash"] = commit_hash
                progress.update(task, description=f"Committed {commit_hash[:8]} ✓")

                # Step 7: Version management (if enabled)
                if self.config.provider_config.get("auto_bump_version", False):
                    task = progress.add_task("Bumping version...", total=None)
                    new_version = self.version_manager.bump_version()
                    self.git_ops.stage_all()
                    version_commit = self.git_ops.commit(
                        f"chore: Bump version to {new_version}", no_verify=True
                    )
                    progress.update(
                        task, description=f"Version bumped to {new_version} ✓"
                    )

                # Step 8: Run post-flight checks
                task = progress.add_task("Running post-flight checks...", total=None)
                post_flight_results = self.active_provider.run_post_flight_checks(
                    commit_hash
                )

                failed_post_checks = [r for r in post_flight_results if not r.success]
                if failed_post_checks:
                    warning_messages = [f.message for f in failed_post_checks]
                    self.logger.warning(
                        f"Post-flight warnings: {'; '.join(warning_messages)}"
                    )

                workflow_result["post_flight_results"] = [
                    {
                        "success": r.success,
                        "message": r.message,
                        "execution_time": r.execution_time,
                    }
                    for r in post_flight_results
                ]
                progress.update(task, description="Post-flight checks completed ✓")

                # Step 9: Push to remote if configured
                if self.config.auto_push:
                    task = progress.add_task("Pushing to remote...", total=None)
                    branch = git_status["current_branch"]
                    if self.git_ops.pull(branch):
                        progress.update(task, description="Pulled latest changes ✓")

                    if self.git_ops.push(branch):
                        progress.update(task, description="Pushed to remote ✓")
                    else:
                        progress.update(task, description="Push failed (continuing) ⚠️")

            workflow_result["success"] = True
            workflow_result[
                "message"
            ] = f"Successfully committed and pushed changes: {commit_message}"
            workflow_result["execution_time"] = time.time() - start_time

        except Exception as e:
            workflow_result["success"] = False
            workflow_result["message"] = str(e)
            workflow_result["execution_time"] = time.time() - start_time
            self.logger.error(f"Commit workflow failed: {e}")

        return workflow_result

    def run_dry_run(self, message: str) -> dict[str, Any]:
        """Run a dry-run of the commit workflow with enhanced preview."""
        dry_run_result = {
            "success": False,
            "message": "",
            "would_commit_files": [],
            "pre_flight_results": [],
            "formatted_commit_message": "",
            "version_info": {},
            "execution_time": 0.0,
        }

        start_time = time.time()

        try:
            if not self.active_provider:
                raise ValueError("No active provider detected")

            # Get current Git status
            git_status = self.get_git_status()

            # Simulate adding all changes
            would_commit_files = []
            if git_status.get("changed_files"):
                would_commit_files.extend(git_status["changed_files"])
            if git_status.get("staged_files"):
                would_commit_files.extend(git_status["staged_files"])

            # Generate enhanced commit message
            line_numbers = self.git_ops.get_changed_line_numbers()
            formatted_message = self.message_generator.generate_smart_message(
                would_commit_files,
                line_numbers,
                use_llm=self.config.provider_config.get("use_llm", False),
            )

            # Apply provider-specific formatting
            final_message = self.active_provider.format_commit_message(
                formatted_message
            )

            # Run pre-flight checks on would-be committed files
            staged_files = [Path(f) for f in would_commit_files]
            pre_flight_results = self.active_provider.run_pre_flight_checks(
                staged_files
            )

            # Get version information
            version_info = self.version_manager.get_version_info()

            dry_run_result.update(
                {
                    "success": True,
                    "message": "Dry run completed successfully",
                    "would_commit_files": would_commit_files,
                    "pre_flight_results": [
                        {
                            "success": r.success,
                            "message": r.message,
                            "execution_time": r.execution_time,
                        }
                        for r in pre_flight_results
                    ],
                    "formatted_commit_message": final_message,
                    "version_info": version_info,
                    "execution_time": time.time() - start_time,
                }
            )

        except Exception as e:
            dry_run_result["success"] = False
            dry_run_result["message"] = str(e)
            dry_run_result["execution_time"] = time.time() - start_time

        return dry_run_result

    def get_project_info(self) -> dict[str, Any]:
        """Get comprehensive project information with enhanced details."""
        info = {
            "project_root": str(self.config.project_root),
            "active_provider": self.active_provider.provider_type.value
            if self.active_provider
            else None,
            "git_status": self.get_git_status(),
            "available_providers": list(self.providers.keys()),
            "config": {
                "auto_push": self.config.auto_push,
                "dry_run": self.config.dry_run,
                "commit_message_template": self.config.commit_message_template,
            },
            "version_info": self.version_manager.get_version_info(),
            "capabilities": {
                "has_llm": self.config.provider_config.get("use_llm", False),
                "auto_bump_version": self.config.provider_config.get(
                    "auto_bump_version", False
                ),
                "auto_fixes": True,
                "line_number_tracking": True,
            },
        }

        if self.active_provider:
            info["provider_metadata"] = self.active_provider.get_metadata()

        return info
