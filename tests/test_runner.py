"""Tests for agent runner."""

import pytest

from hackathon_science.models import Paper
from hackathon_science.runner import generate_appendix, load_agent_module, run_agent


def test_load_agent_module(tmp_path):
    """Test loading agent module from file."""
    agent_file = tmp_path / "test_agent.py"
    agent_file.write_text("""
def run(problem_domain, papers_dir):
    from hackathon_science.models import Paper
    return Paper(
        title="Test",
        introduction="A",
        methods="M",
        results="R",
    )
""")

    module = load_agent_module(agent_file)

    assert hasattr(module, "run")
    result = module.run("domain", None)
    assert result.title == "Test"


def test_load_agent_module_missing_file(tmp_path):
    """Test loading agent module with missing file."""
    with pytest.raises(FileNotFoundError, match="Agent file not found"):
        load_agent_module(tmp_path / "missing.py")


def test_run_agent(tmp_path):
    """Test running a paper-generation agent."""
    agent_file = tmp_path / "run_agent.py"
    agent_file.write_text("""
from hackathon_science.models import Paper

def run(problem_domain, papers_dir):
    assert problem_domain == "Test domain"
    assert papers_dir is None
    return Paper(
        title="Generated Paper",
        introduction="Abstract",
        methods="Methods",
        results="Results",
    )
""")

    paper = run_agent(agent_file, "Test domain")

    assert paper.title == "Generated Paper"
    assert paper.introduction == "Abstract"


def test_run_agent_passes_papers_dir(tmp_path):
    """Test passing a local papers directory through to the agent."""
    papers_dir = tmp_path / "papers"
    agent_file = tmp_path / "run_agent.py"
    agent_file.write_text("""
from hackathon_science.models import Paper

def run(problem_domain, papers_dir):
    return Paper(
        title=str(papers_dir.name),
        introduction="Abstract",
        methods="Methods",
        results="Results",
    )
""")

    paper = run_agent(agent_file, "Test domain", papers_dir=papers_dir)

    assert paper.title == "papers"


def test_run_agent_no_run_function(tmp_path):
    """Test running agent without run function."""
    agent_file = tmp_path / "bad_agent.py"
    agent_file.write_text("def wrong_function(): pass")

    with pytest.raises(ValueError, match="does not have a 'run' function"):
        run_agent(agent_file, "Test domain")


def test_run_agent_invalid_return_type(tmp_path):
    """Test running agent that returns invalid type."""
    agent_file = tmp_path / "bad_agent.py"
    agent_file.write_text("""
def run(problem_domain, papers_dir):
    return "not a paper"
""")

    with pytest.raises(ValueError, match="expected Paper"):
        run_agent(agent_file, "Test domain")


def test_run_agent_missing_fields(tmp_path):
    """Test running agent that returns paper with missing fields."""
    agent_file = tmp_path / "bad_agent.py"
    agent_file.write_text("""
from hackathon_science.models import Paper

def run(problem_domain, papers_dir):
    return Paper(
        title="Title",
        introduction="",
        methods="Methods",
        results="Results",
    )
""")

    with pytest.raises(ValueError, match="Paper missing required fields"):
        run_agent(agent_file, "Test domain")


def test_generate_appendix_reads_script(tmp_path):
    """Test appendix generation from a working directory script."""
    (tmp_path / "script.py").write_text("print('hello')")

    appendix = generate_appendix(tmp_path)

    assert "# Code" in appendix
    assert "print('hello')" in appendix


def test_generate_appendix_missing_script_warns(tmp_path):
    """Test missing script.py returns an empty appendix with warning."""
    with pytest.warns(UserWarning, match="No code found"):
        assert generate_appendix(tmp_path) == ""
