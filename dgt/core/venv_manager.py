"""Virtual Environment Manager - Universal venv discovery and management.

Extracted from TeleseroBalancer/main.py:62-195 with cross-platform support.
Provides zero-touch venv setup for Python projects.
"""

import os
import subprocess
import sys
from pathlib import Path

from loguru import logger
from pydantic import BaseModel


class VenvInfo(BaseModel):
    """Information about a detected virtual environment."""

    path: Path
    python_executable: Path
    version: str
    is_active: bool


class VenvManager:
    """Manages virtual environment detection, creation, and version validation.
    
    Key Features:
    - Cross-platform venv discovery (Windows Scripts/, Unix bin/)
    - Multi-name detection (.venv, venv, env, .env)
    - Python version validation
    - Auto-creation with version pinning
    - Subprocess relaunch pattern for seamless activation
    """

    # Common venv directory names, in priority order
    COMMON_VENV_NAMES = [".venv", "venv", "env", ".env"]

    def __init__(self, project_root: Path):
        """Initialize VenvManager for a project.
        
        Args:
            project_root: Project root directory to search for venvs
        """
        self.project_root = project_root
        self.logger = logger.bind(component="VenvManager")

    def find_venv(self) -> VenvInfo | None:
        """Find existing virtual environment in project.
        
        Searches for venv in priority order: .venv, venv, env, .env
        
        Returns:
            VenvInfo if found, None otherwise
        """
        for venv_name in self.COMMON_VENV_NAMES:
            venv_path = self.project_root / venv_name
            python_exe = self._get_venv_python_exe(venv_path)

            if python_exe.exists():
                # Get version
                try:
                    version = self._get_python_version(python_exe)
                    is_active = self._is_venv_active(venv_path)

                    self.logger.debug(f"Found venv: {venv_path} (Python {version}, active={is_active})")

                    return VenvInfo(
                        path=venv_path,
                        python_executable=python_exe,
                        version=version,
                        is_active=is_active,
                    )
                except Exception as e:
                    self.logger.warning(f"Invalid venv at {venv_path}: {e}")
                    continue

        return None

    def _get_venv_python_exe(self, venv_path: Path) -> Path:
        """Get path to Python executable in venv (cross-platform).
        
        Args:
            venv_path: Path to venv directory
            
        Returns:
            Path to python executable (may not exist)
        """
        if os.name == "nt":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"

    def _get_python_version(self, python_exe: Path) -> str:
        """Get Python version from executable.
        
        Args:
            python_exe: Path to Python executable
            
        Returns:
            Version string (e.g., "3.12.1")
        """
        result = subprocess.run(
            [str(python_exe), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
            check=False, capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()

    def _is_venv_active(self, venv_path: Path) -> bool:
        """Check if the venv is currently active.
        
        Args:
            venv_path: Path to venv directory
            
        Returns:
            True if this venv is active in current process
        """
        # Check if sys.prefix points to this venv
        return Path(sys.prefix) == venv_path.resolve()

    def verify_python_version(
        self,
        venv_info: VenvInfo,
        min_version: tuple[int, int],
    ) -> bool:
        """Verify that venv has minimum Python version.
        
        Args:
            venv_info: VenvInfo to check
            min_version: Minimum (major, minor) version required
            
        Returns:
            True if version meets requirement
        """
        parts = venv_info.version.split(".")
        major, minor = int(parts[0]), int(parts[1])

        return (major, minor) >= min_version

    def create_venv(
        self,
        python_version: str | None = None,
        venv_name: str = ".venv",
    ) -> VenvInfo:
        """Create new virtual environment.
        
        Args:
            python_version: Specific Python version to use (e.g., "3.12")
            venv_name: Name of venv directory (default: .venv)
            
        Returns:
            VenvInfo for created venv
            
        Raises:
            RuntimeError: If venv creation fails
        """
        venv_path = self.project_root / venv_name

        # Find Python executable
        if python_version:
            python_cmd = self._find_python_version(python_version)
        else:
            python_cmd = sys.executable

        self.logger.info(f"Creating venv at {venv_path} with {python_cmd}")

        # Create venv
        try:
            subprocess.run(
                [python_cmd, "-m", "venv", str(venv_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create venv: {e.stderr}")

        # Verify creation
        python_exe = self._get_venv_python_exe(venv_path)
        if not python_exe.exists():
            raise RuntimeError(f"Venv created but Python executable not found: {python_exe}")

        version = self._get_python_version(python_exe)

        self.logger.info(f"✅ Created venv: {venv_path} (Python {version})")

        return VenvInfo(
            path=venv_path,
            python_executable=python_exe,
            version=version,
            is_active=False,
        )

    def _find_python_version(self, target_version: str) -> str:
        """Find Python executable for specific version.
        
        Args:
            target_version: Version string (e.g., "3.12")
            
        Returns:
            Command to invoke Python (e.g., "py -3.12")
            
        Raises:
            RuntimeError: If version not found
        """
        # Windows: Try py launcher first
        if os.name == "nt":
            candidates = [
                f"py -{target_version}",
                f"python{target_version}",
                "python",
            ]
        else:
            candidates = [
                f"python{target_version}",
                f"python3.{target_version.split('.')[1]}",
                "python3",
                "python",
            ]

        for cmd in candidates:
            try:
                result = subprocess.run(
                    cmd.split() + ["-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                    check=False, capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip().startswith(target_version):
                    return cmd
            except Exception:
                continue

        raise RuntimeError(f"Python {target_version} not found")

    def install_dependencies(self, venv_info: VenvInfo) -> None:
        """Install project dependencies into venv.
        
        Args:
            venv_info: VenvInfo to install into
        """
        python_exe = venv_info.python_executable

        # Check for requirements.txt
        requirements_txt = self.project_root / "requirements.txt"
        if requirements_txt.exists():
            self.logger.info(f"Installing from {requirements_txt}")
            subprocess.run(
                [str(python_exe), "-m", "pip", "install", "-r", str(requirements_txt)],
                check=True,
            )
            return

        # Check for pyproject.toml
        pyproject_toml = self.project_root / "pyproject.toml"
        if pyproject_toml.exists():
            self.logger.info(f"Installing from {pyproject_toml} (editable)")
            subprocess.run(
                [str(python_exe), "-m", "pip", "install", "-e", str(self.project_root)],
                check=True,
            )
            return

        self.logger.warning("No dependency file found (requirements.txt or pyproject.toml)")

    def get_or_create_venv(
        self,
        min_version: tuple[int, int] = (3, 12),
        auto_create: bool = True,
    ) -> VenvInfo | None:
        """Get existing venv or create new one.
        
        Args:
            min_version: Minimum Python version required
            auto_create: Create venv if not found
            
        Returns:
            VenvInfo if found/created, None if not found and auto_create=False
        """
        # Try to find existing
        venv_info = self.find_venv()

        if venv_info:
            # Verify version
            if self.verify_python_version(venv_info, min_version):
                return venv_info
            self.logger.warning(
                f"Existing venv has Python {venv_info.version}, "
                f"but {min_version[0]}.{min_version[1]}+ required",
            )

        # Create new venv if allowed
        if auto_create:
            target_version = f"{min_version[0]}.{min_version[1]}"
            return self.create_venv(python_version=target_version)

        return None
