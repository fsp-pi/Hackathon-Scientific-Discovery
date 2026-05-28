"""Tests for git operations."""

import pytest
from datetime import datetime
from unittest.mock import Mock
from git import Repo, GitCommandError

from hackathon_science.git_ops import (
    clone_repo,
    pull_latest,
    _generate_id,
    load_papers,
    publish_paper,
)
from hackathon_science.models import Paper


def test_clone_repo(tmp_path, mocker):
    """Test cloning repository."""
    mock_clone = mocker.patch("hackathon_science.git_ops.Repo.clone_from")

    url = "https://github.com/test/repo.git"
    local_path = tmp_path / "repo"

    clone_repo(url, local_path)

    mock_clone.assert_called_once_with(url, local_path)


def test_clone_repo_creates_parent(tmp_path, mocker):
    """Test cloning creates parent directories."""
    mock_clone = mocker.patch("hackathon_science.git_ops.Repo.clone_from")

    url = "https://github.com/test/repo.git"
    local_path = tmp_path / "nested" / "path" / "repo"

    clone_repo(url, local_path)

    assert local_path.parent.exists()
    mock_clone.assert_called_once_with(url, local_path)


def test_pull_latest(tmp_path, mocker):
    """Test pulling latest changes."""
    mock_repo = Mock(spec=Repo)
    mock_origin = Mock()
    mock_repo.remotes.origin = mock_origin

    mocker.patch("hackathon_science.git_ops.Repo", return_value=mock_repo)

    pull_latest(tmp_path)

    mock_origin.pull.assert_called_once()


def test_generate_id():
    """Test ID generation."""
    content = "test content"
    id1 = _generate_id(content)

    # Should be 8 characters
    assert len(id1) == 8

    # Should be hex
    assert all(c in "0123456789abcdef" for c in id1)

    # Should be deterministic
    id2 = _generate_id(content)
    assert id1 == id2

    # Different content should give different ID
    id3 = _generate_id("different content")
    assert id1 != id3


def test_load_papers_empty(tmp_path):
    """Test loading papers from empty directory."""
    papers = load_papers(tmp_path)
    assert papers == []


def test_load_papers_no_directory(tmp_path):
    """Test loading papers when directory doesn't exist."""
    papers = load_papers(tmp_path / "nonexistent")
    assert papers == []


def test_load_papers_single_paper(tmp_path):
    """Test loading a single paper."""
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()

    paper_content = """---
id: abc12345
title: Test Paper
author: team_alpha/my_run_agent
date: 2026-04-21
introduction: This is a test paper
tags: [test, demo]
---

## Methods

Test methods section.

## Results

Test results section.

"""

    paper_file = papers_dir / "abc12345.md"
    paper_file.write_text(paper_content)

    papers = load_papers(tmp_path)

    assert len(papers) == 1
    paper = papers[0]
    assert paper.id == "abc12345"
    assert paper.title == "Test Paper"
    assert paper.author == "team_alpha/my_run_agent"
    assert paper.date == "2026-04-21"
    assert paper.introduction == "This is a test paper"
    assert paper.tags == ["test", "demo"]
    assert paper.methods == "Test methods section."
    assert paper.results == "Test results section."


def test_load_papers_multiple(tmp_path):
    """Test loading multiple papers."""
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()

    for i in range(3):
        paper_content = f"""---
id: paper{i}
title: Paper {i}
author: team/agent
date: 2026-04-21
introduction: Abstract {i}
tags: []
---

## Methods

Methods {i}

## Results

Results {i}

"""
        paper_file = papers_dir / f"paper{i}.md"
        paper_file.write_text(paper_content)

    papers = load_papers(tmp_path)

    assert len(papers) == 3
    assert all(p.id in ["paper0", "paper1", "paper2"] for p in papers)


def test_load_papers_malformed_file(tmp_path):
    """Test loading papers with malformed file."""
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()

    # Valid paper
    valid_paper = """---
id: valid
title: Valid
author: team/agent
date: 2026-04-21
introduction: Valid
tags: []
---

## Methods

M

## Results

R

"""
    (papers_dir / "valid.md").write_text(valid_paper)

    # Malformed paper (no frontmatter)
    (papers_dir / "malformed.md").write_text("This is not valid markdown")

    papers = load_papers(tmp_path)

    # Should only load valid paper
    assert len(papers) == 1
    assert papers[0].id == "valid"


def test_publish_paper_success(tmp_path, mocker):
    """Test successfully publishing a paper."""
    # Setup
    mock_repo = Mock(spec=Repo)
    mock_index = Mock()
    mock_origin = Mock()
    mock_repo.index = mock_index
    mock_repo.remotes.origin = mock_origin
    mock_repo.active_branch.name = "team_alpha"

    mocker.patch("hackathon_science.git_ops.Repo", return_value=mock_repo)
    mocker.patch("hackathon_science.git_ops.load_papers", return_value=[])

    paper = Paper(
        title="Test Paper",
        introduction="Abstract",
        methods="Methods",
        results="Results",
        tags=["test"],
    )

    agent_file = tmp_path / "my_agent.py"
    agent_file.write_text("# agent code")

    # Execute
    paper_id = publish_paper(
        paper=paper,
        repo_path=tmp_path,
        team_name="team_alpha",
        agent_name="my_run_agent",
        agent_file_path=agent_file
    )

    # Verify
    assert len(paper_id) == 8
    assert paper.id == paper_id
    assert paper.author == "team_alpha/my_run_agent"
    assert paper.date == datetime.now().strftime("%Y-%m-%d")

    # Verify paper file was created
    paper_file = tmp_path / "papers" / f"{paper_id}.md"
    assert paper_file.exists()

    # Verify git operations
    mock_index.add.assert_called()
    mock_index.commit.assert_called_once()
    mock_origin.push.assert_called_once()


def test_publish_paper_missing_title(tmp_path, mocker):
    """Test publishing paper with missing title."""
    mocker.patch("hackathon_science.git_ops.load_papers", return_value=[])

    paper = Paper(
        title="",
        introduction="Abstract",
        methods="Methods",
        results="Results",
    )

    agent_file = tmp_path / "agent.py"
    agent_file.write_text("# code")

    with pytest.raises(ValueError, match="title"):
        publish_paper(paper, tmp_path, "team", "agent", agent_file)


def test_publish_paper_missing_abstract(tmp_path, mocker):
    """Test publishing paper with missing abstract."""
    mocker.patch("hackathon_science.git_ops.load_papers", return_value=[])

    paper = Paper(
        title="Title",
        introduction="",
        methods="Methods",
        results="Results",
    )

    agent_file = tmp_path / "agent.py"
    agent_file.write_text("# code")

    with pytest.raises(ValueError, match="introduction"):
        publish_paper(paper, tmp_path, "team", "agent", agent_file)


def test_publish_paper_missing_methods(tmp_path, mocker):
    """Test publishing paper with missing methods."""
    mocker.patch("hackathon_science.git_ops.load_papers", return_value=[])

    paper = Paper(
        title="Title",
        introduction="Abstract",
        methods="",
        results="Results",
    )

    agent_file = tmp_path / "agent.py"
    agent_file.write_text("# code")

    with pytest.raises(ValueError, match="methods"):
        publish_paper(paper, tmp_path, "team", "agent", agent_file)


def test_publish_paper_accepts_free_form_references(tmp_path, mocker):
    """Test publishing paper preserves free-form references."""
    mock_repo = Mock(spec=Repo)
    mock_index = Mock()
    mock_origin = Mock()
    mock_repo.index = mock_index
    mock_repo.remotes.origin = mock_origin
    mock_repo.active_branch.name = "team"

    mocker.patch("hackathon_science.git_ops.Repo", return_value=mock_repo)
    mocker.patch("hackathon_science.git_ops.load_papers", return_value=[])

    paper = Paper(
        title="Title",
        introduction="Abstract",
        methods="Methods",
        results="Results",
        references="This can cite non-local literature."
    )

    agent_file = tmp_path / "agent.py"
    agent_file.write_text("# code")

    paper_id = publish_paper(paper, tmp_path, "team", "agent", agent_file)

    paper_file = tmp_path / "papers" / f"{paper_id}.md"
    assert "## References" in paper_file.read_text()
    assert "This can cite non-local literature." in paper_file.read_text()


def test_publish_paper_valid_citations(tmp_path, mocker):
    """Test publishing paper with valid citations."""
    # Setup existing paper
    existing_paper = Paper(
        id="existing1",
        title="Existing",
        introduction="A",
        methods="M",
        results="R",
    )

    mock_repo = Mock(spec=Repo)
    mock_index = Mock()
    mock_origin = Mock()
    mock_repo.index = mock_index
    mock_repo.remotes.origin = mock_origin
    mock_repo.active_branch.name = "team"

    mocker.patch("hackathon_science.git_ops.Repo", return_value=mock_repo)
    mocker.patch("hackathon_science.git_ops.load_papers", return_value=[existing_paper])

    paper = Paper(
        title="Title",
        introduction="Abstract",
        methods="Methods",
        results="Results",
    )

    agent_file = tmp_path / "agent.py"
    agent_file.write_text("# code")

    # Should not raise
    paper_id = publish_paper(paper, tmp_path, "team", "agent", agent_file)
    assert paper_id is not None


def test_publish_paper_retry_on_conflict(tmp_path, mocker):
    """Test paper publish retries on git conflict."""
    mock_repo = Mock(spec=Repo)
    mock_index = Mock()
    mock_origin = Mock()
    mock_repo.index = mock_index
    mock_repo.remotes.origin = mock_origin
    mock_repo.active_branch.name = "team"

    # First push fails, second succeeds
    mock_origin.push.side_effect = [
        GitCommandError("push", 1, stderr="rejected"),
        None
    ]

    mocker.patch("hackathon_science.git_ops.Repo", return_value=mock_repo)
    mocker.patch("hackathon_science.git_ops.load_papers", return_value=[])

    paper = Paper(
        title="Title",
        introduction="Abstract",
        methods="Methods",
        results="Results",
    )

    agent_file = tmp_path / "agent.py"
    agent_file.write_text("# code")

    paper_id = publish_paper(paper, tmp_path, "team", "agent", agent_file, max_retries=3)

    assert paper_id is not None
    # Should have pulled on retry
    mock_origin.pull.assert_called()
    # Should have pushed twice
    assert mock_origin.push.call_count == 2


def test_publish_paper_max_retries_exceeded(tmp_path, mocker):
    """Test paper publish fails after max retries."""
    mock_repo = Mock(spec=Repo)
    mock_index = Mock()
    mock_origin = Mock()
    mock_repo.index = mock_index
    mock_repo.remotes.origin = mock_origin
    mock_repo.active_branch.name = "team"

    # All pushes fail
    mock_origin.push.side_effect = GitCommandError("push", 1, stderr="rejected")

    mocker.patch("hackathon_science.git_ops.Repo", return_value=mock_repo)
    mocker.patch("hackathon_science.git_ops.load_papers", return_value=[])

    paper = Paper(
        title="Title",
        introduction="Abstract",
        methods="Methods",
        results="Results",
    )

    agent_file = tmp_path / "agent.py"
    agent_file.write_text("# code")

    with pytest.raises(GitCommandError, match="Failed to publish paper after"):
        publish_paper(paper, tmp_path, "team", "agent", agent_file, max_retries=3)
