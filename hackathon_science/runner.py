"""Agent execution and validation."""
import importlib.util
import sys
import warnings
from pathlib import Path
from typing import Optional
from hackathon_science.models import Paper
from hackathon_science.tools import _get_working_dir


def load_agent_module(agent_file: Path):
    """
    Load agent module from file path.

    Args:
        agent_file: Path to agent Python file

    Returns:
        Loaded module

    Raises:
        FileNotFoundError: If agent file doesn't exist
        ImportError: If module cannot be loaded
    """
    if not agent_file.exists():
        raise FileNotFoundError(f"Agent file not found: {agent_file}")

    spec = importlib.util.spec_from_file_location("agent_module", agent_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {agent_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_module"] = module
    spec.loader.exec_module(module)

    return module


def generate_appendix(working_dir: Optional[Path]) -> str:
    """
    Generate appendix content by reading script.py from working directory.

    Args:
        working_dir: Path to working directory containing script.py

    Returns:
        Formatted appendix content with code, or empty string if no working_dir

    Raises:
        UserWarning: If script.py not found in working directory
    """
    if working_dir is None:
        return ""

    script_path = Path(working_dir) / "script.py"

    if not script_path.exists():
        warnings.warn(
            "No code found. Paper likely to be reviewed poorly",
            UserWarning,
            stacklevel=2
        )
        return ""

    try:
        code_content = script_path.read_text()
        # Format as markdown code block
        appendix = f"# Code\n\n```python\n{code_content}\n```"
        return appendix
    except Exception as e:
        warnings.warn(
            f"Failed to read script.py: {e}. Paper likely to be reviewed poorly",
            UserWarning,
            stacklevel=2
        )
        return ""


def run_agent(
    agent_file: Path,
    problem_domain: str,
    papers_dir: Optional[Path] = None
) -> Paper:
    """
    Execute a run agent.

    Args:
        agent_file: Path to agent Python file
        problem_domain: Research problem domain
        papers_dir: Optional path to papers directory

    Returns:
        Generated Paper

    Raises:
        ValueError: If agent doesn't have run function or returns invalid paper
    """
    # Load agent module
    module = load_agent_module(agent_file)

    if not hasattr(module, "run"):
        raise ValueError(f"Agent {agent_file} does not have a 'run' function")

    # Call agent's run function
    paper = module.run(problem_domain, papers_dir)

    # Validate paper
    if not isinstance(paper, Paper):
        raise ValueError(f"Agent returned {type(paper)}, expected Paper")

    if not paper.title or not paper.introduction or not paper.methods or not paper.results:
        missing = []
        if not paper.title:
            missing.append("title")
        if not paper.introduction:
            missing.append("introduction")
        if not paper.methods:
            missing.append("methods")
        if not paper.results:
            missing.append("results")
        raise ValueError(f"Paper missing required fields: {', '.join(missing)}")

    # Auto-populate appendix if not already set
    if not paper.appendix:
        working_dir = _get_working_dir()
        paper.appendix = generate_appendix(working_dir)

    return paper


