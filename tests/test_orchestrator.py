"""Tests for DGT orchestrator."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from dgt.core.config import DGTConfig
from dgt.core.orchestrator import DGTOrchestrator
from dgt.providers.base import ProviderType, CheckResult


class TestDGTOrchestrator:
    """Test cases for DGTOrchestrator."""
    
    @pytest.fixture
    def config(self, tmp_path):
        """Create test configuration."""
        return DGTConfig(project_root=tmp_path)
    
    @pytest.fixture
    def mock_repo(self):
        """Create mock Git repository."""
        repo = Mock()
        repo.is_dirty.return_value = True
        repo.active_branch.name = "main"
        repo.index.diff.return_value = []
        repo.untracked_files.return_value = []
        repo.index.commit.return_value.hexsha = "abc123"
        repo.remote.return_value.push.return_value = None
        return repo
    
    @patch('git.Repo')
    def test_orchestrator_init_success(self, mock_git_repo, config, mock_repo):
        """Test successful orchestrator initialization."""
        mock_git_repo.return_value = mock_repo
        
        orchestrator = DGTOrchestrator(config)
        
        assert orchestrator.config == config
        assert orchestrator.repo == mock_repo
        assert isinstance(orchestrator.providers, dict)
    
    @patch('git.Repo')
    def test_orchestrator_init_no_git_repo(self, mock_git_repo, config):
        """Test orchestrator initialization with no Git repository."""
        from git import InvalidGitRepositoryError
        mock_git_repo.side_effect = InvalidGitRepositoryError()
        
        with pytest.raises(ValueError, match="Not a Git repository"):
            DGTOrchestrator(config)
    
    @patch('git.Repo')
    def test_get_git_status_dirty(self, mock_git_repo, config, mock_repo):
        """Test Git status for dirty repository."""
        mock_git_repo.return_value = mock_repo
        mock_repo.is_dirty.return_value = True
        mock_repo.index.diff.return_value = [Mock(a_path="file1.py")]
        mock_repo.untracked_files.return_value = ["file2.py"]
        mock_repo.index.diff.side_effect = [
            [Mock(a_path="file1.py")],  # staged files
            [Mock(a_path="file3.py")]   # changed files
        ]
        
        orchestrator = DGTOrchestrator(config)
        status = orchestrator.get_git_status()
        
        assert status["is_dirty"] is True
        assert status["has_staged_changes"] is True
        assert "file1.py" in status["staged_files"]
        assert "file2.py" in status["untracked_files"]
    
    @patch('git.Repo')
    def test_get_git_status_clean(self, mock_git_repo, config, mock_repo):
        """Test Git status for clean repository."""
        mock_git_repo.return_value = mock_repo
        mock_repo.is_dirty.return_value = False
        
        orchestrator = DGTOrchestrator(config)
        status = orchestrator.get_git_status()
        
        assert status["is_dirty"] is False
        assert status["has_staged_changes"] is False
    
    @patch('git.Repo')
    def test_run_commit_workflow_success(self, mock_git_repo, config, mock_repo):
        """Test successful commit workflow."""
        mock_git_repo.return_value = mock_repo
        mock_repo.is_dirty.return_value = True
        mock_repo.index.diff.side_effect = [
            [Mock(a_path="file1.py")],  # staged files
            []  # HEAD diff
        ]
        mock_repo.untracked_files.return_value = []
        
        # Mock active provider
        with patch.object(DGTOrchestrator, '_detect_active_provider') as mock_detect:
            mock_provider = Mock()
            mock_provider.validate_environment.return_value = CheckResult(success=True, message="OK")
            mock_provider.run_pre_flight_checks.return_value = [CheckResult(success=True, message="OK")]
            mock_provider.format_commit_message.return_value="[Python] test message"
            mock_provider.run_post_flight_checks.return_value = [CheckResult(success=True, message="OK")]
            mock_detect.return_value = mock_provider
            
            orchestrator = DGTOrchestrator(config)
            result = orchestrator.run_commit_workflow("test message")
            
            assert result["success"] is True
            assert result["commit_hash"] == "abc123"
            assert len(result["pre_flight_results"]) == 1
            assert len(result["post_flight_results"]) == 1
    
    @patch('git.Repo')
    def test_run_commit_workflow_no_staged_files(self, mock_git_repo, config, mock_repo):
        """Test commit workflow with no staged files."""
        mock_git_repo.return_value = mock_repo
        mock_repo.is_dirty.return_value = False
        mock_repo.index.diff.return_value = []
        mock_repo.untracked_files.return_value = []
        
        with patch.object(DGTOrchestrator, '_detect_active_provider') as mock_detect:
            mock_provider = Mock()
            mock_provider.validate_environment.return_value = CheckResult(success=True, message="OK")
            mock_detect.return_value = mock_provider
            
            orchestrator = DGTOrchestrator(config)
            result = orchestrator.run_commit_workflow("test message")
            
            assert result["success"] is False
            assert "No staged changes" in result["message"]
    
    @patch('git.Repo')
    def test_run_commit_workflow_pre_flight_failure(self, mock_git_repo, config, mock_repo):
        """Test commit workflow with pre-flight check failure."""
        mock_git_repo.return_value = mock_repo
        mock_repo.is_dirty.return_value = True
        mock_repo.index.diff.return_value = [Mock(a_path="file1.py")]
        mock_repo.untracked_files.return_value = []
        
        with patch.object(DGTOrchestrator, '_detect_active_provider') as mock_detect:
            mock_provider = Mock()
            mock_provider.validate_environment.return_value = CheckResult(success=True, message="OK")
            mock_provider.run_pre_flight_checks.return_value = [
                CheckResult(success=False, message="Test failed")
            ]
            mock_detect.return_value = mock_provider
            
            orchestrator = DGTOrchestrator(config)
            result = orchestrator.run_commit_workflow("test message")
            
            assert result["success"] is False
            assert "Pre-flight checks failed" in result["message"]
    
    @patch('git.Repo')
    def test_run_dry_run_success(self, mock_git_repo, config, mock_repo):
        """Test successful dry run."""
        mock_git_repo.return_value = mock_repo
        mock_repo.is_dirty.return_value = True
        mock_repo.index.diff.return_value = [Mock(a_path="file1.py")]
        mock_repo.untracked_files.return_value = ["file2.py"]
        
        with patch.object(DGTOrchestrator, '_detect_active_provider') as mock_detect:
            mock_provider = Mock()
            mock_provider.format_commit_message.return_value="[Python] test message"
            mock_provider.run_pre_flight_checks.return_value = [CheckResult(success=True, message="OK")]
            mock_detect.return_value = mock_provider
            
            orchestrator = DGTOrchestrator(config)
            result = orchestrator.run_dry_run("test message")
            
            assert result["success"] is True
            assert result["formatted_commit_message"] == "[Python] test message"
            assert "file1.py" in result["would_commit_files"]
            assert "file2.py" in result["would_commit_files"]
            assert len(result["pre_flight_results"]) == 1
    
    @patch('git.Repo')
    def test_get_project_info(self, mock_git_repo, config, mock_repo):
        """Test project information retrieval."""
        mock_git_repo.return_value = mock_repo
        mock_repo.is_dirty.return_value = False
        
        with patch.object(DGTOrchestrator, '_detect_active_provider') as mock_detect:
            mock_provider = Mock()
            mock_provider.provider_type.value = "python"
            mock_provider.get_metadata.return_value = {"version": "1.0.0"}
            mock_detect.return_value = mock_provider
            
            orchestrator = DGTOrchestrator(config)
            info = orchestrator.get_project_info()
            
            assert info["project_root"] == str(config.project_root)
            assert info["active_provider"] == "python"
            assert "git_status" in info
            assert "available_providers" in info
            assert "config" in info
            assert info["provider_metadata"]["version"] == "1.0.0"
