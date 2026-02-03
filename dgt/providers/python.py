"""Python provider for DGT with venv, pytest, and linting support."""

import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

from .base import BaseProvider, CheckResult, ProviderType


class PythonProvider(BaseProvider):
    """Provider for Python projects with comprehensive development workflow."""
    
    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.PYTHON
    
    @property
    def anchor_files(self) -> List[str]:
        """Return list of anchor files that identify Python projects."""
        return [
            "requirements.txt",
            "pyproject.toml", 
            "setup.py",
            "Pipfile",
            "poetry.lock",
            "setup.cfg"
        ]
    
    def detect_project(self, project_root: Path) -> bool:
        """Detect if this is a Python project by checking for anchor files."""
        return any((project_root / anchor).exists() for anchor in self.anchor_files)
    
    def _validate_environment_impl(self) -> None:
        """Validate Python environment and required tools."""
        # Check Python version
        result = subprocess.run(
            ["python", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        version_str = result.stdout.strip()
        self.logger.info(f"Python version: {version_str}")
        
        # Check for required tools
        required_tools = ["pip"]
        for tool in required_tools:
            subprocess.run([tool, "--version"], capture_output=True, text=True, check=True)
    
    def run_pre_flight_checks(self, staged_files: List[Path]) -> List[CheckResult]:
        """Run Python-specific pre-flight checks."""
        results = []
        
        # Check if we're in a virtual environment
        results.append(self._check_virtual_environment())
        
        # Install dependencies if needed
        results.append(self._install_dependencies())
        
        # Run linting
        if self._should_run_linting(staged_files):
            results.extend(self._run_linting(staged_files))
        
        # Run tests
        if self._should_run_tests(staged_files):
            results.append(self._run_tests())
        
        # Type checking
        if self._should_run_type_checking(staged_files):
            results.append(self._run_type_checking())
        
        return results
    
    def run_post_flight_checks(self, commit_hash: str) -> List[CheckResult]:
        """Run Python-specific post-flight checks."""
        results = []
        
        # Run full test suite after commit
        results.append(self._run_full_test_suite())
        
        # Check for security vulnerabilities
        results.append(self._run_security_check())
        
        return results
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get Python-specific metadata for commit messages."""
        metadata = {}
        project_root = self.config.project_root
        
        # Try to get version from pyproject.toml
        pyproject_toml = project_root / "pyproject.toml"
        if pyproject_toml.exists():
            try:
                import tomllib
                with pyproject_toml.open("rb") as f:
                    data = tomllib.load(f)
                metadata["version"] = data.get("project", {}).get("version", "unknown")
            except Exception as e:
                self.logger.warning(f"Failed to read pyproject.toml: {e}")
        
        # Try to get Python version
        try:
            result = subprocess.run(
                ["python", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                capture_output=True,
                text=True,
                check=True
            )
            metadata["python_version"] = result.stdout.strip()
        except Exception as e:
            self.logger.warning(f"Failed to get Python version: {e}")
        
        return metadata
    
    def _check_virtual_environment(self) -> CheckResult:
        """Check if we're running in a virtual environment."""
        start_time = time.time()
        
        try:
            import sys
            has_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
            
            if has_venv:
                return CheckResult(
                    success=True,
                    message="Virtual environment detected",
                    execution_time=time.time() - start_time
                )
            else:
                return CheckResult(
                    success=False,
                    message="No virtual environment detected. Please activate a virtual environment.",
                    execution_time=time.time() - start_time
                )
        except Exception as e:
            return CheckResult(
                success=False,
                message=f"Failed to check virtual environment: {e}",
                execution_time=time.time() - start_time
            )
    
    def _install_dependencies(self) -> CheckResult:
        """Install project dependencies."""
        start_time = time.time()
        project_root = self.config.project_root
        
        try:
            # Check for different dependency files
            if (project_root / "requirements.txt").exists():
                subprocess.run(
                    ["pip", "install", "-r", "requirements.txt"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return CheckResult(
                    success=True,
                    message="Dependencies installed from requirements.txt",
                    execution_time=time.time() - start_time
                )
            
            elif (project_root / "pyproject.toml").exists():
                subprocess.run(
                    ["pip", "install", "-e", "."],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return CheckResult(
                    success=True,
                    message="Dependencies installed from pyproject.toml",
                    execution_time=time.time() - start_time
                )
            
            else:
                return CheckResult(
                    success=True,
                    message="No dependency file found, skipping installation",
                    execution_time=time.time() - start_time
                )
                
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Failed to install dependencies: {e.stderr}",
                execution_time=time.time() - start_time
            )
    
    def _should_run_linting(self, staged_files: List[Path]) -> bool:
        """Determine if linting should be run based on staged files."""
        python_files = [f for f in staged_files if f.suffix == ".py"]
        return len(python_files) > 0
    
    def _run_linting(self, staged_files: List[Path]) -> List[CheckResult]:
        """Run Python linting tools."""
        results = []
        python_files = [str(f) for f in staged_files if f.suffix == ".py"]
        
        if not python_files:
            return results
        
        # Try ruff first (fast)
        if self._tool_available("ruff"):
            results.append(self._run_ruff(python_files))
        
        # Try black for formatting
        elif self._tool_available("black"):
            results.append(self._run_black(python_files))
        
        # Fallback to flake8
        elif self._tool_available("flake8"):
            results.append(self._run_flake8(python_files))
        
        return results
    
    def _run_ruff(self, files: List[str]) -> CheckResult:
        """Run ruff linting."""
        start_time = time.time()
        
        try:
            result = subprocess.run(
                ["ruff", "check", "--fix"] + files,
                capture_output=True,
                text=True,
                check=True
            )
            return CheckResult(
                success=True,
                message=f"Ruff linting passed for {len(files)} files",
                details={"output": result.stdout},
                execution_time=time.time() - start_time
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Ruff linting failed: {e.stderr}",
                details={"output": e.stdout},
                execution_time=time.time() - start_time
            )
    
    def _run_black(self, files: List[str]) -> CheckResult:
        """Run black formatting check."""
        start_time = time.time()
        
        try:
            result = subprocess.run(
                ["black", "--check", "--diff"] + files,
                capture_output=True,
                text=True,
                check=True
            )
            return CheckResult(
                success=True,
                message=f"Black formatting check passed for {len(files)} files",
                execution_time=time.time() - start_time
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Black formatting check failed. Run 'black' to fix: {e.stderr}",
                details={"diff": e.stdout},
                execution_time=time.time() - start_time
            )
    
    def _run_flake8(self, files: List[str]) -> CheckResult:
        """Run flake8 linting."""
        start_time = time.time()
        
        try:
            result = subprocess.run(
                ["flake8"] + files,
                capture_output=True,
                text=True,
                check=True
            )
            return CheckResult(
                success=True,
                message=f"Flake8 linting passed for {len(files)} files",
                execution_time=time.time() - start_time
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Flake8 linting failed: {e.stderr}",
                execution_time=time.time() - start_time
            )
    
    def _should_run_tests(self, staged_files: List[Path]) -> bool:
        """Determine if tests should be run."""
        # Run tests if Python files are staged or if test files are staged
        python_files = [f for f in staged_files if f.suffix == ".py"]
        test_files = [f for f in staged_files if "test" in f.name.lower()]
        return len(python_files) > 0 or len(test_files) > 0
    
    def _run_tests(self) -> CheckResult:
        """Run pytest."""
        start_time = time.time()
        
        if not self._tool_available("pytest"):
            return CheckResult(
                success=True,
                message="pytest not available, skipping tests",
                execution_time=time.time() - start_time
            )
        
        try:
            result = subprocess.run(
                ["pytest", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                check=True
            )
            return CheckResult(
                success=True,
                message="pytest passed",
                details={"output": result.stdout},
                execution_time=time.time() - start_time
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"pytest failed: {e.stderr}",
                details={"output": e.stdout},
                execution_time=time.time() - start_time
            )
    
    def _should_run_type_checking(self, staged_files: List[Path]) -> bool:
        """Determine if type checking should be run."""
        # Run type checking if pyproject.toml has mypy configuration
        pyproject_toml = self.config.project_root / "pyproject.toml"
        if pyproject_toml.exists():
            try:
                import tomllib
                with pyproject_toml.open("rb") as f:
                    data = tomllib.load(f)
                return "mypy" in data.get("tool", {})
            except Exception:
                pass
        return False
    
    def _run_type_checking(self) -> CheckResult:
        """Run mypy type checking."""
        start_time = time.time()
        
        if not self._tool_available("mypy"):
            return CheckResult(
                success=True,
                message="mypy not available, skipping type checking",
                execution_time=time.time() - start_time
            )
        
        try:
            result = subprocess.run(
                ["mypy", "."],
                capture_output=True,
                text=True,
                check=True
            )
            return CheckResult(
                success=True,
                message="mypy type checking passed",
                execution_time=time.time() - start_time
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"mypy type checking failed: {e.stderr}",
                execution_time=time.time() - start_time
            )
    
    def _run_full_test_suite(self) -> CheckResult:
        """Run full test suite with coverage."""
        start_time = time.time()
        
        if not self._tool_available("pytest"):
            return CheckResult(
                success=True,
                message="pytest not available, skipping full test suite",
                execution_time=time.time() - start_time
            )
        
        try:
            cmd = ["pytest", "--cov=.", "--cov-report=term-missing"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return CheckResult(
                success=True,
                message="Full test suite with coverage passed",
                details={"output": result.stdout},
                execution_time=time.time() - start_time
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Full test suite failed: {e.stderr}",
                details={"output": e.stdout},
                execution_time=time.time() - start_time
            )
    
    def _run_security_check(self) -> CheckResult:
        """Run security vulnerability check."""
        start_time = time.time()
        
        if not self._tool_available("safety"):
            return CheckResult(
                success=True,
                message="safety not available, skipping security check",
                execution_time=time.time() - start_time
            )
        
        try:
            result = subprocess.run(
                ["safety", "check"],
                capture_output=True,
                text=True,
                check=True
            )
            return CheckResult(
                success=True,
                message="Security check passed",
                execution_time=time.time() - start_time
            )
        except subprocess.CalledProcessError as e:
            return CheckResult(
                success=False,
                message=f"Security vulnerabilities found: {e.stderr}",
                execution_time=time.time() - start_time
            )
    
    def _tool_available(self, tool: str) -> bool:
        """Check if a tool is available in the environment."""
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
