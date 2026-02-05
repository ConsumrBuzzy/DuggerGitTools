"""Linting Manager - Automated code quality and formatting.

NO MANUAL PEP8. NO MANUAL FORMATTING.
Wraps black, isort, and cargo fmt for zero-friction code quality.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass
class LintResult:
    """Result of a linting/formatting operation."""

    success: bool
    tool: str  # black, isort, cargo fmt, etc.
    files_processed: int
    message: str
    details: str | None = None


class LintingManager:
    """Automated code quality manager.
    
    Wraps standard tools:
    - black: Python formatting
    - isort: Python import sorting
    - cargo fmt: Rust formatting
    
    Integrated into commit workflow for zero-friction quality.
    """

    def __init__(self, project_root: Path):
        """Initialize LintingManager.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root
        self.logger = logger.bind(component="LintingManager")

    def format_python_files(self, files: list[Path], check_only: bool = False) -> LintResult:
        """Format Python files with black.
        
        Args:
            files: List of Python files to format
            check_only: If True, only check without modifying
            
        Returns:
            LintResult
        """
        python_files = [f for f in files if f.suffix == ".py"]

        if not python_files:
            return LintResult(
                success=True,
                tool="black",
                files_processed=0,
                message="No Python files to format",
            )

        try:
            # Check if black is installed
            subprocess.run(
                ["black", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return LintResult(
                success=False,
                tool="black",
                files_processed=0,
                message="black not installed (install: pip install black)",
            )

        try:
            cmd = ["black"]
            if check_only:
                cmd.append("--check")
            cmd.extend([str(f) for f in python_files])

            result = subprocess.run(
                cmd,
                check=False, cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                action = "checked" if check_only else "formatted"
                return LintResult(
                    success=True,
                    tool="black",
                    files_processed=len(python_files),
                    message=f"Black {action} {len(python_files)} files ✓",
                    details=result.stdout,
                )
            return LintResult(
                success=False,
                tool="black",
                files_processed=len(python_files),
                message=f"Black failed on {len(python_files)} files",
                details=result.stderr,
            )

        except Exception as e:
            return LintResult(
                success=False,
                tool="black",
                files_processed=0,
                message=f"Black execution failed: {e}",
            )

    def sort_python_imports(self, files: list[Path], check_only: bool = False) -> LintResult:
        """Sort Python imports with isort.
        
        Args:
            files: List of Python files
            check_only: If True, only check without modifying
            
        Returns:
            LintResult
        """
        python_files = [f for f in files if f.suffix == ".py"]

        if not python_files:
            return LintResult(
                success=True,
                tool="isort",
                files_processed=0,
                message="No Python files to sort",
            )

        try:
            # Check if isort is installed
            subprocess.run(
                ["isort", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return LintResult(
                success=False,
                tool="isort",
                files_processed=0,
                message="isort not installed (install: pip install isort)",
            )

        try:
            cmd = ["isort"]
            if check_only:
                cmd.append("--check-only")
            cmd.extend([str(f) for f in python_files])

            result = subprocess.run(
                cmd,
                check=False, cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                action = "checked" if check_only else "sorted"
                return LintResult(
                    success=True,
                    tool="isort",
                    files_processed=len(python_files),
                    message=f"Isort {action} {len(python_files)} files ✓",
                    details=result.stdout,
                )
            return LintResult(
                success=False,
                tool="isort",
                files_processed=len(python_files),
                message=f"Isort found issues in {len(python_files)} files",
                details=result.stderr,
            )

        except Exception as e:
            return LintResult(
                success=False,
                tool="isort",
                files_processed=0,
                message=f"Isort execution failed: {e}",
            )

    def format_rust_files(self, files: list[Path]) -> LintResult:
        """Format Rust files with cargo fmt.
        
        Args:
            files: List of Rust files
            
        Returns:
            LintResult
        """
        rust_files = [f for f in files if f.suffix == ".rs"]

        if not rust_files:
            return LintResult(
                success=True,
                tool="cargo fmt",
                files_processed=0,
                message="No Rust files to format",
            )

        # Check for Cargo.toml
        if not (self.project_root / "Cargo.toml").exists():
            return LintResult(
                success=True,
                tool="cargo fmt",
                files_processed=0,
                message="No Cargo.toml found, skipping Rust formatting",
            )

        try:
            result = subprocess.run(
                ["cargo", "fmt", "--all"],
                check=False, cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return LintResult(
                    success=True,
                    tool="cargo fmt",
                    files_processed=len(rust_files),
                    message=f"Cargo fmt formatted {len(rust_files)} Rust files ✓",
                )
            return LintResult(
                success=False,
                tool="cargo fmt",
                files_processed=len(rust_files),
                message="Cargo fmt failed",
                details=result.stderr,
            )

        except FileNotFoundError:
            return LintResult(
                success=False,
                tool="cargo fmt",
                files_processed=0,
                message="cargo not found (install Rust toolchain)",
            )
        except Exception as e:
            return LintResult(
                success=False,
                tool="cargo fmt",
                files_processed=0,
                message=f"Cargo fmt execution failed: {e}",
            )

    def check_python_syntax(self, files: list[Path]) -> LintResult:
        """Basic Python syntax check (compilation test).
        
        Args:
            files: List of Python files
            
        Returns:
            LintResult
        """
        python_files = [f for f in files if f.suffix == ".py"]

        if not python_files:
            return LintResult(
                success=True,
                tool="py_compile",
                files_processed=0,
                message="No Python files to check",
            )

        errors = []
        for py_file in python_files:
            try:
                import py_compile
                py_compile.compile(str(py_file), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f"{py_file.name}: {e}")

        if errors:
            return LintResult(
                success=False,
                tool="py_compile",
                files_processed=len(python_files),
                message=f"Syntax errors in {len(errors)} files",
                details="\n".join(errors),
            )

        return LintResult(
            success=True,
            tool="py_compile",
            files_processed=len(python_files),
            message=f"Syntax check passed for {len(python_files)} files ✓",
        )

    def format_staged_files(self, files: list[Path]) -> list[LintResult]:
        """Format all staged files (Python + Rust).
        
        This is the main entry point for the commit workflow.
        
        Args:
            files: List of staged files
            
        Returns:
            List of LintResult objects
        """
        results = []

        # Python: isort first, then black
        results.append(self.sort_python_imports(files))
        results.append(self.format_python_files(files))

        # Rust: cargo fmt
        results.append(self.format_rust_files(files))

        # Log results
        for result in results:
            if result.files_processed > 0:
                if result.success:
                    self.logger.info(result.message)
                else:
                    self.logger.warning(result.message)
                    if result.details:
                        self.logger.debug(result.details)

        return results

    def pre_commit_check(self, files: list[Path]) -> tuple[bool, list[LintResult]]:
        """Run pre-commit checks (syntax validation).
        
        Args:
            files: List of files to check
            
        Returns:
            Tuple of (all_passed, results)
        """
        results = []

        # Syntax check
        syntax_result = self.check_python_syntax(files)
        results.append(syntax_result)

        all_passed = all(r.success for r in results)
        return all_passed, results
