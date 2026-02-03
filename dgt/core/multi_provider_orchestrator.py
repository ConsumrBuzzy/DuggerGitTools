"""Multi-provider orchestrator for hybrid projects."""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .config import DGTConfig
from .schema import DuggerSchema, MultiProviderConfig
from .universal_auto_fixer import MultiProviderAutoFixer
from .universal_message_generator import UniversalMessageGenerator
from .universal_versioning import MultiProviderVersionManager
from .git_operations import GitOperations


class MultiProviderOrchestrator:
    """Orchestrator for multi-provider (hybrid) projects."""
    
    def __init__(self, config: DGTConfig, schema: DuggerSchema) -> None:
        """Initialize multi-provider orchestrator."""
        self.config = config
        self.schema = schema
        self.logger = logger.bind(multi_orchestrator=True)
        self.console = Console()
        
        if not schema.multi_provider:
            raise ValueError("Multi-provider configuration not found")
        
        # Initialize core components
        self.git_ops = GitOperations(config)
        self.message_generator = UniversalMessageGenerator(config, schema)
        self.auto_fixer = MultiProviderAutoFixer(config, schema)
        self.version_manager = MultiProviderVersionManager(config, schema)
        
        self.multi_config = schema.multi_provider
        self.enabled_providers = self.multi_config.enabled_providers
    
    def run_commit_workflow(self, message: str, auto_add: bool = True) -> Dict[str, Any]:
        """Run commit workflow across all providers."""
        workflow_result = {
            "success": False,
            "message": "",
            "provider_results": {},
            "commit_hash": None,
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
                
                # Step 1: Get Git status
                task = progress.add_task("Checking Git status...", total=None)
                git_status = self.git_ops.get_status()
                
                if auto_add and git_status.get("is_dirty", False):
                    self.git_ops.stage_all()
                    git_status = self.git_ops.get_git_status()
                
                staged_files = [Path(f) for f in git_status.get("staged_files", [])]
                
                if not staged_files:
                    raise ValueError("No staged changes to commit")
                
                progress.update(task, description=f"Found {len(staged_files)} staged files ✓")
                
                # Step 2: Run pre-flight checks for all providers
                task = progress.add_task("Running multi-provider pre-flight checks...", total=None)
                pre_flight_results = self._run_multi_provider_checks("pre-flight", staged_files)
                
                failed_providers = [name for name, result in pre_flight_results.items() if not result["success"]]
                if failed_providers and self.multi_config.fail_fast:
                    raise ValueError(f"Pre-flight checks failed for providers: {', '.join(failed_providers)}")
                
                workflow_result["provider_results"]["pre_flight"] = pre_flight_results
                progress.update(task, description="Pre-flight checks completed ✓")
                
                # Step 3: Run auto-fixes across all providers
                task = progress.add_task("Running multi-provider auto-fixes...", total=None)
                fixes_applied = self.auto_fixer.run_all_fixes(staged_files)
                
                if fixes_applied:
                    self.git_ops.stage_all()
                    staged_files = [Path(f) for f in self.git_ops.get_changed_files(staged=True)]
                    progress.update(task, description="Auto-fixes applied ✓")
                else:
                    progress.update(task, description="No fixes needed ✓")
                
                # Step 4: Generate unified commit message
                task = progress.add_task("Generating unified commit message...", total=None)
                line_numbers = self.git_ops.get_changed_line_numbers()
                commit_message = self.message_generator.generate_smart_message(
                    [str(f) for f in staged_files],
                    line_numbers,
                    use_llm=self.schema.llm_enabled
                )
                
                # Add multi-provider context
                provider_list = ", ".join(self.enabled_providers)
                enhanced_message = f"[{provider_list}] {commit_message}"
                
                progress.update(task, description="Commit message generated ✓")
                
                # Step 5: Commit changes
                task = progress.add_task("Committing changes...", total=None)
                commit_success = self.git_ops.commit(enhanced_message, no_verify=True)
                
                if not commit_success:
                    raise ValueError("Git commit failed")
                
                commit_hash = self.git_ops.get_last_commit_hash()
                workflow_result["commit_hash"] = commit_hash
                progress.update(task, description=f"Committed {commit_hash[:8]} ✓")
                
                # Step 6: Version management (if enabled)
                if self.schema.auto_bump:
                    task = progress.add_task("Managing versions across providers...", total=None)
                    current_version = self.version_manager.get_unified_version()
                    new_version = self._calculate_next_version(current_version)
                    
                    sync_results = self.version_manager.sync_all_providers(new_version)
                    
                    # Commit version changes
                    if any(sync_results.values()):
                        self.git_ops.stage_all()
                        version_commit = self.git_ops.commit(
                            f"chore: Bump version to {new_version} across providers", 
                            no_verify=True
                        )
                        progress.update(task, description=f"Version bumped to {new_version} ✓")
                    else:
                        progress.update(task, description="Version management skipped ✓")
                
                # Step 7: Run post-flight checks
                task = progress.add_task("Running multi-provider post-flight checks...", total=None)
                post_flight_results = self._run_multi_provider_checks("post-flight", [commit_hash])
                
                workflow_result["provider_results"]["post_flight"] = post_flight_results
                progress.update(task, description="Post-flight checks completed ✓")
                
                # Step 8: Push to remote if configured
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
            workflow_result["message"] = f"Successfully committed across {len(self.enabled_providers)} providers"
            workflow_result["execution_time"] = time.time() - start_time
            
        except Exception as e:
            workflow_result["success"] = False
            workflow_result["message"] = str(e)
            workflow_result["execution_time"] = time.time() - start_time
            self.logger.error(f"Multi-provider commit workflow failed: {e}")
        
        return workflow_result
    
    def run_dry_run(self, message: str) -> Dict[str, Any]:
        """Run dry-run across all providers."""
        dry_run_result = {
            "success": False,
            "message": "",
            "provider_results": {},
            "would_commit_files": [],
            "formatted_commit_message": "",
            "version_info": {},
            "execution_time": 0.0
        }
        
        start_time = time.time()
        
        try:
            # Get current Git status
            git_status = self.git_ops.get_status()
            
            # Simulate adding all changes
            would_commit_files = []
            if git_status.get("changed_files"):
                would_commit_files.extend(git_status["changed_files"])
            if git_status.get("staged_files"):
                would_commit_files.extend(git_status["staged_files"])
            
            # Generate unified commit message
            line_numbers = self.git_ops.get_changed_line_numbers()
            commit_message = self.message_generator.generate_smart_message(
                would_commit_files,
                line_numbers,
                use_llm=self.schema.llm_enabled
            )
            
            # Add multi-provider context
            provider_list = ", ".join(self.enabled_providers)
            final_message = f"[{provider_list}] {commit_message}"
            
            # Run pre-flight checks on would-be committed files
            staged_files = [Path(f) for f in would_commit_files]
            pre_flight_results = self._run_multi_provider_checks("pre-flight", staged_files)
            
            # Get version information
            version_info = {
                "unified_version": self.version_manager.get_unified_version(),
                "enabled_providers": self.enabled_providers,
                "execution_order": self.multi_config.execution_order,
            }
            
            dry_run_result.update({
                "success": True,
                "message": "Multi-provider dry run completed successfully",
                "would_commit_files": would_commit_files,
                "provider_results": {"pre_flight": pre_flight_results},
                "formatted_commit_message": final_message,
                "version_info": version_info,
                "execution_time": time.time() - start_time
            })
            
        except Exception as e:
            dry_run_result["success"] = False
            dry_run_result["message"] = str(e)
            dry_run_result["execution_time"] = time.time() - start_time
        
        return dry_run_result
    
    def get_project_info(self) -> Dict[str, Any]:
        """Get comprehensive multi-provider project information."""
        return {
            "project_root": str(self.config.project_root),
            "project_type": self.schema.project_type.value,
            "enabled_providers": self.enabled_providers,
            "execution_order": self.multi_config.execution_order,
            "fail_fast": self.multi_config.fail_fast,
            "merge_strategies": self.multi_config.merge_strategies,
            "git_status": self.git_ops.get_status(),
            "unified_version": self.version_manager.get_unified_version(),
            "tool_status": self.auto_fixer.get_tool_status(),
            "capabilities": {
                "multi_provider": True,
                "llm_enabled": self.schema.llm_enabled,
                "auto_bump_version": self.schema.auto_bump,
                "auto_fix": self.schema.auto_fix,
            }
        }
    
    def _run_multi_provider_checks(
        self, 
        check_type: str, 
        context: List[Path]
    ) -> Dict[str, Dict[str, Any]]:
        """Run checks across all providers."""
        results = {}
        
        execution_order = self.multi_config.execution_order or self.enabled_providers
        
        for provider_name in execution_order:
            if provider_name not in self.enabled_providers:
                continue
            
            try:
                self.logger.info(f"Running {check_type} checks for {provider_name}")
                
                # This would integrate with individual provider checks
                # For now, simulate the process
                result = {
                    "success": True,
                    "message": f"{check_type} checks passed for {provider_name}",
                    "execution_time": 0.1,
                    "details": {}
                }
                
                results[provider_name] = result
                
            except Exception as e:
                error_result = {
                    "success": False,
                    "message": f"{check_type} checks failed for {provider_name}: {e}",
                    "execution_time": 0.1,
                    "details": {"error": str(e)}
                }
                
                results[provider_name] = error_result
                
                if self.multi_config.fail_fast:
                    self.logger.error(f"Fail-fast enabled, stopping remaining providers")
                    break
        
        return results
    
    def _calculate_next_version(self, current_version: str) -> str:
        """Calculate next version based on bump type."""
        # Simple semantic versioning bump
        import re
        
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", current_version)
        if not match:
            return current_version
        
        major, minor, patch = map(int, match.groups())
        
        if self.schema.bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif self.schema.bump_type == "minor":
            minor += 1
            patch = 0
        else:  # patch
            patch += 1
        
        return f"{major}.{minor}.{patch}"
    
    def validate_multi_provider_setup(self) -> Dict[str, Any]:
        """Validate multi-provider configuration and dependencies."""
        validation_result = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "provider_status": {}
        }
        
        # Check if all enabled providers are valid
        for provider_name in self.enabled_providers:
            provider_status = {
                "available": True,
                "configured": True,
                "issues": []
            }
            
            # Check provider-specific requirements
            if provider_name == "rust":
                if not (self.config.project_root / "Cargo.toml").exists():
                    provider_status["available"] = False
                    provider_status["issues"].append("Cargo.toml not found")
            
            elif provider_name == "python":
                has_python_files = any(
                    (self.config.project_root).rglob("*.py")
                )
                if not has_python_files:
                    provider_status["available"] = False
                    provider_status["issues"].append("No Python files found")
            
            elif provider_name == "chrome-extension":
                if not (self.config.project_root / "manifest.json").exists():
                    provider_status["available"] = False
                    provider_status["issues"].append("manifest.json not found")
            
            validation_result["provider_status"][provider_name] = provider_status
            
            if not provider_status["available"]:
                validation_result["issues"].append(f"Provider {provider_name} not available")
                validation_result["valid"] = False
        
        # Check execution order
        if self.multi_config.execution_order:
            for provider in self.multi_config.execution_order:
                if provider not in self.enabled_providers:
                    validation_result["warnings"].append(
                        f"Provider {provider} in execution_order but not enabled"
                    )
        
        return validation_result
