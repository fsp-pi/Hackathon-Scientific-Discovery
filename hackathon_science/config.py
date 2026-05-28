"""Configuration loading and saving for global and team configs."""

import os
import stat
from pathlib import Path
from typing import Optional

import toml


def expand_path(path: str) -> Path:
    """Expand ~ and environment variables in path.

    Args:
        path: Path string potentially containing ~ or environment variables

    Returns:
        Expanded Path object
    """
    expanded = os.path.expanduser(path)
    expanded = os.path.expandvars(expanded)
    return Path(expanded)


def load_global_config() -> Optional[dict]:
    """Load global configuration from ~/.hackathon-science/config.toml.

    Returns:
        Configuration dictionary if file exists, None otherwise
    """
    config_path = expand_path("~/.hackathon-science/config.toml")

    if not config_path.exists():
        return None

    try:
        with open(config_path, "r") as f:
            return toml.load(f)
    except Exception:
        return None


def save_global_config(config: dict) -> None:
    """Save global configuration to ~/.hackathon-science/config.toml with chmod 600.

    Args:
        config: Configuration dictionary to save
    """
    config_dir = expand_path("~/.hackathon-science")
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / "config.toml"

    with open(config_path, "w") as f:
        toml.dump(config, f)

    # Set permissions to 600 (read/write for owner only)
    config_path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_team_config(team_dir: Path) -> Optional[dict]:
    """Load team configuration from team_dir/config.toml.

    Args:
        team_dir: Path to team directory

    Returns:
        Configuration dictionary if file exists, None otherwise
    """
    config_path = team_dir / "config.toml"

    if not config_path.exists():
        return None

    try:
        with open(config_path, "r") as f:
            return toml.load(f)
    except Exception:
        return None


def save_team_config(team_dir: Path, config: dict) -> None:
    """Save team configuration to team_dir/config.toml.

    Args:
        team_dir: Path to team directory
        config: Configuration dictionary to save
    """
    config_path = team_dir / "config.toml"

    with open(config_path, "w") as f:
        toml.dump(config, f)
