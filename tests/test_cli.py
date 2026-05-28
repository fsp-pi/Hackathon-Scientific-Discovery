"""Tests for CLI commands."""

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from hackathon_science.cli import main
from hackathon_science.models import Paper


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_home(tmp_path):
    """Create a temporary home directory for credentials."""
    original_home = os.environ.get("HOME")
    os.environ["HOME"] = str(tmp_path)
    yield tmp_path
    if original_home:
        os.environ["HOME"] = original_home
    else:
        os.environ.pop("HOME", None)


def test_create_team_command_creates_workspace(runner, tmp_path, mocker):
    """Test create-team command creates the current paper-agent workspace."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["create-team", "alpha"])

        assert result.exit_code == 0
        assert "Creating local workspace for team alpha" in result.output
        team_dir = Path("agents") / "alpha"
        assert (team_dir / ".cache").exists()
        assert "alpha" in (team_dir / "my_run_agent.py").read_text()
        assert (team_dir / "config.toml").exists()


def test_create_team_command_skips_existing_files(runner, tmp_path, mocker):
    """Test create-team command skips files that already exist."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "run_agent_template.py").write_text("template")
    (templates_dir / "team_config_template.toml").write_text("template")

    mocker.patch(
        "hackathon_science.cli.Path",
        side_effect=lambda x: templates_dir if str(x).endswith("templates") else Path(x),
    )

    with runner.isolated_filesystem(temp_dir=tmp_path):
        team_dir = Path("agents") / "gamma"
        team_dir.mkdir(parents=True)
        (team_dir / "my_run_agent.py").write_text("existing")

        result = runner.invoke(main, ["create-team", "gamma"])

        assert result.exit_code == 0
        assert "already exists, skipping" in result.output
        assert (team_dir / "my_run_agent.py").read_text() == "existing"


def test_run_command_caches_paper_draft(runner, tmp_path, mocker):
    """Test run command executes an agent and saves a paper draft."""
    agent_dir = tmp_path / "agents" / "team1"
    agent_dir.mkdir(parents=True)
    agent_file = agent_dir / "test_agent.py"
    agent_file.write_text("def run(problem_domain, papers_dir): pass")

    mock_paper = Paper(
        title="Test Paper",
        introduction="Abstract",
        methods="Methods",
        results="Results",
        tags=["ai", "ml"],
    )
    mock_run_agent = mocker.patch("hackathon_science.cli.run_agent", return_value=mock_paper)
    mock_save_draft = mocker.patch("hackathon_science.cli.save_draft")

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["run", str(agent_file)])

    assert result.exit_code == 0
    assert "Paper draft cached with id" in result.output
    mock_run_agent.assert_called_once_with(agent_file, mocker.ANY, papers_dir=None)
    mock_save_draft.assert_called_once()
    saved_paper = mock_save_draft.call_args.args[2]
    assert saved_paper.author == "team1/test_agent"
    assert saved_paper.id


def test_run_command_rejects_agent_outside_agents_dir(runner, tmp_path):
    """Test run command rejects agent files outside agents/<team>/."""
    agent_file = tmp_path / "bad_location.py"
    agent_file.write_text("def run(problem_domain, papers_dir): pass")

    result = runner.invoke(main, ["run", str(agent_file)])

    assert result.exit_code != 0
    assert "Agent must live under agents/<team>/" in result.output


def test_publish_to_ecosystem_posts_matching_draft(runner, tmp_path, mocker):
    """`publish-to-ecosystem` finds a cached draft and posts it as a
    preprint, then prints a hint pointing users to `submit`."""
    draft = Paper(
        id="paper123",
        title="Title",
        introduction="Intro",
        methods="Methods",
        results="Results",
        author="team1/agent",
        tags=["tag"],
    )
    mocker.patch("hackathon_science.cli.load_draft", return_value=draft)
    mock_client = mocker.Mock()
    mock_client.me.return_value = {"email": "user@example.com", "team_id": "team1"}
    mock_client.publish_paper.return_value = {"id": "cloud123"}
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    with runner.isolated_filesystem(temp_dir=tmp_path):
        (Path("agents") / "team1" / ".cache").mkdir(parents=True)
        result = runner.invoke(main, ["publish-to-ecosystem", "paper123"])

    assert result.exit_code == 0
    assert "Published preprint cloud123" in result.output
    assert "uv run hackathon submit cloud123" in result.output
    mock_client.publish_paper.assert_called_once()
    assert mock_client.publish_paper.call_args.args[0]["author_agent"] == "agent"


def test_publish_to_ecosystem_rejects_wrong_team(runner, tmp_path, mocker):
    """Publish refuses drafts owned by a different signed-in team."""
    draft = Paper(
        id="paper123",
        title="Title",
        introduction="Intro",
        methods="Methods",
        results="Results",
    )
    mocker.patch("hackathon_science.cli.load_draft", return_value=draft)
    mock_client = mocker.Mock()
    mock_client.me.return_value = {"email": "user@example.com", "team_id": "other"}
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    with runner.isolated_filesystem(temp_dir=tmp_path):
        (Path("agents") / "team1" / ".cache").mkdir(parents=True)
        result = runner.invoke(main, ["publish-to-ecosystem", "paper123"])

    assert result.exit_code != 0
    assert "Draft is under agents/team1" in result.output
    mock_client.publish_paper.assert_not_called()


def test_submit_calls_client_and_prints_round(runner, mocker):
    """`submit` calls the cloud submit endpoint and reports the round."""
    mock_client = mocker.Mock()
    mock_client.submit_paper.return_value = {
        "id": "cloud123",
        "kind": "submitted",
        "submitted_round": 2,
    }
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["submit", "cloud123"])

    assert result.exit_code == 0
    assert "Submitted paper cloud123 for review in round 2" in result.output
    mock_client.submit_paper.assert_called_once_with("cloud123")


def test_submit_surfaces_server_error(runner, mocker):
    """Server errors (e.g. per-round cap) come back as a Click exception."""
    mock_client = mocker.Mock()
    mock_client.submit_paper.side_effect = RuntimeError(
        "409 team has already submitted 2 papers in round 2 (the per-round cap)"
    )
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["submit", "cloud123"])

    assert result.exit_code != 0
    assert "per-round cap" in result.output


def test_current_round_prints_round_team_and_cohort(runner, mocker):
    """`current-round` prints the round, your team's slot usage, and cohort total."""
    mock_client = mocker.Mock()
    mock_client.current_round.return_value = {
        "round": 2,
        "submissions_per_team_cap": 2,
    }
    mock_client.me.return_value = {"team_id": "alpha", "email": "a@b.c", "cognito_sub": "x"}
    # team submitted=1, team preprints=7, cohort submitted=14
    mock_client.count_papers.side_effect = [1, 7, 14]
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["current-round"])

    assert result.exit_code == 0, result.output
    assert "Round 2" in result.output
    assert "up to 2 papers" in result.output
    assert "Your team (alpha)" in result.output
    assert "1 / 2" in result.output
    assert "1 slot left" in result.output
    assert "Preprints this round:  7" in result.output
    assert "Cohort: 14 paper(s) submitted this round." in result.output
    assert "submit <paper_id>" in result.output


def test_current_round_cap_reached_hides_submit_hint(runner, mocker):
    """When the team is at cap, the submit hint is omitted and it says so."""
    mock_client = mocker.Mock()
    mock_client.current_round.return_value = {
        "round": 1,
        "submissions_per_team_cap": 2,
    }
    mock_client.me.return_value = {"team_id": "alpha", "email": "a@b.c", "cognito_sub": "x"}
    mock_client.count_papers.side_effect = [2, 3, 9]
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["current-round"])

    assert result.exit_code == 0, result.output
    assert "2 / 2" in result.output
    assert "cap reached" in result.output
    assert "submit <paper_id>" not in result.output


def test_activity_prints_rows(runner, mocker):
    """Test activity command prints cloud rows."""
    mock_client = mocker.Mock()
    mock_client.activity.return_value = [{"team_name": "alpha", "papers": 3}]
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["activity"])

    assert result.exit_code == 0
    assert "alpha" in result.output
    assert "3" in result.output


def test_list_papers_prints_published_papers(runner, mocker):
    """Test list-papers command prints papers from the cloud."""
    mock_client = mocker.Mock()
    mock_client.list_papers.return_value = [
        {
            "id": "abcdef123456",
            "title": "Paper A",
            "author_agent": "agent",
            "created_at": "2026-04-21",
            "tags": ["ai"],
        }
    ]
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["list-papers"])

    assert result.exit_code == 0
    assert "Paper A" in result.output
    assert "[abcdef12]" in result.output


def test_my_papers_lists_team_papers_with_links(runner, mocker):
    """`my-papers` lists the signed-in team's papers with web links."""
    mock_client = mocker.Mock()
    mock_client.me.return_value = {"email": "user@example.com", "team_id": "team1"}
    mock_client.list_papers.return_value = [
        {"id": "pp1", "title": "Paper A", "kind": "preprint"},
        {"id": "pp2", "title": "Paper B", "kind": "submitted"},
    ]
    mock_client.web_base.return_value = "https://flagship-hackathon.com"
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["my-papers"])

    assert result.exit_code == 0
    mock_client.list_papers.assert_called_once_with(team_id="team1")
    assert "team1 — 2 paper(s) (1 preprint, 1 submitted)" in result.output
    assert "Paper A" in result.output
    assert "Paper B" in result.output
    assert "https://flagship-hackathon.com/papers/pp1" in result.output
    assert "https://flagship-hackathon.com/papers/pp2" in result.output


def test_my_papers_empty_state_points_at_run(runner, mocker):
    """When the team has no papers, `my-papers` suggests running an agent."""
    mock_client = mocker.Mock()
    mock_client.me.return_value = {"email": "user@example.com", "team_id": "team1"}
    mock_client.list_papers.return_value = []
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["my-papers"])

    assert result.exit_code == 0
    assert "No papers published yet by team team1" in result.output
    assert "agents/team1/my_run_agent.py" in result.output


def test_show_paper_prints_full_details(runner, mocker):
    """Test show-paper command prints one paper."""
    mock_client = mocker.Mock()
    mock_client.get_paper.return_value = {
        "id": "paper123",
        "title": "Paper A",
        "author_agent": "agent",
        "created_at": "2026-04-21",
        "tags": ["ai"],
        "introduction": "Intro",
        "methods": "Methods",
        "results": "Results",
        "references": "Refs",
        "appendix": "Appendix",
    }
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["show-paper", "paper123"])

    assert result.exit_code == 0
    assert "Title: Paper A" in result.output
    assert "REFERENCES:" in result.output
    assert "APPENDIX:" in result.output


def test_download_papers_writes_markdown(runner, tmp_path, mocker):
    """Test download-papers writes markdown files."""
    mock_client = mocker.Mock()
    mock_client.list_papers.return_value = [
        {
            "id": "paper123",
            "title": "Paper A",
            "author_agent": "agent",
            "created_at": "2026-04-21",
            "tags": ["ai"],
            "introduction": "Intro",
            "methods": "Methods",
            "results": "Results",
        }
    ]
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    output_dir = tmp_path / "papers"
    result = runner.invoke(main, ["download-papers", "--output-dir", str(output_dir)])

    assert result.exit_code == 0
    assert (output_dir / "paper123.md").exists()
    assert "# Paper A" in (output_dir / "paper123.md").read_text()


def test_login_saves_credentials_and_verifies(runner, mocker):
    """Test login saves credentials and calls /me."""
    mock_save = mocker.patch("hackathon_science.cli.save_credentials")
    mock_client = mocker.Mock()
    mock_client.me.return_value = {"email": "user@example.com", "team_id": "team1"}
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["login", "--api-url", "https://api.example", "--api-key", "secret"])

    assert result.exit_code == 0
    mock_save.assert_called_once_with("https://api.example", "secret")
    assert "Signed in as user@example.com" in result.output


def test_whoami_prints_identity(runner, mocker):
    """Test whoami command prints current identity."""
    mock_client = mocker.Mock()
    mock_client.me.return_value = {"email": "user@example.com", "team_id": "team1"}
    mocker.patch("hackathon_science.cli.CloudClient", return_value=mock_client)

    result = runner.invoke(main, ["whoami"])

    assert result.exit_code == 0
    assert "user@example.com" in result.output
    assert "team1" in result.output
