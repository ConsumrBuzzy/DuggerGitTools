"""Version management system with patterns from Convoso and other projects."""

import json
import re
from pathlib import Path

from loguru import logger

from .config import DGTConfig
from .git_operations import GitOperations


class VersionManager:
    """Advanced version management for different project types."""

    def __init__(self, config: DGTConfig) -> None:
        """Initialize version manager."""
        self.config = config
        self.logger = logger.bind(versioning=True)
        self.git_ops = GitOperations(config)
        self.repo_path = config.project_root

    def get_current_version(self) -> str:
        """Get current version based on project type."""
        project_type = self._detect_project_type()

        if project_type == "Chrome Extension":
            return self._get_chrome_version()
        if project_type == "Python":
            return self._get_python_version()
        if project_type == "Rust":
            return self._get_rust_version()
        if project_type == "Node.js":
            return self._get_nodejs_version()
        return "0.0.0"

    def build_release_version(self) -> str:
        """Build release version with commit count (Convoso pattern)."""
        base_version = self.get_current_version()
        commit_count = self.git_ops.get_commit_count()

        # Convoso pattern: r{base}.r{commits}
        if self._detect_project_type() == "Chrome Extension":
            return f"r{base_version}.r{commit_count}"

        # Standard pattern: {base}.{commits}
        return f"{base_version}.{commit_count}"

    def bump_version(self, bump_type: str = "patch") -> str:
        """Bump version based on semantic versioning."""
        current = self.get_current_version()

        # Extract version numbers
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", current)
        if not match:
            self.logger.warning(f"Invalid version format: {current}")
            return current

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
            return current

        new_version = f"{major}.{minor}.{patch}"

        # Update version file
        project_type = self._detect_project_type()
        if project_type == "Chrome Extension":
            self._update_chrome_version(new_version)
        elif project_type == "Python":
            self._update_python_version(new_version)
        elif project_type == "Rust":
            self._update_rust_version(new_version)
        elif project_type == "Node.js":
            self._update_nodejs_version(new_version)

        self.logger.info(f"Version bumped from {current} to {new_version}")
        return new_version

    def write_version_file(self, target: Path | None = None) -> str:
        """Write version to file (Convoso pattern)."""
        version = self.build_release_version()

        if target is None:
            target = self.repo_path / "VERSION"

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(version, encoding="utf-8")

        self.logger.info(f"Version written to {target}: {version}")
        return version

    def _detect_project_type(self) -> str:
        """Detect project type based on anchor files."""
        if (self.repo_path / "manifest.json").exists():
            return "Chrome Extension"
        if (self.repo_path / "Cargo.toml").exists():
            return "Rust"
        if (self.repo_path / "package.json").exists():
            return "Node.js"
        if (self.repo_path / "requirements.txt").exists() or (self.repo_path / "pyproject.toml").exists():
            return "Python"
        return "Unknown"

    def _get_chrome_version(self) -> str:
        """Get Chrome Extension version from manifest.json."""
        manifest_path = self.repo_path / "manifest.json"
        try:
            with manifest_path.open(encoding="utf-8") as f:
                manifest = json.load(f)
            return str(manifest.get("version", "0.0.0"))
        except Exception as e:
            self.logger.error(f"Failed to read Chrome version: {e}")
            return "0.0.0"

    def _get_python_version(self) -> str:
        """Get Python project version."""
        # Try pyproject.toml first
        pyproject_toml = self.repo_path / "pyproject.toml"
        if pyproject_toml.exists():
            try:
                import tomllib
                with pyproject_toml.open("rb") as f:
                    data = tomllib.load(f)
                return data.get("project", {}).get("version", "0.0.0")
            except Exception as e:
                self.logger.warning(f"Failed to read pyproject.toml: {e}")

        # Try setup.py
        setup_py = self.repo_path / "setup.py"
        if setup_py.exists():
            try:
                # Simple regex extraction
                content = setup_py.read_text()
                match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
            except Exception as e:
                self.logger.warning(f"Failed to read setup.py: {e}")

        # Try VERSION file
        version_file = self.repo_path / "VERSION"
        if version_file.exists():
            try:
                return version_file.read_text().strip()
            except Exception as e:
                self.logger.warning(f"Failed to read VERSION file: {e}")

        return "0.0.0"

    def _get_rust_version(self) -> str:
        """Get Rust project version from Cargo.toml."""
        cargo_toml = self.repo_path / "Cargo.toml"
        try:
            import tomllib
            with cargo_toml.open("rb") as f:
                data = tomllib.load(f)
            return data.get("package", {}).get("version", "0.0.0")
        except Exception as e:
            self.logger.error(f"Failed to read Rust version: {e}")
            return "0.0.0"

    def _get_nodejs_version(self) -> str:
        """Get Node.js project version from package.json."""
        package_json = self.repo_path / "package.json"
        try:
            with package_json.open(encoding="utf-8") as f:
                package = json.load(f)
            return str(package.get("version", "0.0.0"))
        except Exception as e:
            self.logger.error(f"Failed to read Node.js version: {e}")
            return "0.0.0"

    def _update_chrome_version(self, new_version: str) -> None:
        """Update Chrome Extension version in manifest.json."""
        manifest_path = self.repo_path / "manifest.json"
        try:
            with manifest_path.open(encoding="utf-8") as f:
                manifest = json.load(f)

            manifest["version"] = new_version

            with manifest_path.open("w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            self.logger.info(f"Updated Chrome Extension version to {new_version}")
        except Exception as e:
            self.logger.error(f"Failed to update Chrome version: {e}")

    def _update_python_version(self, new_version: str) -> None:
        """Update Python project version."""
        # Update pyproject.toml
        pyproject_toml = self.repo_path / "pyproject.toml"
        if pyproject_toml.exists():
            try:
                import tomllib
                with pyproject_toml.open("rb") as f:
                    data = tomllib.load(f)

                if "project" in data:
                    data["project"]["version"] = new_version

                    # Write back using toml library
                    try:
                        import tomli_w
                        with pyproject_toml.open("wb") as f:
                            tomli_w.dump(data, f)
                    except ImportError:
                        # Fallback to simple text replacement
                        content = pyproject_toml.read_text()
                        content = re.sub(
                            r'version\s*=\s*["\'][^"\']+["\']',
                            f'version = "{new_version}"',
                            content,
                        )
                        pyproject_toml.write_text(content)

                    self.logger.info(f"Updated Python version to {new_version}")
                    return
            except Exception as e:
                self.logger.warning(f"Failed to update pyproject.toml: {e}")

        # Update VERSION file
        version_file = self.repo_path / "VERSION"
        version_file.write_text(new_version, encoding="utf-8")
        self.logger.info(f"Updated VERSION file to {new_version}")

    def _update_rust_version(self, new_version: str) -> None:
        """Update Rust project version in Cargo.toml."""
        cargo_toml = self.repo_path / "Cargo.toml"
        try:
            import tomllib
            with cargo_toml.open("rb") as f:
                data = tomllib.load(f)

            data["package"]["version"] = new_version

            # Write back using toml library
            try:
                import tomli_w
                with cargo_toml.open("wb") as f:
                    tomli_w.dump(data, f)
            except ImportError:
                # Fallback to simple text replacement
                content = cargo_toml.read_text()
                content = re.sub(
                    r'version\s*=\s*["\'][^"\']+["\']',
                    f'version = "{new_version}"',
                    content,
                )
                cargo_toml.write_text(content)

            self.logger.info(f"Updated Rust version to {new_version}")
        except Exception as e:
            self.logger.error(f"Failed to update Rust version: {e}")

    def _update_nodejs_version(self, new_version: str) -> None:
        """Update Node.js project version in package.json."""
        package_json = self.repo_path / "package.json"
        try:
            with package_json.open(encoding="utf-8") as f:
                package = json.load(f)

            package["version"] = new_version

            with package_json.open("w", encoding="utf-8") as f:
                json.dump(package, f, indent=2)

            self.logger.info(f"Updated Node.js version to {new_version}")
        except Exception as e:
            self.logger.error(f"Failed to update Node.js version: {e}")

    def validate_version(self, version: str) -> bool:
        """Validate version format."""
        # Semantic versioning pattern
        semver_pattern = r"^\d+\.\d+\.\d+$"
        return bool(re.match(semver_pattern, version))

    def get_version_info(self) -> dict:
        """Get comprehensive version information."""
        current_version = self.get_current_version()
        release_version = self.build_release_version()
        commit_count = self.git_ops.get_commit_count()
        project_type = self._detect_project_type()

        return {
            "current_version": current_version,
            "release_version": release_version,
            "commit_count": commit_count,
            "project_type": project_type,
            "is_valid": self.validate_version(current_version),
            "last_commit": self.git_ops.get_last_commit_hash()[:8],
        }
