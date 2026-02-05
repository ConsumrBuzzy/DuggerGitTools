"""Chrome Extension provider for DGT with manifest validation."""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .base import BaseProvider, CheckResult, ProviderType


class ChromeExtensionProvider(BaseProvider):
    """Provider for Chrome Extension projects with manifest validation."""

    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.CHROME_EXTENSION

    @property
    def anchor_files(self) -> list[str]:
        """Return list of anchor files that identify Chrome Extension projects."""
        return ["manifest.json"]

    def detect_project(self, project_root: Path) -> bool:
        """Detect if this is a Chrome Extension project."""
        manifest_file = project_root / "manifest.json"
        if not manifest_file.exists():
            return False

        try:
            with manifest_file.open("r") as f:
                manifest = json.load(f)

            # Check for manifest_version key (required for Chrome extensions)
            return "manifest_version" in manifest

        except (json.JSONDecodeError, KeyError):
            return False

    def _validate_environment_impl(self) -> None:
        """Validate Chrome Extension development environment."""
        # Check for Node.js if package.json exists
        project_root = self.config.project_root
        package_json = project_root / "package.json"

        if package_json.exists():
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            node_version = result.stdout.strip()
            self.logger.info(f"Node.js version: {node_version}")

            result = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            npm_version = result.stdout.strip()
            self.logger.info(f"npm version: {npm_version}")

    def run_pre_flight_checks(self, staged_files: list[Path]) -> list[CheckResult]:
        """Run Chrome Extension-specific pre-flight checks."""
        results = []

        # Validate manifest.json
        results.append(self._validate_manifest())

        # Check for required files
        results.append(self._check_required_files())

        # Validate HTML files if staged
        html_files = [f for f in staged_files if f.suffix == ".html"]
        if html_files:
            results.extend(self._validate_html_files(html_files))

        # Validate JavaScript files if staged
        js_files = [f for f in staged_files if f.suffix in [".js", ".mjs", ".ts"]]
        if js_files:
            results.extend(self._validate_js_files(js_files))

        # Run build script if package.json exists
        if (self.config.project_root / "package.json").exists():
            results.append(self._run_build_script())

        return results

    def run_post_flight_checks(self, commit_hash: str) -> list[CheckResult]:
        """Run Chrome Extension-specific post-flight checks."""
        results = []

        # Bump version if configured
        if self.provider_config.custom_settings.get("auto_bump_version", False):
            results.append(self._bump_version())

        # Create release package if auto_build enabled
        if self.provider_config.custom_settings.get("auto_build", False):
            results.append(self._create_release_package())

        # Validate extension package
        results.append(self._validate_extension_package())

        return results

    def get_metadata(self) -> dict[str, Any]:
        """Get Chrome Extension-specific metadata for commit messages."""
        metadata = {}
        project_root = self.config.project_root

        # Parse manifest.json for extension info
        manifest_file = project_root / "manifest.json"
        if manifest_file.exists():
            try:
                with manifest_file.open("r") as f:
                    manifest = json.load(f)

                metadata["extension_name"] = manifest.get("name", "unknown")
                metadata["version"] = manifest.get("version", "unknown")
                metadata["manifest_version"] = manifest.get("manifest_version", "unknown")

                # Get extension type from permissions or background scripts
                if "permissions" in manifest:
                    metadata["permissions"] = ", ".join(manifest["permissions"])

                if "background" in manifest:
                    metadata["has_background"] = True

                if "content_scripts" in manifest:
                    metadata["has_content_scripts"] = True

            except Exception as e:
                self.logger.warning(f"Failed to read manifest.json: {e}")

        return metadata

    def _validate_manifest(self) -> CheckResult:
        """Validate manifest.json against Chrome Extension schema."""
        start_time = time.time()
        manifest_file = self.config.project_root / "manifest.json"

        try:
            with manifest_file.open("r") as f:
                manifest = json.load(f)

            # Basic validation
            required_fields = ["manifest_version", "name", "version"]
            missing_fields = [field for field in required_fields if field not in manifest]

            if missing_fields:
                return CheckResult(
                    success=False,
                    message=f"Missing required fields in manifest.json: {', '.join(missing_fields)}",
                    execution_time=time.time() - start_time,
                )

            # Validate manifest version
            manifest_version = manifest["manifest_version"]
            if manifest_version not in [2, 3]:
                return CheckResult(
                    success=False,
                    message=f"Unsupported manifest version: {manifest_version}. Expected 2 or 3.",
                    execution_time=time.time() - start_time,
                )

            # Validate version format (semver)
            version = manifest["version"]
            if not self._is_valid_version(version):
                return CheckResult(
                    success=False,
                    message=f"Invalid version format: {version}. Expected semver format (x.y.z).",
                    execution_time=time.time() - start_time,
                )

            return CheckResult(
                success=True,
                message="manifest.json validation passed",
                details={"manifest": manifest},
                execution_time=time.time() - start_time,
            )

        except json.JSONDecodeError as e:
            return CheckResult(
                success=False,
                message=f"Invalid JSON in manifest.json: {e}",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return CheckResult(
                success=False,
                message=f"Failed to validate manifest.json: {e}",
                execution_time=time.time() - start_time,
            )

    def _check_required_files(self) -> CheckResult:
        """Check for required files based on manifest configuration."""
        start_time = time.time()
        project_root = self.config.project_root

        try:
            with (project_root / "manifest.json").open("r") as f:
                manifest = json.load(f)

            missing_files = []

            # Check for icons
            icons = manifest.get("icons", {})
            for size, icon_path in icons.items():
                if not (project_root / icon_path).exists():
                    missing_files.append(f"icon_{size}: {icon_path}")

            # Check for background scripts
            background = manifest.get("background", {})
            if "service_worker" in background:
                sw_path = background["service_worker"]
                if not (project_root / sw_path).exists():
                    missing_files.append(f"service_worker: {sw_path}")
            elif "scripts" in background:
                for script in background["scripts"]:
                    if not (project_root / script).exists():
                        missing_files.append(f"background_script: {script}")

            # Check for content scripts
            content_scripts = manifest.get("content_scripts", [])
            for script_set in content_scripts:
                for script in script_set.get("js", []):
                    if not (project_root / script).exists():
                        missing_files.append(f"content_script: {script}")

            if missing_files:
                return CheckResult(
                    success=False,
                    message=f"Missing required files: {', '.join(missing_files)}",
                    execution_time=time.time() - start_time,
                )

            return CheckResult(
                success=True,
                message="All required files present",
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            return CheckResult(
                success=False,
                message=f"Failed to check required files: {e}",
                execution_time=time.time() - start_time,
            )

    def _validate_html_files(self, html_files: list[Path]) -> list[CheckResult]:
        """Validate HTML files."""
        results = []

        for html_file in html_files:
            start_time = time.time()

            try:
                # Basic HTML validation using Python's html.parser
                from html.parser import HTMLParser

                class HTMLValidator(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.errors = []

                    def error(self, message):
                        self.errors.append(message)

                parser = HTMLValidator()
                with html_file.open("r", encoding="utf-8") as f:
                    content = f.read()

                parser.feed(content)

                if parser.errors:
                    results.append(CheckResult(
                        success=False,
                        message=f"HTML validation failed for {html_file.name}: {parser.errors[0]}",
                        execution_time=time.time() - start_time,
                    ))
                else:
                    results.append(CheckResult(
                        success=True,
                        message=f"HTML validation passed for {html_file.name}",
                        execution_time=time.time() - start_time,
                    ))

            except Exception as e:
                results.append(CheckResult(
                    success=False,
                    message=f"Failed to validate {html_file.name}: {e}",
                    execution_time=time.time() - start_time,
                ))

        return results

    def _validate_js_files(self, js_files: list[Path]) -> list[CheckResult]:
        """Validate JavaScript/TypeScript files."""
        results = []

        for js_file in js_files:
            start_time = time.time()

            # Basic syntax check using Node.js if available
            try:
                result = subprocess.run(
                    ["node", "--check", str(js_file)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                results.append(CheckResult(
                    success=True,
                    message=f"JavaScript syntax check passed for {js_file.name}",
                    execution_time=time.time() - start_time,
                ))

            except subprocess.CalledProcessError as e:
                results.append(CheckResult(
                    success=False,
                    message=f"JavaScript syntax error in {js_file.name}: {e.stderr}",
                    execution_time=time.time() - start_time,
                ))

            except FileNotFoundError:
                # Node.js not available, skip validation
                results.append(CheckResult(
                    success=True,
                    message=f"Node.js not available, skipping validation for {js_file.name}",
                    execution_time=time.time() - start_time,
                ))

        return results

    def _run_build_script(self) -> CheckResult:
        """Run build script if defined in package.json."""
        start_time = time.time()
        project_root = self.config.project_root

        try:
            with (project_root / "package.json").open("r") as f:
                package_data = json.load(f)

            scripts = package_data.get("scripts", {})
            if "build" not in scripts:
                return CheckResult(
                    success=True,
                    message="No build script defined in package.json",
                    execution_time=time.time() - start_time,
                )

            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True,
            )

            return CheckResult(
                success=True,
                message="Build script executed successfully",
                details={"output": result.stdout},
                execution_time=time.time() - start_time,
            )

        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Build script failed: {e.stderr}",
                details={"output": e.stdout},
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return CheckResult(
                success=False,
                message=f"Failed to run build script: {e}",
                execution_time=time.time() - start_time,
            )

    def _bump_version(self) -> CheckResult:
        """Bump version in manifest.json."""
        start_time = time.time()
        manifest_file = self.config.project_root / "manifest.json"

        try:
            with manifest_file.open("r") as f:
                manifest = json.load(f)

            current_version = manifest["version"]
            new_version = self._increment_version(current_version)
            manifest["version"] = new_version

            with manifest_file.open("w") as f:
                json.dump(manifest, f, indent=2)

            return CheckResult(
                success=True,
                message=f"Version bumped from {current_version} to {new_version}",
                details={"old_version": current_version, "new_version": new_version},
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            return CheckResult(
                success=False,
                message=f"Failed to bump version: {e}",
                execution_time=time.time() - start_time,
            )

    def _validate_extension_package(self) -> CheckResult:
        """Validate the extension package for distribution."""
        start_time = time.time()

        # This would typically involve running Chrome's extension validation
        # For now, we'll do basic checks
        try:
            manifest_file = self.config.project_root / "manifest.json"
            with manifest_file.open("r") as f:
                manifest = json.load(f)

            # Check file size limits (Chrome extension limits)
            total_size = sum(
                f.stat().st_size
                for f in self.config.project_root.rglob("*")
                if f.is_file()
            )

            # Chrome Web Store limit is 128MB
            if total_size > 128 * 1024 * 1024:
                return CheckResult(
                    success=False,
                    message=f"Extension package too large: {total_size / (1024*1024):.1f}MB (limit: 128MB)",
                    execution_time=time.time() - start_time,
                )

            return CheckResult(
                success=True,
                message=f"Extension package validation passed ({total_size / (1024*1024):.1f}MB)",
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            return CheckResult(
                success=False,
                message=f"Extension package validation failed: {e}",
                execution_time=time.time() - start_time,
            )

    def _is_valid_version(self, version: str) -> bool:
        """Check if version string follows semver format."""
        import re
        semver_pattern = r"^\d+\.\d+\.\d+$"
        return re.match(semver_pattern, version) is not None

    def _create_release_package(self) -> CheckResult:
        """Create versioned ZIP package for Chrome Web Store upload.
        
        CBHuddle pattern: Extract version from manifest.json, zip dist/ directory,
        save to releases/ with version-tagged name.
        """
        start_time = time.time()
        project_root = self.config.project_root

        try:
            # Read manifest for version
            manifest_file = project_root / "manifest.json"
            with manifest_file.open("r") as f:
                manifest = json.load(f)
            version = manifest.get("version", "1.0.0")

            # Determine source directory (dist/ or extension/ or root)
            dist_dir = None
            if (project_root / "dist").exists():
                dist_dir = project_root / "dist"
            elif (project_root / "extension" / "dist").exists():
                dist_dir = project_root / "extension" / "dist"
            elif (project_root / "build").exists():
                dist_dir = project_root / "build"
            else:
                # No dist directory, package the entire project
                dist_dir = project_root

            # Create releases directory
            releases_dir = project_root / "releases"
            releases_dir.mkdir(exist_ok=True)

            # Create zip file with versioned name
            import zipfile
            safe_version = version.replace(".", "_")
            extension_name = manifest.get("name", "extension").replace(" ", "_")
            zip_name = f"{extension_name}_v{safe_version}.zip"
            zip_path = releases_dir / zip_name

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in dist_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(dist_dir)
                        zipf.write(file_path, arcname)

            zip_size = zip_path.stat().st_size / 1024  # KB

            return CheckResult(
                success=True,
                message=f"Created release package: {zip_name} ({zip_size:.2f} KB)",
                details={
                    "zip_path": str(zip_path),
                    "version": version,
                    "size_kb": zip_size,
                },
                execution_time=time.time() - start_time,
            )

        except Exception as e:
            return CheckResult(
                success=False,
                message=f"Failed to create release package: {e}",
                execution_time=time.time() - start_time,
            )

    def _increment_version(self, version: str) -> str:
        """Increment patch version."""
        parts = version.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {version}")

        major, minor, patch = map(int, parts)
        patch += 1

        return f"{major}.{minor}.{patch}"
