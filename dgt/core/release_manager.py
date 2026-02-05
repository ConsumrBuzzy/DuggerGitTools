"""Release Manager - Universal version tracking and artifact archiving.

Extracted from CBHuddle/scripts/build-release.ps1 pattern.
Implements Git SHA → Version → Artifact linking for RELEASES.json tracking.
"""

import json
import re
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from loguru import logger
from pydantic import BaseModel


class ReleaseArtifact(BaseModel):
    """Information about a release artifact."""
    
    file_path: str
    size_bytes: int
    created_at: str
    checksum: Optional[str] = None
    

class Release(BaseModel):
    """Complete release information."""
    
    version: str
    git_sha: str
    created_at: str
    commit_message: str
    artifacts: List[ReleaseArtifact]
    release_notes: Optional[str] = None
    

class ReleasesManifest(BaseModel):
    """RELEASES.json structure."""
    
    project_name: str
    current_version: str
    releases: List[Release]
    

class ReleaseManager:
    """Manages releases, versioning, and artifact archiving.
    
    Key Features:
    - SemVer calculation from commit types (feat:, fix:, breaking:)
    - Git SHA → Version → Artifact tracking
    - Automatic artifact archiving (zip bundles)
    - RELEASES.json manifest management
    - Release notes generation
    """
    
    COMMIT_TYPE_BUMP_MAP = {
        "breaking": "major",
        "feat": "minor",
        "fix": "patch",
        "refactor": "patch",
        "perf": "patch",
        "docs": None,  # No version bump
        "chore": None,
    }
    
    def __init__(self, project_root: Path, project_name: Optional[str] = None):
        """Initialize ReleaseManager.
        
        Args:
            project_root: Project root directory
            project_name: Project name (defaults to directory name)
        """
        self.project_root = project_root
        self.project_name = project_name or project_root.name
        self.releases_dir = project_root / "releases"
        self.releases_manifest = project_root / "RELEASES.json"
        self.logger = logger.bind(component="ReleaseManager")
    
    def get_current_version(self) -> str:
        """Get current version from RELEASES.json or default to 0.1.0.
        
        Returns:
            Current version string
        """
        if self.releases_manifest.exists():
            try:
                with self.releases_manifest.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                manifest = ReleasesManifest(**data)
                return manifest.current_version
            except Exception as e:
                self.logger.warning(f"Failed to read RELEASES.json: {e}")
        
        return "0.1.0"
    
    def calculate_next_version(
        self, 
        commit_message: Optional[str] = None,
        bump_type: Optional[str] = None
    ) -> str:
        """Calculate next version based on commit message or explicit bump type.
        
        Args:
            commit_message: Commit message to parse for type (e.g., "feat: add feature")
            bump_type: Explicit bump type (major, minor, patch)
            
        Returns:
            Next version string
        """
        current_version = self.get_current_version()
        
        # Parse commit message to determine bump type if not explicit
        if bump_type is None and commit_message:
            bump_type = self._parse_commit_type(commit_message)
        
        # Default to patch if no type determined
        if bump_type is None:
            bump_type = "patch"
        
        return self._bump_version(current_version, bump_type)
    
    def _parse_commit_type(self, commit_message: str) -> Optional[str]:
        """Parse commit message to determine bump type.
        
        Looks for Conventional Commits format: type: subject
        Example: "feat: add new feature" → "minor"
        
        Args:
            commit_message: Commit message
            
        Returns:
            Bump type (major, minor, patch) or None
        """
        # Check for breaking change
        if "BREAKING CHANGE" in commit_message or "!" in commit_message.split(":")[0]:
            return "major"
        
        # Extract type from conventional commits format
        match = re.match(r'^(\w+)(?:\([^)]+\))?:', commit_message)
        if match:
            commit_type = match.group(1).lower()
            return self.COMMIT_TYPE_BUMP_MAP.get(commit_type)
        
        return None
    
    def _bump_version(self, version: str, bump_type: str) -> str:
        """Bump semantic version.
        
        Args:
            version: Current version (e.g., "1.2.3")
            bump_type: Type of bump (major, minor, patch)
            
        Returns:
            Bumped version string
        """
        match = re.match(r'(\d+)\.(\d+)\.(\d+)', version)
        if not match:
            return version
        
        major, minor, patch = map(int, match.groups())
        
        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        else:  # patch
            patch += 1
        
        return f"{major}.{minor}.{patch}"
    
    def get_last_commit_sha(self) -> str:
        """Get SHA of last commit.
        
        Returns:
            Git commit SHA
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "unknown"
    
    def get_last_commit_message(self) -> str:
        """Get last commit message.
        
        Returns:
            Commit message
        """
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "No commit message"
    
    def create_release_bundle(
        self, 
        version: str,
        files_to_include: List[Path],
        output_name: Optional[str] = None
    ) -> Path:
        """Create ZIP archive of release artifacts.
        
        Args:
            version: Version string
            files_to_include: List of files/directories to include
            output_name: Custom output name (defaults to {project}_{version}.zip)
            
        Returns:
            Path to created ZIP file
        """
        # Ensure releases directory exists
        self.releases_dir.mkdir(exist_ok=True)
        
        # Generate ZIP name
        if output_name is None:
            safe_version = version.replace(".", "_")
            output_name = f"{self.project_name}_v{safe_version}.zip"
        
        zip_path = self.releases_dir / output_name
        
        # Create ZIP
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files_to_include:
                if file_path.is_file():
                    # Add file with relative path
                    arcname = file_path.relative_to(self.project_root)
                    zipf.write(file_path, arcname)
                elif file_path.is_dir():
                    # Add directory recursively
                    for item in file_path.rglob("*"):
                        if item.is_file():
                            arcname = item.relative_to(self.project_root)
                            zipf.write(item, arcname)
        
        self.logger.info(f"Created release bundle: {zip_path} ({zip_path.stat().st_size / 1024:.2f} KB)")
        return zip_path
    
    def record_release(
        self, 
        version: str,
        artifact_paths: List[Path],
        release_notes: Optional[str] = None
    ) -> None:
        """Record release in RELEASES.json.
        
        Args:
            version: Version string
            artifact_paths: Paths to release artifacts
            release_notes: Optional release notes
        """
        git_sha = self.get_last_commit_sha()
        commit_message = self.get_last_commit_message()
        
        # Build artifact info
        artifacts = []
        for artifact_path in artifact_paths:
            if artifact_path.exists():
                artifacts.append(ReleaseArtifact(
                    file_path=str(artifact_path.relative_to(self.project_root)),
                    size_bytes=artifact_path.stat().st_size,
                    created_at=datetime.now().isoformat()
                ))
        
        # Create new release
        new_release = Release(
            version=version,
            git_sha=git_sha,
            created_at=datetime.now().isoformat(),
            commit_message=commit_message,
            artifacts=artifacts,
            release_notes=release_notes
        )
        
        # Load or create manifest
        if self.releases_manifest.exists():
            with self.releases_manifest.open("r", encoding="utf-8") as f:
                data = json.load(f)
            manifest = ReleasesManifest(**data)
            manifest.releases.append(new_release)
            manifest.current_version = version
        else:
            manifest = ReleasesManifest(
                project_name=self.project_name,
                current_version=version,
                releases=[new_release]
            )
        
        # Write manifest
        with self.releases_manifest.open("w", encoding="utf-8") as f:
            json.dump(manifest.model_dump(), f, indent=2)
        
        self.logger.info(f"✅ Recorded release {version} (SHA: {git_sha[:8]})")
    
    def get_release_by_sha(self, git_sha: str) -> Optional[Release]:
        """Get release information by Git SHA.
        
        Args:
            git_sha: Git commit SHA (full or short)
            
        Returns:
            Release if found, None otherwise
        """
        if not self.releases_manifest.exists():
            return None
        
        with self.releases_manifest.open("r", encoding="utf-8") as f:
            data = json.load(f)
        manifest = ReleasesManifest(**data)
        
        for release in manifest.releases:
            if release.git_sha.startswith(git_sha):
                return release
        
        return None
    
    def get_release_by_version(self, version: str) -> Optional[Release]:
        """Get release information by version string.
        
        Args:
            version: Version string
            
        Returns:
            Release if found, None otherwise
        """
        if not self.releases_manifest.exists():
            return None
        
        with self.releases_manifest.open("r", encoding="utf-8") as f:
            data = json.load(f)
        manifest = ReleasesManifest(**data)
        
        for release in manifest.releases:
            if release.version == version:
                return release
        
        return None
    
    def generate_release_notes(self, since_version: Optional[str] = None) -> str:
        """Generate release notes from commit history.
        
        Args:
            since_version: Generate notes since this version
            
        Returns:
            Markdown formatted release notes
        """
        # Get commit range
        if since_version:
            release = self.get_release_by_version(since_version)
            if release:
                commit_range = f"{release.git_sha}..HEAD"
            else:
                commit_range = "HEAD~10..HEAD"  # Last 10 commits
        else:
            commit_range = "HEAD~10..HEAD"
        
        try:
            result = subprocess.run(
                ["git", "log", commit_range, "--pretty=format:%s"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            
            commits = result.stdout.strip().splitlines()
            
            # Group by type
            features = []
            fixes = []
            others = []
            
            for commit in commits:
                if commit.startswith("feat"):
                    features.append(commit)
                elif commit.startswith("fix"):
                    fixes.append(commit)
                else:
                    others.append(commit)
            
            # Build markdown
            notes = []
            if features:
                notes.append("### ✨ Features")
                notes.extend(f"- {c}" for c in features)
                notes.append("")
            
            if fixes:
                notes.append("### 🐛 Fixes")
                notes.extend(f"- {c}" for c in fixes)
                notes.append("")
            
            if others:
                notes.append("### 📝 Other Changes")
                notes.extend(f"- {c}" for c in others)
            
            return "\n".join(notes)
        
        except subprocess.CalledProcessError:
            return "No release notes available"
