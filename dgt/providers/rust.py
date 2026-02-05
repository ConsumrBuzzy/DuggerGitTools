"""Rust provider for DGT with Cargo integration."""

import subprocess
import time
from pathlib import Path
from typing import Any

from .base import BaseProvider, CheckResult, ProviderType


class RustProvider(BaseProvider):
    """Provider for Rust projects with Cargo workflow integration."""

    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.RUST

    @property
    def anchor_files(self) -> list[str]:
        """Return list of anchor files that identify Rust projects."""
        return ["Cargo.toml"]

    def detect_project(self, project_root: Path) -> bool:
        """Detect if this is a Rust project by checking for Cargo.toml."""
        return (project_root / "Cargo.toml").exists()

    def _validate_environment_impl(self) -> None:
        """Validate Rust environment using RustToolchain."""
        from ..core.rust_toolchain import RustToolchain

        toolchain = RustToolchain(self.config.project_root)
        is_ok, message, toolchain_info = toolchain.verify_toolchain()

        if not is_ok:
            raise RuntimeError(message)

        self.logger.info(message)

        # Store toolchain info for later use
        self._toolchain_info = toolchain_info

    def run_pre_flight_checks(self, staged_files: list[Path]) -> list[CheckResult]:
        """Run Rust-specific pre-flight checks."""
        results = []

        # Check OpenSSL availability
        results.append(self._check_openssl())

        # Format code
        results.append(self._run_cargo_fmt())

        # Check compilation
        results.append(self._run_cargo_check())

        # Run clippy for linting
        results.append(self._run_cargo_clippy())

        # Run tests if relevant files changed
        if self._should_run_tests(staged_files):
            results.append(self._run_cargo_test())

        return results

    def run_post_flight_checks(self, commit_hash: str) -> list[CheckResult]:
        """Run Rust-specific post-flight checks."""
        results = []

        # Run full test suite
        results.append(self._run_cargo_test_all())

        # Build release version
        results.append(self._run_cargo_build_release())

        # Run benchmarks if available
        if self._has_benchmarks():
            results.append(self._run_cargo_bench())

        return results

    def get_metadata(self) -> dict[str, Any]:
        """Get Rust-specific metadata for commit messages."""
        metadata = {}
        project_root = self.config.project_root

        # Parse Cargo.toml for version and package info
        cargo_toml = project_root / "Cargo.toml"
        if cargo_toml.exists():
            try:
                import tomllib
                with cargo_toml.open("rb") as f:
                    data = tomllib.load(f)

                package = data.get("package", {})
                metadata["version"] = package.get("version", "unknown")
                metadata["package_name"] = package.get("name", "unknown")

                # Get Rust edition
                metadata["edition"] = package.get("edition", "2021")

            except Exception as e:
                self.logger.warning(f"Failed to read Cargo.toml: {e}")

        # Get Rust version
        try:
            result = subprocess.run(
                ["rustc", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            metadata["rust_version"] = result.stdout.strip()
        except Exception as e:
            self.logger.warning(f"Failed to get Rust version: {e}")

        return metadata

    def _run_cargo_fmt(self) -> CheckResult:
        """Run cargo fmt to format code."""
        start_time = time.time()

        try:
            result = subprocess.run(
                ["cargo", "fmt", "--all", "--", "--check"],
                capture_output=True,
                text=True,
                check=True,
            )
            return CheckResult(
                success=True,
                message="Code formatting check passed",
                execution_time=time.time() - start_time,
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Code formatting issues found. Run 'cargo fmt' to fix: {e.stderr}",
                execution_time=time.time() - start_time,
            )

    def _run_cargo_check(self) -> CheckResult:
        """Run cargo check to verify compilation."""
        start_time = time.time()

        try:
            result = subprocess.run(
                ["cargo", "check", "--all"],
                capture_output=True,
                text=True,
                check=True,
            )
            return CheckResult(
                success=True,
                message="Compilation check passed",
                execution_time=time.time() - start_time,
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Compilation failed: {e.stderr}",
                execution_time=time.time() - start_time,
            )

    def _run_cargo_clippy(self) -> CheckResult:
        """Run cargo clippy for linting."""
        start_time = time.time()

        try:
            result = subprocess.run(
                ["cargo", "clippy", "--all", "--", "-D", "warnings"],
                capture_output=True,
                text=True,
                check=True,
            )
            return CheckResult(
                success=True,
                message="Clippy linting passed",
                execution_time=time.time() - start_time,
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Clippy linting failed: {e.stderr}",
                execution_time=time.time() - start_time,
            )

    def _should_run_tests(self, staged_files: list[Path]) -> bool:
        """Determine if tests should be run based on staged files."""
        rust_files = [f for f in staged_files if f.suffix in [".rs", ".toml"]]
        return len(rust_files) > 0

    def _run_cargo_test(self) -> CheckResult:
        """Run cargo test."""
        start_time = time.time()

        try:
            result = subprocess.run(
                ["cargo", "test", "--all"],
                capture_output=True,
                text=True,
                check=True,
            )
            return CheckResult(
                success=True,
                message="Tests passed",
                details={"output": result.stdout},
                execution_time=time.time() - start_time,
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Tests failed: {e.stderr}",
                details={"output": e.stdout},
                execution_time=time.time() - start_time,
            )

    def _run_cargo_test_all(self) -> CheckResult:
        """Run full test suite with all features."""
        start_time = time.time()

        try:
            result = subprocess.run(
                ["cargo", "test", "--all", "--all-features"],
                capture_output=True,
                text=True,
                check=True,
            )
            return CheckResult(
                success=True,
                message="Full test suite passed",
                details={"output": result.stdout},
                execution_time=time.time() - start_time,
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Full test suite failed: {e.stderr}",
                details={"output": e.stdout},
                execution_time=time.time() - start_time,
            )

    def _run_cargo_build_release(self) -> CheckResult:
        """Run cargo build in release mode."""
        start_time = time.time()

        try:
            result = subprocess.run(
                ["cargo", "build", "--release", "--all"],
                capture_output=True,
                text=True,
                check=True,
            )
            return CheckResult(
                success=True,
                message="Release build successful",
                execution_time=time.time() - start_time,
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Release build failed: {e.stderr}",
                execution_time=time.time() - start_time,
            )

    def _has_benchmarks(self) -> bool:
        """Check if the project has benchmarks."""
        cargo_toml = self.config.project_root / "Cargo.toml"
        if not cargo_toml.exists():
            return False

        try:
            import tomllib
            with cargo_toml.open("rb") as f:
                data = tomllib.load(f)

            # Check for benchmark dependencies or [[bench]] sections
            if "bench" in data:
                return True

            dev_dependencies = data.get("dev-dependencies", {})
            return any("criterion" in dep or "bencher" in dep for dep in dev_dependencies)

        except Exception:
            return False

    def _run_cargo_bench(self) -> CheckResult:
        """Run cargo bench if benchmarks are available."""
        start_time = time.time()

        try:
            result = subprocess.run(
                ["cargo", "bench", "--all"],
                capture_output=True,
                text=True,
                check=True,
            )
            return CheckResult(
                success=True,
                message="Benchmarks passed",
                details={"output": result.stdout},
                execution_time=time.time() - start_time,
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Benchmarks failed: {e.stderr}",
                details={"output": e.stdout},
                execution_time=time.time() - start_time,
            )

    def _check_openssl(self) -> CheckResult:
        """Check OpenSSL availability using RustToolchain."""
        start_time = time.time()

        try:
            from ..core.rust_toolchain import RustToolchain

            toolchain = RustToolchain(self.config.project_root)
            openssl_info = toolchain.find_openssl()

            if openssl_info:
                return CheckResult(
                    success=True,
                    message=f"System OpenSSL found: {openssl_info.openssl_dir}",
                    details={"openssl_dir": str(openssl_info.openssl_dir), "lib_dir": str(openssl_info.lib_dir)},
                    execution_time=time.time() - start_time,
                )
            return CheckResult(
                success=True,
                message="No system OpenSSL - will use vendored build (slower)",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return CheckResult(
                success=False,
                message=f"Failed to check OpenSSL: {e}",
                execution_time=time.time() - start_time,
            )
