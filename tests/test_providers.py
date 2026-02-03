"""Tests for DGT providers."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from dgt.core.config import DGTConfig, ProviderConfig
from dgt.providers.base import ProviderType, CheckResult
from dgt.providers.python import PythonProvider
from dgt.providers.rust import RustProvider
from dgt.providers.chrome import ChromeExtensionProvider


class TestPythonProvider:
    """Test cases for PythonProvider."""
    
    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration."""
        return DGTConfig(project_root=tmp_path)
    
    @pytest.fixture
    def provider_config(self):
        """Create test provider configuration."""
        return ProviderConfig(enabled=True)
    
    @pytest.fixture
    def python_provider(self, config, provider_config):
        """Create Python provider instance."""
        return PythonProvider(config, provider_config)
    
    def test_provider_type(self, python_provider):
        """Test provider type identification."""
        assert python_provider.provider_type == ProviderType.PYTHON
    
    def test_anchor_files(self, python_provider):
        """Test anchor file identification."""
        anchor_files = python_provider.anchor_files
        assert "requirements.txt" in anchor_files
        assert "pyproject.toml" in anchor_files
        assert "setup.py" in anchor_files
    
    def test_detect_project_with_requirements(self, python_provider, tmp_path):
        """Test project detection with requirements.txt."""
        (tmp_path / "requirements.txt").touch()
        assert python_provider.detect_project(tmp_path) is True
    
    def test_detect_project_with_pyproject(self, python_provider, tmp_path):
        """Test project detection with pyproject.toml."""
        (tmp_path / "pyproject.toml").touch()
        assert python_provider.detect_project(tmp_path) is True
    
    def test_detect_project_no_anchor(self, python_provider, tmp_path):
        """Test project detection with no anchor files."""
        assert python_provider.detect_project(tmp_path) is False
    
    @patch('subprocess.run')
    def test_validate_environment_success(self, mock_run, python_provider):
        """Test successful environment validation."""
        mock_run.return_value = Mock(stdout="Python 3.13.0", returncode=0)
        
        result = python_provider.validate_environment()
        
        assert result.success is True
        assert "Python version:" in result.message
    
    @patch('subprocess.run')
    def test_validate_environment_failure(self, mock_run, python_provider):
        """Test environment validation failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "python")
        
        result = python_provider.validate_environment()
        
        assert result.success is False
        assert "validation failed" in result.message.lower()


class TestRustProvider:
    """Test cases for RustProvider."""
    
    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration."""
        return DGTConfig(project_root=tmp_path)
    
    @pytest.fixture
    def provider_config(self):
        """Create test provider configuration."""
        return ProviderConfig(enabled=True)
    
    @pytest.fixture
    def rust_provider(self, config, provider_config):
        """Create Rust provider instance."""
        return RustProvider(config, provider_config)
    
    def test_provider_type(self, rust_provider):
        """Test provider type identification."""
        assert rust_provider.provider_type == ProviderType.RUST
    
    def test_anchor_files(self, rust_provider):
        """Test anchor file identification."""
        assert rust_provider.anchor_files == ["Cargo.toml"]
    
    def test_detect_project_with_cargo(self, rust_provider, tmp_path):
        """Test project detection with Cargo.toml."""
        (tmp_path / "Cargo.toml").touch()
        assert rust_provider.detect_project(tmp_path) is True
    
    def test_detect_project_no_cargo(self, rust_provider, tmp_path):
        """Test project detection without Cargo.toml."""
        assert rust_provider.detect_project(tmp_path) is False
    
    @patch('subprocess.run')
    def test_validate_environment_success(self, mock_run, rust_provider):
        """Test successful environment validation."""
        mock_run.side_effect = [
            Mock(stdout="rustc 1.75.0", returncode=0),
            Mock(stdout="cargo 1.75.0", returncode=0)
        ]
        
        result = rust_provider.validate_environment()
        
        assert result.success is True
        assert "validated successfully" in result.message.lower()


class TestChromeExtensionProvider:
    """Test cases for ChromeExtensionProvider."""
    
    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration."""
        return DGTConfig(project_root=tmp_path)
    
    @pytest.fixture
    def provider_config(self):
        """Create test provider configuration."""
        return ProviderConfig(enabled=True)
    
    @pytest.fixture
    def chrome_provider(self, config, provider_config):
        """Create Chrome extension provider instance."""
        return ChromeExtensionProvider(config, provider_config)
    
    def test_provider_type(self, chrome_provider):
        """Test provider type identification."""
        assert chrome_provider.provider_type == ProviderType.CHROME_EXTENSION
    
    def test_anchor_files(self, chrome_provider):
        """Test anchor file identification."""
        assert chrome_provider.anchor_files == ["manifest.json"]
    
    def test_detect_project_with_valid_manifest(self, chrome_provider, tmp_path):
        """Test project detection with valid manifest.json."""
        manifest = {
            "manifest_version": 3,
            "name": "Test Extension",
            "version": "1.0.0"
        }
        
        import json
        with (tmp_path / "manifest.json").open("w") as f:
            json.dump(manifest, f)
        
        assert chrome_provider.detect_project(tmp_path) is True
    
    def test_detect_project_with_invalid_manifest(self, chrome_provider, tmp_path):
        """Test project detection with invalid manifest.json."""
        (tmp_path / "manifest.json").write_text("invalid json")
        
        assert chrome_provider.detect_project(tmp_path) is False
    
    def test_detect_project_no_manifest(self, chrome_provider, tmp_path):
        """Test project detection without manifest.json."""
        assert chrome_provider.detect_project(tmp_path) is False
    
    def test_validate_manifest_success(self, chrome_provider, tmp_path):
        """Test successful manifest validation."""
        manifest = {
            "manifest_version": 3,
            "name": "Test Extension",
            "version": "1.0.0"
        }
        
        import json
        with (tmp_path / "manifest.json").open("w") as f:
            json.dump(manifest, f)
        
        result = chrome_provider._validate_manifest()
        
        assert result.success is True
        assert "validation passed" in result.message.lower()
    
    def test_validate_manifest_missing_fields(self, chrome_provider, tmp_path):
        """Test manifest validation with missing required fields."""
        manifest = {
            "name": "Test Extension"
            # Missing manifest_version and version
        }
        
        import json
        with (tmp_path / "manifest.json").open("w") as f:
            json.dump(manifest, f)
        
        result = chrome_provider._validate_manifest()
        
        assert result.success is False
        assert "missing required fields" in result.message.lower()
    
    def test_version_validation(self, chrome_provider):
        """Test version format validation."""
        assert chrome_provider._is_valid_version("1.0.0") is True
        assert chrome_provider._is_valid_version("1.0") is False
        assert chrome_provider._is_valid_version("1.0.0.0") is False
        assert chrome_provider._is_valid_version("invalid") is False
    
    def test_version_increment(self, chrome_provider):
        """Test version increment logic."""
        assert chrome_provider._increment_version("1.0.0") == "1.0.1"
        assert chrome_provider._increment_version("2.5.10") == "2.5.11"
        
        with pytest.raises(ValueError):
            chrome_provider._increment_version("invalid")
