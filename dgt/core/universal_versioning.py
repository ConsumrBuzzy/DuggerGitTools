"""Universal versioning system with Dugger-Schema support."""

import re

from loguru import logger

from .config import DGTConfig
from .git_operations import GitOperations
from .schema import DuggerSchema


class UniversalVersionManager:
    """Language-agnostic version management using Dugger-Schema."""

    def __init__(self, config: DGTConfig, schema: DuggerSchema) -> None:
        """Initialize universal version manager."""
        self.config = config
        self.schema = schema
        self.logger = logger.bind(versioning=True)
        self.git_ops = GitOperations(config)
        self.repo_path = config.project_root

    def get_current_versions(self) -> dict[str, str]:
        """Get current versions from all configured version files."""
        versions = {}

        for version_format in self.schema.version_formats:
            file_path = self.repo_path / version_format.file_path

            if not file_path.exists():
                self.logger.warning(f"Version file not found: {file_path}")
                continue

            try:
                content = file_path.read_text(encoding=version_format.encoding)
                match = re.search(version_format.pattern, content, re.MULTILINE)

                if match:
                    version = match.group(1)
                    versions[version_format.file_path] = version
                    self.logger.debug(f"Found version {version} in {version_format.file_path}")
                else:
                    self.logger.warning(f"Version pattern not found in {version_format.file_path}")

            except Exception as e:
                self.logger.error(f"Failed to read version from {version_format.file_path}: {e}")

        return versions

    def build_release_version(self, base_version: str | None = None) -> str:
        """Build release version using project-specific format."""
        if base_version is None:
            # Get the first available version
            current_versions = self.get_current_versions()
            if not current_versions:
                return "0.0.0.1"
            base_version = list(current_versions.values())[0]

        # Get commit count
        commit_count = self.git_ops.get_commit_count()

        # Apply project-specific formatting
        if self.schema.project_type.value == "chrome-extension":
            # Convoso pattern: r{base}.r{commits}
            return f"r{base_version}.r{commit_count}"
        # Standard pattern: {base}.{commits}
        return f"{base_version}.{commit_count}"

    def bump_version(self, bump_type: str = "patch") -> dict[str, str]:
        """Bump version across all configured version files."""
        current_versions = self.get_current_versions()

        if not current_versions:
            raise ValueError("No version files found to bump")

        # Calculate new version (use first version as base)
        base_version = list(current_versions.values())[0]
        new_version = self._calculate_new_version(base_version, bump_type)

        updated_versions = {}

        # Update all version files
        for version_format in self.schema.version_formats:
            file_path = self.repo_path / version_format.file_path

            if not file_path.exists():
                continue

            try:
                content = file_path.read_text(encoding=version_format.encoding)

                # Find and replace version
                match = re.search(version_format.pattern, content, re.MULTILINE)
                if match:
                    if version_format.replacement:
                        # Use template replacement
                        new_content = re.sub(
                            version_format.pattern,
                            version_format.replacement.format(new_version=new_version),
                            content,
                            flags=re.MULTILINE,
                        )
                    else:
                        # Simple replacement
                        new_content = re.sub(
                            version_format.pattern,
                            match.group(0).replace(match.group(1), new_version),
                            content,
                            flags=re.MULTILINE,
                        )

                    file_path.write_text(new_content, encoding=version_format.encoding)
                    updated_versions[version_format.file_path] = new_version
                    self.logger.info(f"Updated {version_format.file_path}: {base_version} -> {new_version}")
                else:
                    self.logger.warning(f"Version pattern not found in {version_format.file_path}")

            except Exception as e:
                self.logger.error(f"Failed to update {version_format.file_path}: {e}")

        return updated_versions

    def validate_versions(self) -> dict[str, bool]:
        """Validate all version formats."""
        results = {}

        for version_format in self.schema.version_formats:
            file_path = self.repo_path / version_format.file_path

            if not file_path.exists():
                results[version_format.file_path] = False
                continue

            try:
                content = file_path.read_text(encoding=version_format.encoding)
                match = re.search(version_format.pattern, content, re.MULTILINE)

                if match:
                    version = match.group(1)
                    results[version_format.file_path] = self._is_valid_semver(version)
                else:
                    results[version_format.file_path] = False

            except Exception:
                results[version_format.file_path] = False

        return results

    def get_version_info(self) -> dict:
        """Get comprehensive version information."""
        current_versions = self.get_current_versions()
        validation_results = self.validate_versions()
        release_version = self.build_release_version()

        return {
            "project_type": self.schema.project_type.value,
            "current_versions": current_versions,
            "validation_results": validation_results,
            "release_version": release_version,
            "commit_count": self.git_ops.get_commit_count(),
            "last_commit": self.git_ops.get_last_commit_hash()[:8],
            "auto_bump_enabled": self.schema.auto_bump,
            "bump_type": self.schema.bump_type,
            "version_files": [fmt.file_path for fmt in self.schema.version_formats],
        }

    def _calculate_new_version(self, current_version: str, bump_type: str) -> str:
        """Calculate new version using semantic versioning."""
        # Extract version numbers
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", current_version)
        if not match:
            self.logger.warning(f"Invalid version format: {current_version}")
            return current_version

        major, minor, patch = map(int, match.groups())

        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        elif bump_type == "patch":
            patch += 1
        else:
            self.logger.error(f"Invalid bump type: {bump_type}")
            return current_version

        return f"{major}.{minor}.{patch}"

    def _is_valid_semver(self, version: str) -> bool:
        """Check if version follows semantic versioning."""
        semver_pattern = r"^\d+\.\d+\.\d+$"
        return bool(re.match(semver_pattern, version))

    def sync_versions(self, target_version: str) -> dict[str, str]:
        """Sync all version files to a specific target version."""
        if not self._is_valid_semver(target_version):
            raise ValueError(f"Invalid target version: {target_version}")

        updated_versions = {}

        for version_format in self.schema.version_formats:
            file_path = self.repo_path / version_format.file_path

            if not file_path.exists():
                continue

            try:
                content = file_path.read_text(encoding=version_format.encoding)

                # Find and replace version
                if version_format.replacement:
                    new_content = re.sub(
                        version_format.pattern,
                        version_format.replacement.format(new_version=target_version),
                        content,
                        flags=re.MULTILINE,
                    )
                else:
                    # Simple replacement
                    match = re.search(version_format.pattern, content, re.MULTILINE)
                    if match:
                        new_content = re.sub(
                            version_format.pattern,
                            match.group(0).replace(match.group(1), target_version),
                            content,
                            flags=re.MULTILINE,
                        )
                    else:
                        continue

                file_path.write_text(new_content, encoding=version_format.encoding)
                updated_versions[version_format.file_path] = target_version
                self.logger.info(f"Synced {version_format.file_path} to {target_version}")

            except Exception as e:
                self.logger.error(f"Failed to sync {version_format.file_path}: {e}")

        return updated_versions


class MultiProviderVersionManager:
    """Version management for multi-provider projects."""

    def __init__(self, config: DGTConfig, schema: DuggerSchema) -> None:
        """Initialize multi-provider version manager."""
        self.config = config
        self.schema = schema
        self.logger = logger.bind(multi_versioning=True)

        if not schema.multi_provider:
            raise ValueError("Multi-provider configuration not found")

    def get_unified_version(self) -> str:
        """Get unified version across all providers."""
        versions = {}

        # Collect versions from all providers
        for provider_name in self.schema.multi_provider.enabled_providers:
            try:
                # This would integrate with individual provider version managers
                # For now, we'll simulate this
                versions[provider_name] = self._get_provider_version(provider_name)
            except Exception as e:
                self.logger.warning(f"Failed to get version from {provider_name}: {e}")

        if not versions:
            return "0.0.0"

        # Apply merge strategy
        merge_strategy = self.schema.multi_provider.merge_strategies.get("version", "highest")

        if merge_strategy == "highest":
            return max(versions.values(), key=self._version_key)
        if merge_strategy == "lowest":
            return min(versions.values(), key=self._version_key)
        if merge_strategy == "first":
            return list(versions.values())[0]
        self.logger.warning(f"Unknown merge strategy: {merge_strategy}")
        return list(versions.values())[0]

    def sync_all_providers(self, target_version: str) -> dict[str, bool]:
        """Sync all providers to target version."""
        results = {}

        for provider_name in self.schema.multi_provider.enabled_providers:
            try:
                self._set_provider_version(provider_name, target_version)
                results[provider_name] = True
                self.logger.info(f"Synced {provider_name} to {target_version}")
            except Exception as e:
                results[provider_name] = False
                self.logger.error(f"Failed to sync {provider_name}: {e}")

        return results

    def _get_provider_version(self, provider_name: str) -> str:
        """Get version from a specific provider."""
        # This would integrate with individual provider version managers
        # For now, return a placeholder
        return "1.0.0"

    def _set_provider_version(self, provider_name: str, version: str) -> None:
        """Set version for a specific provider."""
        # This would integrate with individual provider version managers
        # For now, just log the action
        self.logger.info(f"Would set {provider_name} version to {version}")

    def _version_key(self, version: str) -> tuple[int, int, int]:
        """Convert version string to comparable tuple."""
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
        if match:
            return tuple(map(int, match.groups()))
        return (0, 0, 0)
