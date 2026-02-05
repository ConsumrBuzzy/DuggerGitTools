"""Rust Toolchain Manager - Universal Rust/WASM build environment configuration.

Extracted from SolanaShredder/build_rust.py:79-266 with Windows dev environment focus.
Handles rustup conflicts, OpenSSL detection, and WASM target validation.
"""

import os
import shutil
import subprocess
from pathlib import Path

from loguru import logger
from pydantic import BaseModel


class OpenSSLInfo(BaseModel):
    """OpenSSL installation information."""

    openssl_dir: Path
    lib_dir: Path
    include_dir: Path
    is_system: bool  # False if vendored build required


class RustToolchainInfo(BaseModel):
    """Rust toolchain information."""

    rustc_path: Path
    rustup_path: Path | None
    host_target: str
    has_conflict: bool  # True if Chocolatey rustc detected
    installed_targets: list[str]


class RustToolchain:
    """Manages Rust toolchain validation and build environment setup.
    
    Key Features:
    - Detects Chocolatey vs rustup-managed rustc conflicts
    - Smart OpenSSL linking (system vs vendored)
    - WASM target detection via Cargo.toml parsing
    - Auto-configures build environment variables
    """

    PREFERRED_TARGET = "x86_64-pc-windows-msvc"

    def __init__(self, project_root: Path):
        """Initialize RustToolchain manager.
        
        Args:
            project_root: Rust project root (contains Cargo.toml)
        """
        self.project_root = project_root
        self.logger = logger.bind(component="RustToolchain")

    def find_rustup(self) -> Path | None:
        """Locate rustup executable.
        
        Returns:
            Path to rustup if found, None otherwise
        """
        rustup_path = shutil.which("rustup")
        if rustup_path:
            return Path(rustup_path)

        # Check standard location
        cargo_bin = Path.home() / ".cargo" / "bin"
        rustup_exe = cargo_bin / ("rustup.exe" if os.name == "nt" else "rustup")
        if rustup_exe.exists():
            return rustup_exe

        return None

    def get_rustc_info(self) -> tuple[Path | None, str | None]:
        """Get rustc path and host target.
        
        Returns:
            (rustc_path, host_target) tuple
        """
        rustc_path = shutil.which("rustc")
        if not rustc_path:
            return None, None

        rustc_path = Path(rustc_path)

        try:
            result = subprocess.run(
                [str(rustc_path), "-vV"],
                check=False, capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.splitlines():
                if line.startswith("host:"):
                    return rustc_path, line.split(":", 1)[1].strip()
        except Exception as e:
            self.logger.warning(f"Failed to get rustc info: {e}")

        return rustc_path, None

    def verify_toolchain(self) -> tuple[bool, str, RustToolchainInfo | None]:
        """Verify Rust toolchain configuration.
        
        Returns:
            (is_ok, message, toolchain_info) tuple
        """
        rustup = self.find_rustup()
        if not rustup:
            return False, "❌ Rustup not found. Install from https://rustup.rs", None

        rustc_path, host_target = self.get_rustc_info()
        if not rustc_path:
            return False, "❌ rustc not found in PATH", None

        # Check for Chocolatey conflict
        cargo_bin = Path.home() / ".cargo" / "bin"
        choco_bin = Path("C:/ProgramData/chocolatey/bin")
        rustc_parent = rustc_path.parent

        has_conflict = False
        if rustc_parent == choco_bin:
            has_conflict = True
            message = (
                f"⚠️  CONFLICT: rustc is from Chocolatey, not rustup!\n"
                f"   Path: {rustc_path}\n"
                f"   Fix: Run 'choco uninstall rust -y' or reorder PATH\n"
                f"   Ensure {cargo_bin} comes BEFORE {choco_bin}"
            )
            return False, message, None

        # Get installed targets
        installed_targets = self._get_installed_targets(rustup)

        toolchain_info = RustToolchainInfo(
            rustc_path=rustc_path,
            rustup_path=rustup,
            host_target=host_target or "unknown",
            has_conflict=has_conflict,
            installed_targets=installed_targets,
        )

        # Check if using preferred target
        if host_target and host_target != self.PREFERRED_TARGET:
            message = (
                f"⚠️  Rust host is {host_target} (prefer {self.PREFERRED_TARGET})\n"
                f"   May require vendored OpenSSL (slower build)"
            )
            return True, message, toolchain_info

        return True, f"✅ Rust toolchain: {host_target} at {rustc_path}", toolchain_info

    def _get_installed_targets(self, rustup: Path) -> list[str]:
        """Get list of installed Rust targets.
        
        Args:
            rustup: Path to rustup executable
            
        Returns:
            List of target triple strings
        """
        try:
            result = subprocess.run(
                [str(rustup), "target", "list", "--installed"],
                check=False, capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip().splitlines()
        except Exception:
            return []

    def detect_cargo_targets(self) -> dict[str, bool]:
        """Detect target types from Cargo.toml.
        
        Returns:
            Dict with keys: bin, lib, cdylib, wasm
        """
        cargo_toml = self.project_root / "Cargo.toml"
        if not cargo_toml.exists():
            return {"bin": False, "lib": False, "cdylib": False, "wasm": False}

        try:
            import tomllib
            with cargo_toml.open("rb") as f:
                data = tomllib.load(f)

            targets = {
                "bin": "bin" in data or any("bin" in d for d in data.get("dependencies", {}).values() if isinstance(d, dict)),
                "lib": "lib" in data,
                "cdylib": False,
                "wasm": False,
            }

            # Check for cdylib/wasm in lib section
            if "lib" in data:
                lib_config = data["lib"]
                if isinstance(lib_config, dict):
                    crate_type = lib_config.get("crate-type", [])
                    if isinstance(crate_type, str):
                        crate_type = [crate_type]
                    targets["cdylib"] = "cdylib" in crate_type
                    # WASM targets typically use cdylib
                    targets["wasm"] = "cdylib" in crate_type or "wasm" in str(data).lower()

            return targets

        except Exception as e:
            self.logger.warning(f"Failed to parse Cargo.toml: {e}")
            return {"bin": False, "lib": False, "cdylib": False, "wasm": False}

    def find_openssl(self) -> OpenSSLInfo | None:
        """Find system OpenSSL installation.
        
        Returns:
            OpenSSLInfo if found, None if vendored build required
        """
        # Check OPENSSL_DIR environment variable
        openssl_dir_env = os.environ.get("OPENSSL_DIR")
        if openssl_dir_env:
            openssl_path = Path(openssl_dir_env)
            lib_dir = self._detect_openssl_lib_dir(openssl_path)
            if lib_dir:
                return OpenSSLInfo(
                    openssl_dir=openssl_path,
                    lib_dir=lib_dir,
                    include_dir=openssl_path / "include",
                    is_system=True,
                )

        # Check common Windows paths
        common_paths = [
            Path("C:/Program Files/OpenSSL-Win64"),
            Path("C:/Program Files/OpenSSL"),
            Path("C:/OpenSSL-Win64"),
            Path("C:/OpenSSL"),
            Path("C:/Strawberry/c"),  # Strawberry Perl includes OpenSSL
        ]

        for openssl_path in common_paths:
            if openssl_path.exists():
                lib_dir = self._detect_openssl_lib_dir(openssl_path)
                if lib_dir:
                    self.logger.info(f"✅ Found OpenSSL at {openssl_path}")
                    return OpenSSLInfo(
                        openssl_dir=openssl_path,
                        lib_dir=lib_dir,
                        include_dir=openssl_path / "include",
                        is_system=True,
                    )

        return None

    def _detect_openssl_lib_dir(self, openssl_path: Path) -> Path | None:
        """Detect correct lib subdirectory for OpenSSL.
        
        Args:
            openssl_path: OpenSSL installation root
            
        Returns:
            Path to lib directory with .lib files
        """
        # slproweb.com MSVC layout
        vc_lib = openssl_path / "lib" / "VC" / "x64" / "MD"
        if vc_lib.exists() and (vc_lib / "libssl.lib").exists():
            self.logger.debug(f"Using MSVC libs: {vc_lib}")
            return vc_lib

        # Strawberry Perl layout
        strawberry_lib = openssl_path / "lib"
        if strawberry_lib.exists():
            if (strawberry_lib / "libssl.a").exists() or (strawberry_lib / "ssl.lib").exists():
                self.logger.debug(f"Using libs: {strawberry_lib}")
                return strawberry_lib

        # Standard layout
        if (openssl_path / "lib").exists():
            return openssl_path / "lib"

        return None

    def setup_build_env(
        self,
        prefer_system_openssl: bool = True,
    ) -> dict[str, str]:
        """Configure environment variables for Rust build.
        
        Args:
            prefer_system_openssl: Use system OpenSSL if available
            
        Returns:
            Environment variable dict to merge with os.environ
        """
        env = {}

        # Force rustup to use MSVC toolchain if available
        rustup = self.find_rustup()
        if rustup:
            try:
                result = subprocess.run(
                    [str(rustup), "toolchain", "list"],
                    check=False, capture_output=True,
                    text=True,
                    timeout=10,
                )
                if f"stable-{self.PREFERRED_TARGET}" in result.stdout:
                    env["RUSTUP_TOOLCHAIN"] = f"stable-{self.PREFERRED_TARGET}"
                    self.logger.info(f"📌 Forcing toolchain: stable-{self.PREFERRED_TARGET}")
            except Exception:
                pass

        # Ensure cargo bin is in PATH
        cargo_bin = Path.home() / ".cargo" / "bin"
        if cargo_bin.exists():
            env["PATH"] = str(cargo_bin) + os.pathsep + os.environ.get("PATH", "")

        # Setup OpenSSL
        if prefer_system_openssl:
            openssl_info = self.find_openssl()
            if openssl_info:
                env["OPENSSL_DIR"] = str(openssl_info.openssl_dir)
                env["OPENSSL_LIB_DIR"] = str(openssl_info.lib_dir)
                env["OPENSSL_INCLUDE_DIR"] = str(openssl_info.include_dir)
                env["OPENSSL_NO_VENDOR"] = "1"
                self.logger.info("🔗 Using system OpenSSL (NO_VENDOR=1)")
            else:
                self.logger.warning("⚠️  No system OpenSSL - will use vendored build (slow)")

        return env

    def get_build_features(self) -> list[str]:
        """Get Cargo features needed for build.
        
        Returns:
            List of feature flags for --features
        """
        features = []

        # Check if vendored OpenSSL needed
        openssl_info = self.find_openssl()
        if not openssl_info:
            features.append("openssl-vendored")
            self.logger.info("Adding feature: openssl-vendored")

        return features
