"""Core orchestration logic for DGT."""

import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from git import Repo, InvalidGitRepositoryError
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .config import DGTConfig, LoggingConfig
from ..providers.base import BaseProvider, CheckResult, ProviderType
from ..providers.python import PythonProvider
from ..providers.rust import RustProvider
from ..providers.chrome import ChromeExtensionProvider


class DGTOrchestrator:
    """Main orchestrator for DuggerCore Git Tools."""
    
    def __init__(self, config: Optional[DGTConfig] = None) -> None:
        """Initialize orchestrator with configuration."""
        self.config = config or DGTConfig.from_project_root()
        self.config.logging.configure()
        
        self.logger = logger.bind(orchestrator=True)
        self.console = Console()
        
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
            self.logger.info(f"Active provider: {self.active_provider.provider_type.value}")
        else:
            self.logger.warning("No suitable provider detected for this project")
    
    def _register_providers(self) -> Dict[ProviderType, BaseProvider]:
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
    
    def _detect_active_provider(self) -> Optional[BaseProvider]:
        """Detect the appropriate provider for the current project."""
        for provider in self.providers.values():
            if provider.detect_project(self.config.project_root):
                return provider
        return None
    
    def get_git_status(self) -> Dict[str, Any]:
        """Get current Git status."""
        try:
            # Check if we're in a Git repository
            if self.repo.is_dirty(untracked_files=True):
                changed_files = [item.a_path for item in self.repo.index.diff(None)]
                untracked_files = self.repo.untracked_files()
                staged_files = [item.a_path for item in self.repo.index.diff("HEAD")]
                
                return {
                    "is_dirty": True,
                    "changed_files": changed_files,
                    "untracked_files": untracked_files,
                    "staged_files": staged_files,
                    "current_branch": self.repo.active_branch.name,
                    "has_staged_changes": len(staged_files) > 0
                }
            else:
                return {
                    "is_dirty": False,
                    "current_branch": self.repo.active_branch.name,
                    "has_staged_changes": False
                }
        except Exception as e:
            self.logger.error(f"Failed to get Git status: {e}")
            return {"error": str(e)}
    
    def run_commit_workflow(self, message: str, auto_add: bool = True) -> Dict[str, Any]:
        """Run the complete commit workflow."""
        workflow_result = {
            "success": False,
            "message": "",
            "pre_flight_results": [],
            "commit_hash": None,
            "post_flight_results": [],
            "execution_time": 0.0
        }
        
        start_time = time.time()
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=self.console
            ) as progress:
                
                # Step 1: Validate environment
                if not self.active_provider:
                    raise ValueError("No active provider detected")
                
                task = progress.add_task("Validating environment...", total=None)
                env_validation = self.active_provider.validate_environment()
                if not env_validation.success:
                    raise ValueError(f"Environment validation failed: {env_validation.message}")
                progress.update(task, description="Environment validated ✓")
                
                # Step 2: Get Git status and staged files
                task = progress.add_task("Checking Git status...", total=None)
                git_status = self.get_git_status()
                
                if auto_add and git_status.get("is_dirty", False):
                    # Add all changes
                    self.repo.git.add("-A")
                    git_status = self.get_git_status()  # Refresh status
                
                staged_files = [Path(f) for f in git_status.get("staged_files", [])]
                
                if not staged_files:
                    raise ValueError("No staged changes to commit")
                
                progress.update(task, description=f"Found {len(staged_files)} staged files ✓")
                
                # Step 3: Run pre-flight checks
                task = progress.add_task("Running pre-flight checks...", total=None)
                pre_flight_results = self.active_provider.run_pre_flight_checks(staged_files)
                
                failed_checks = [r for r in pre_flight_results if not r.success]
                if failed_checks:
                    error_messages = [f.message for f in failed_checks]
                    raise ValueError(f"Pre-flight checks failed: {'; '.join(error_messages)}")
                
                workflow_result["pre_flight_results"] = [
                    {"success": r.success, "message": r.message, "execution_time": r.execution_time}
                    for r in pre_flight_results
                ]
                progress.update(task, description="Pre-flight checks passed ✓")
                
                # Step 4: Commit changes
                task = progress.add_task("Committing changes...", total=None)
                commit_message = self.active_provider.format_commit_message(message)
                commit = self.repo.index.commit(commit_message)
                workflow_result["commit_hash"] = commit.hexsha
                progress.update(task, description=f"Committed {commit.hexsha[:8]} ✓")
                
                # Step 5: Run post-flight checks
                task = progress.add_task("Running post-flight checks...", total=None)
                post_flight_results = self.active_provider.run_post_flight_checks(commit.hexsha)
                
                failed_post_checks = [r for r in post_flight_results if not r.success]
                if failed_post_checks:
                    # Log warnings but don't fail the workflow
                    warning_messages = [f.message for f in failed_post_checks]
                    self.logger.warning(f"Post-flight warnings: {'; '.join(warning_messages)}")
                
                workflow_result["post_flight_results"] = [
                    {"success": r.success, "message": r.message, "execution_time": r.execution_time}
                    for r in post_flight_results
                ]
                progress.update(task, description="Post-flight checks completed ✓")
                
                # Step 6: Push to remote if configured
                if self.config.auto_push:
                    task = progress.add_task("Pushing to remote...", total=None)
                    try:
                        origin = self.repo.remote(name="origin")
                        origin.push()
                        progress.update(task, description="Pushed to remote ✓")
                    except Exception as e:
                        self.logger.warning(f"Failed to push to remote: {e}")
                        progress.update(task, description="Push failed (continuing) ⚠️")
            
            workflow_result["success"] = True
            workflow_result["message"] = f"Successfully committed and pushed changes: {commit_message}"
            workflow_result["execution_time"] = time.time() - start_time
            
        except Exception as e:
            workflow_result["success"] = False
            workflow_result["message"] = str(e)
            workflow_result["execution_time"] = time.time() - start_time
            self.logger.error(f"Commit workflow failed: {e}")
        
        return workflow_result
    
    def run_dry_run(self, message: str) -> Dict[str, Any]:
        """Run a dry-run of the commit workflow without making changes."""
        dry_run_result = {
            "success": False,
            "message": "",
            "would_commit_files": [],
            "pre_flight_results": [],
            "formatted_commit_message": "",
            "execution_time": 0.0
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
            if git_status.get("untracked_files"):
                would_commit_files.extend(git_status["untracked_files"])
            
            # Format commit message
            formatted_message = self.active_provider.format_commit_message(message)
            
            # Run pre-flight checks on would-be committed files
            staged_files = [Path(f) for f in would_commit_files]
            pre_flight_results = self.active_provider.run_pre_flight_checks(staged_files)
            
            dry_run_result.update({
                "success": True,
                "message": "Dry run completed successfully",
                "would_commit_files": would_commit_files,
                "pre_flight_results": [
                    {"success": r.success, "message": r.message, "execution_time": r.execution_time}
                    for r in pre_flight_results
                ],
                "formatted_commit_message": formatted_message,
                "execution_time": time.time() - start_time
            })
            
        except Exception as e:
            dry_run_result["success"] = False
            dry_run_result["message"] = str(e)
            dry_run_result["execution_time"] = time.time() - start_time
        
        return dry_run_result
    
    def get_project_info(self) -> Dict[str, Any]:
        """Get comprehensive project information."""
        info = {
            "project_root": str(self.config.project_root),
            "active_provider": self.active_provider.provider_type.value if self.active_provider else None,
            "git_status": self.get_git_status(),
            "available_providers": list(self.providers.keys()),
            "config": {
                "auto_push": self.config.auto_push,
                "dry_run": self.config.dry_run,
                "commit_message_template": self.config.commit_message_template
            }
        }
        
        if self.active_provider:
            info["provider_metadata"] = self.active_provider.get_metadata()
        
        return info
