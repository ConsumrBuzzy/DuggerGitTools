"""Universal rollback system for multi-provider operations."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .config import DGTConfig
from .git_operations import GitOperations
from .schema import DuggerSchema


class RollbackManager:
    """Universal rollback system for failed operations."""
    
    def __init__(self, config: DGTConfig, schema: DuggerSchema) -> None:
        """Initialize rollback manager."""
        self.config = config
        self.schema = schema
        self.logger = logger.bind(rollback=True)
        self.git_ops = GitOperations(config)
        self.repo_path = config.project_root
        
        # Rollback state directory
        self.rollback_dir = self.repo_path / ".dgt" / "rollback"
        self.rollback_dir.mkdir(parents=True, exist_ok=True)
    
    def create_checkpoint(self, operation_id: str, description: str) -> str:
        """Create a rollback checkpoint before operations."""
        checkpoint_id = self._generate_checkpoint_id(operation_id)
        checkpoint_file = self.rollback_dir / f"{checkpoint_id}.json"
        
        try:
            # Get current state
            current_state = self._capture_current_state()
            
            # Create checkpoint data
            checkpoint_data = {
                "checkpoint_id": checkpoint_id,
                "operation_id": operation_id,
                "description": description,
                "timestamp": self._get_timestamp(),
                "git_state": {
                    "commit_hash": self.git_ops.get_last_commit_hash(),
                    "branch": self.git_ops.get_current_branch(),
                    "status": self.git_ops.get_status(),
                    "staged_files": self.git_ops.get_changed_files(staged=True),
                    "changed_files": self.git_ops.get_changed_files(staged=False),
                },
                "file_snapshots": self._capture_file_snapshots(),
                "version_state": self._capture_version_state(),
                "metadata": {
                    "project_type": self.schema.project_type.value,
                    "enabled_providers": self.schema.multi_provider.enabled_providers if self.schema.multi_provider else [],
                }
            }
            
            # Save checkpoint
            with checkpoint_file.open("w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, indent=2)
            
            self.logger.info(f"Created checkpoint: {checkpoint_id} for {description}")
            return checkpoint_id
            
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")
            raise
    
    def rollback_to_checkpoint(self, checkpoint_id: str) -> bool:
        """Rollback to a specific checkpoint."""
        checkpoint_file = self.rollback_dir / f"{checkpoint_id}.json"
        
        if not checkpoint_file.exists():
            self.logger.error(f"Checkpoint not found: {checkpoint_id}")
            return False
        
        try:
            # Load checkpoint
            with checkpoint_file.open("r", encoding="utf-8") as f:
                checkpoint_data = json.load(f)
            
            self.logger.info(f"Rolling back to checkpoint: {checkpoint_id}")
            
            # Rollback Git state
            git_rollback_success = self._rollback_git_state(checkpoint_data["git_state"])
            
            # Rollback file changes
            file_rollback_success = self._rollback_file_snapshots(checkpoint_data["file_snapshots"])
            
            # Rollback version files
            version_rollback_success = self._rollback_version_state(checkpoint_data["version_state"])
            
            # Overall success
            overall_success = git_rollback_success and file_rollback_success and version_rollback_success
            
            if overall_success:
                self.logger.info(f"Successfully rolled back to checkpoint: {checkpoint_id}")
            else:
                self.logger.warning(f"Partial rollback to checkpoint: {checkpoint_id}")
            
            return overall_success
            
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False
    
    def rollback_last_operation(self) -> bool:
        """Rollback the last operation."""
        latest_checkpoint = self._get_latest_checkpoint()
        
        if not latest_checkpoint:
            self.logger.warning("No checkpoints found for rollback")
            return False
        
        return self.rollback_to_checkpoint(latest_checkpoint)
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all available checkpoints."""
        checkpoints = []
        
        for checkpoint_file in self.rollback_dir.glob("*.json"):
            try:
                with checkpoint_file.open("r", encoding="utf-8") as f:
                    checkpoint_data = json.load(f)
                
                checkpoints.append({
                    "checkpoint_id": checkpoint_data["checkpoint_id"],
                    "operation_id": checkpoint_data["operation_id"],
                    "description": checkpoint_data["description"],
                    "timestamp": checkpoint_data["timestamp"],
                    "commit_hash": checkpoint_data["git_state"]["commit_hash"],
                    "branch": checkpoint_data["git_state"]["branch"],
                })
                
            except Exception as e:
                self.logger.warning(f"Failed to read checkpoint {checkpoint_file}: {e}")
        
        # Sort by timestamp (newest first)
        checkpoints.sort(key=lambda x: x["timestamp"], reverse=True)
        return checkpoints
    
    def cleanup_checkpoints(self, keep_count: int = 10) -> int:
        """Clean up old checkpoints, keeping only the most recent ones."""
        checkpoints = self.list_checkpoints()
        
        if len(checkpoints) <= keep_count:
            return 0
        
        # Remove oldest checkpoints
        checkpoints_to_remove = checkpoints[keep_count:]
        removed_count = 0
        
        for checkpoint in checkpoints_to_remove:
            checkpoint_file = self.rollback_dir / f"{checkpoint['checkpoint_id']}.json"
            
            try:
                checkpoint_file.unlink()
                removed_count += 1
                self.logger.debug(f"Removed checkpoint: {checkpoint['checkpoint_id']}")
            except Exception as e:
                self.logger.warning(f"Failed to remove checkpoint {checkpoint['checkpoint_id']}: {e}")
        
        self.logger.info(f"Cleaned up {removed_count} old checkpoints")
        return removed_count
    
    def _generate_checkpoint_id(self, operation_id: str) -> str:
        """Generate unique checkpoint ID."""
        import hashlib
        import time
        
        timestamp = str(int(time.time()))
        material = f"{operation_id}:{timestamp}"
        return hashlib.md5(material.encode()).hexdigest()[:12]
    
    def _capture_current_state(self) -> Dict[str, Any]:
        """Capture current system state."""
        return {
            "working_directory": str(self.repo_path),
            "timestamp": self._get_timestamp(),
            "dgt_version": "1.0.0",  # Would get from actual version
        }
    
    def _capture_file_snapshots(self) -> Dict[str, str]:
        """Capture snapshots of important files."""
        snapshots = {}
        
        # Capture version files
        for version_format in self.schema.version_formats:
            file_path = self.repo_path / version_format.file_path
            
            if file_path.exists():
                try:
                    snapshots[version_format.file_path] = file_path.read_text(
                        encoding=version_format.encoding
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to snapshot {version_format.file_path}: {e}")
        
        # Capture configuration files
        config_files = ["dugger.yaml", "dugger.yml", ".dgtrc", ".dugger.json"]
        
        for config_file in config_files:
            file_path = self.repo_path / config_file
            
            if file_path.exists():
                try:
                    snapshots[config_file] = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    self.logger.warning(f"Failed to snapshot {config_file}: {e}")
        
        return snapshots
    
    def _capture_version_state(self) -> Dict[str, str]:
        """Capture current version state."""
        versions = {}
        
        for version_format in self.schema.version_formats:
            file_path = self.repo_path / version_format.file_path
            
            if file_path.exists():
                try:
                    import re
                    content = file_path.read_text(encoding=version_format.encoding)
                    match = re.search(version_format.pattern, content, re.MULTILINE)
                    
                    if match:
                        versions[version_format.file_path] = match.group(1)
                except Exception as e:
                    self.logger.warning(f"Failed to capture version from {version_format.file_path}: {e}")
        
        return versions
    
    def _rollback_git_state(self, git_state: Dict[str, Any]) -> bool:
        """Rollback Git state."""
        try:
            current_commit = self.git_ops.get_last_commit_hash()
            target_commit = git_state["commit_hash"]
            
            if current_commit == target_commit:
                self.logger.debug("Git state already matches checkpoint")
                return True
            
            # Reset to target commit
            reset_success = self.git_ops._run_command(
                ["reset", "--hard", target_commit],
                check=True
            )
            
            if not reset_success:
                self.logger.error("Failed to reset Git state")
                return False
            
            # Restore branch if needed
            current_branch = self.git_ops.get_current_branch()
            target_branch = git_state["branch"]
            
            if current_branch != target_branch:
                checkout_success = self.git_ops._run_command(
                    ["checkout", target_branch],
                    check=True
                )
                
                if not checkout_success:
                    self.logger.warning(f"Failed to checkout branch {target_branch}")
            
            self.logger.info("Git state rolled back successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Git rollback failed: {e}")
            return False
    
    def _rollback_file_snapshots(self, file_snapshots: Dict[str, str]) -> bool:
        """Rollback file snapshots."""
        success = True
        
        for file_path, content in file_snapshots.items():
            full_path = self.repo_path / file_path
            
            try:
                # Create parent directories if needed
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write file content
                full_path.write_text(content, encoding="utf-8")
                self.logger.debug(f"Restored file: {file_path}")
                
            except Exception as e:
                self.logger.error(f"Failed to restore file {file_path}: {e}")
                success = False
        
        return success
    
    def _rollback_version_state(self, version_state: Dict[str, str]) -> bool:
        """Rollback version state."""
        success = True
        
        for file_path, target_version in version_state.items():
            version_format = next(
                (vf for vf in self.schema.version_formats if vf.file_path == file_path),
                None
            )
            
            if not version_format:
                self.logger.warning(f"No version format found for {file_path}")
                success = False
                continue
            
            full_path = self.repo_path / file_path
            
            try:
                if not full_path.exists():
                    self.logger.warning(f"Version file not found: {file_path}")
                    success = False
                    continue
                
                content = full_path.read_text(encoding=version_format.encoding)
                
                # Replace version
                if version_format.replacement:
                    new_content = content.replace(
                        version_format.replacement.format(new_version="CURRENT_VERSION"),
                        version_format.replacement.format(new_version=target_version)
                    )
                else:
                    # Use regex replacement
                    import re
                    new_content = re.sub(
                        version_format.pattern,
                        lambda m: m.group(0).replace(m.group(1), target_version),
                        content,
                        flags=re.MULTILINE
                    )
                
                full_path.write_text(new_content, encoding=version_format.encoding)
                self.logger.debug(f"Restored version in {file_path}: {target_version}")
                
            except Exception as e:
                self.logger.error(f"Failed to restore version in {file_path}: {e}")
                success = False
        
        return success
    
    def _get_latest_checkpoint(self) -> Optional[str]:
        """Get the most recent checkpoint ID."""
        checkpoints = self.list_checkpoints()
        return checkpoints[0]["checkpoint_id"] if checkpoints else None
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()


class RollbackContext:
    """Context manager for automatic rollback on failure."""
    
    def __init__(self, config: DGTConfig, schema: DuggerSchema, operation_id: str, description: str):
        """Initialize rollback context."""
        self.config = config
        self.schema = schema
        self.operation_id = operation_id
        self.description = description
        self.rollback_manager = RollbackManager(config, schema)
        self.checkpoint_id = None
        self.should_rollback = True
    
    def __enter__(self) -> "RollbackContext":
        """Enter context and create checkpoint."""
        self.checkpoint_id = self.rollback_manager.create_checkpoint(
            self.operation_id, 
            self.description
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context and rollback if needed."""
        if exc_type is not None and self.should_rollback:
            self.rollback_manager.rollback_to_checkpoint(self.checkpoint_id)
            return False  # Don't suppress exception
        
        return True
    
    def disable_rollback(self) -> None:
        """Disable automatic rollback."""
        self.should_rollback = False
    
    def manual_rollback(self) -> bool:
        """Perform manual rollback."""
        if self.checkpoint_id:
            return self.rollback_manager.rollback_to_checkpoint(self.checkpoint_id)
        return False
