"""Release Service - SRP-compliant wrapper for ReleaseManager.

Moves release management logic OUT of MultiProviderOrchestrator.
The Orchestrator triggers; the Service executes.
"""

from pathlib import Path
from typing import Optional, List

from loguru import logger

from ..core.release_manager import ReleaseManager, Release


class ReleaseService:
    """Service layer for release management.
    
    Responsibilities:
    - Coordinate ReleaseManager
    - Handle version bumping workflow
    - Manage artifact archiving
    - Provide high-level create_release() interface for orchestrator
    """
    
    def __init__(self, project_root: Path, project_name: Optional[str] = None):
        """Initialize ReleaseService.
        
        Args:
            project_root: Project root directory
            project_name: Project name (defaults to directory name)
        """
        self.project_root = project_root
        self.logger = logger.bind(component="ReleaseService")
        
        # Initialize ReleaseManager
        self.release_manager = ReleaseManager(project_root, project_name)
    
    def create_release(
        self, 
        commit_message: str,
        artifact_paths: Optional[List[Path]] = None,
        auto_version: bool = True
    ) -> Optional[Release]:
        """Create a new release.
        
        This is the primary interface for the orchestrator.
        Calculates version, creates bundles, and records in RELEASES.json.
        
        Args:
            commit_message: Commit message (for version calculation)
            artifact_paths: Paths to artifacts to archive
            auto_version: Auto-calculate version from commit message
            
        Returns:
            Release object if successful, None otherwise
        """
        try:
            # Calculate next version
            if auto_version:
                new_version = self.release_manager.calculate_next_version(
                    commit_message=commit_message
                )
            else:
                new_version = self.release_manager.get_current_version()
            
            # Create release bundle if artifacts provided
            bundle_path = None
            if artifact_paths:
                bundle_path = self.release_manager.create_release_bundle(
                    version=new_version,
                    files_to_include=artifact_paths
                )
            
            # Generate release notes
            release_notes = self.release_manager.generate_release_notes()
            
            # Record release
            artifacts_to_record = [bundle_path] if bundle_path else []
            if artifact_paths:
                artifacts_to_record.extend(artifact_paths)
            
            self.release_manager.record_release(
                version=new_version,
                artifact_paths=artifacts_to_record,
                release_notes=release_notes
            )
            
            # Get recorded release
            release = self.release_manager.get_release_by_version(new_version)
            
            self.logger.info(f"✅ Created release {new_version}")
            return release
            
        except Exception as e:
            self.logger.error(f"Failed to create release: {e}")
            return None
    
    def get_current_version(self) -> str:
        """Get current project version.
        
        Returns:
            Version string
        """
        return self.release_manager.get_current_version()
    
    def get_next_version(self, commit_message: str) -> str:
        """Calculate next version from commit message.
        
        Args:
            commit_message: Commit message
            
        Returns:
            Next version string
        """
        return self.release_manager.calculate_next_version(commit_message)
    
    def get_release_by_sha(self, git_sha: str) -> Optional[Release]:
        """Get release by Git SHA.
        
        Args:
            git_sha: Git commit SHA
            
        Returns:
            Release if found, None otherwise
        """
        return self.release_manager.get_release_by_sha(git_sha)
    
    def get_release_history(self) -> List[Release]:
        """Get all releases.
        
        Returns:
            List of Release objects
        """
        import json
        releases_file = self.project_root / "RELEASES.json"
        
        if not releases_file.exists():
            return []
        
        try:
            with releases_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return [Release(**r) for r in data.get("releases", [])]
        except Exception as e:
            self.logger.warning(f"Failed to read release history: {e}")
            return []
