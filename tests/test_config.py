"""Tests for configuration loading and saving."""

import os
import tempfile
from pathlib import Path

import pytest

from hackathon_science.config import (
    expand_path,
    load_global_config,
    load_team_config,
    save_global_config,
    save_team_config,
)


class TestLoadGlobalConfig:
    """Tests for load_global_config function."""

    def test_load_global_config_returns_none_when_file_missing(self):
        """Test that load_global_config returns None when config file doesn't exist."""
        # Temporarily override the home directory to a non-existent path
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save original HOME
            original_home = os.environ.get("HOME")
            try:
                # Set HOME to temp directory (which won't have .hackathon-science/config.toml)
                os.environ["HOME"] = tmpdir
                result = load_global_config()
                assert result is None
            finally:
                # Restore original HOME
                if original_home:
                    os.environ["HOME"] = original_home
                else:
                    os.environ.pop("HOME", None)


class TestSaveGlobalConfig:
    """Tests for save_global_config function."""

    def test_save_global_config_creates_file_with_correct_content(self):
        """Test that save_global_config creates file with correct content and permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_home = os.environ.get("HOME")
            try:
                os.environ["HOME"] = tmpdir

                config_data = {"api_key": "test-key", "debug": True}
                save_global_config(config_data)

                # Check file exists
                config_path = Path(tmpdir) / ".hackathon-science" / "config.toml"
                assert config_path.exists()

                # Check permissions are 600
                stat_info = config_path.stat()
                # Extract permission bits (octal)
                perms = oct(stat_info.st_mode)[-3:]
                assert perms == "600", f"Expected permissions 600, got {perms}"

                # Check content
                loaded = load_global_config()
                assert loaded == config_data
            finally:
                if original_home:
                    os.environ["HOME"] = original_home
                else:
                    os.environ.pop("HOME", None)


class TestLoadTeamConfig:
    """Tests for load_team_config function."""

    def test_load_team_config_returns_none_when_file_missing(self):
        """Test that load_team_config returns None when config file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            team_dir = Path(tmpdir) / "team-001"
            team_dir.mkdir()

            result = load_team_config(team_dir)
            assert result is None

    def test_load_team_config_loads_existing_file(self):
        """Test that load_team_config loads existing config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            team_dir = Path(tmpdir) / "team-001"
            team_dir.mkdir()

            config_data = {"team_name": "Alpha", "members": 5}
            save_team_config(team_dir, config_data)

            result = load_team_config(team_dir)
            assert result == config_data


class TestSaveTeamConfig:
    """Tests for save_team_config function."""

    def test_save_team_config_creates_file(self):
        """Test that save_team_config creates config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            team_dir = Path(tmpdir) / "team-001"
            team_dir.mkdir()

            config_data = {"team_name": "Beta", "members": 3}
            save_team_config(team_dir, config_data)

            config_path = team_dir / "config.toml"
            assert config_path.exists()


class TestExpandPath:
    """Tests for expand_path function."""

    def test_expand_path_expands_home_directory(self):
        """Test that expand_path expands ~ to home directory."""
        result = expand_path("~/test/path")
        assert str(result).startswith(os.path.expanduser("~"))
        assert "test/path" in str(result)

    def test_expand_path_expands_environment_variables(self):
        """Test that expand_path expands environment variables."""
        os.environ["TEST_VAR"] = "/test/value"
        result = expand_path("$TEST_VAR/config")
        assert "/test/value/config" in str(result)

    def test_expand_path_returns_path_object(self):
        """Test that expand_path returns a Path object."""
        result = expand_path("~/test")
        assert isinstance(result, Path)

    def test_expand_path_handles_absolute_paths(self):
        """Test that expand_path handles absolute paths correctly."""
        result = expand_path("/absolute/path")
        assert result == Path("/absolute/path")
