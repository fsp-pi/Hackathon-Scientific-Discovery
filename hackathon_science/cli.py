"""CLI commands for hackathon-science.

In the Path-B cloud architecture, the CLI no longer touches git for sharing
work. `uv run hackathon run` generates drafts locally,
`uv run hackathon publish-to-ecosystem` POSTs them to the cloud as
preprints (capped at 1000 per team per round), and `uv run hackathon submit`
promotes a preprint into the current round's 2-per-team review slate.

Auth: `uv run hackathon login --api-key KEY` writes credentials to
~/.hackathon-science/credentials (chmod 600). Subsequent commands read it.
Pass `--api-url` to override the default cloud URL.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import click

from hackathon_science.cache import load_draft, save_draft
from hackathon_science.cloud_client import (
    DEFAULT_API_URL,
    CloudClient,
    NotLoggedInError,
    load_credentials,
    save_credentials,
)
from hackathon_science.models import Paper
from hackathon_science.runner import run_agent

PROBLEM_DOMAIN_DEFAULT = (
    "Agentic design and algorithms for scientific hypothesis generation / falsification"
)


def _short_id(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:8]


def _resolve_team(agent_path: Path) -> str:
    """Pull team name from agents/<team>/<file>.py. Errors if not in that
    layout — the rest of the CLI expects this convention."""
    parts = agent_path.parts
    if "agents" not in parts:
        raise click.ClickException("Agent must live under agents/<team>/")
    idx = parts.index("agents")
    if len(parts) <= idx + 1:
        raise click.ClickException(
            "Cannot determine team name from agent path; expected agents/<team>/<file>.py"
        )
    return parts[idx + 1]


@click.group()
def main() -> None:
    """Hackathon Scientific Discovery Platform CLI."""


# --- Account ---


@main.command()
@click.option(
    "--api-url",
    default=DEFAULT_API_URL,
    show_default=True,
    help="Base URL of the cloud API. Override only if you're running against a custom deployment.",
)
@click.option("--api-key", required=True, help="API key minted in the web Settings page")
def login(api_url: str, api_key: str) -> None:
    """Save cloud API credentials to ~/.hackathon-science/credentials."""
    if not api_url.startswith(("http://", "https://")):
        raise click.ClickException(
            f"--api-url must include a scheme (e.g. {DEFAULT_API_URL}); got {api_url!r}."
        )
    save_credentials(api_url, api_key)
    # Verify the credentials immediately so the user gets a fast failure
    # rather than seeing it on the next publish.
    try:
        me = CloudClient().me()
    except Exception as e:
        raise click.ClickException(
            f"Saved credentials, but /me failed: {e}.\n"
            "Run `uv run hackathon login` again with corrected values."
        )
    click.echo(f"Signed in as {me['email']} on team {me['team_id']}.")


@main.command()
def whoami() -> None:
    """Show who the CLI is signed in as."""
    try:
        me = CloudClient().me()
    except NotLoggedInError as e:
        raise click.ClickException(str(e))
    click.echo(f"{me['email']} — team {me['team_id']}")


# --- Team workspace scaffolding ---


@main.command()
@click.argument("team_name")
def create_team(team_name: str) -> None:
    """Scaffold a local team workspace with run agent template.

    The team itself is created in the cloud at sign-up (via the SPA);
    this command only sets up local files. If the local team name doesn't
    match the one you registered with, your publishes will be rejected.
    """
    click.echo(f"Creating local workspace for team {team_name}…")
    team_dir = Path("agents") / team_name
    team_dir.mkdir(parents=True, exist_ok=True)
    (team_dir / ".cache").mkdir(exist_ok=True)

    templates_dir = Path(__file__).parent / "templates"

    def _scaffold(template_name: str, dest_name: str) -> None:
        dest = team_dir / dest_name
        if dest.exists():
            click.echo(f"  {dest} already exists, skipping")
            return
        content = (templates_dir / template_name).read_text().replace("{team_name}", team_name)
        dest.write_text(content)
        click.echo(f"  created {dest}")

    _scaffold("run_agent_template.py", "my_run_agent.py")
    _scaffold("team_config_template.toml", "config.toml")

    click.echo(
        "\nDone. Next:\n"
        f"  1. Edit {team_dir / 'my_run_agent.py'} to implement your run agent\n"
        f"  2. uv run hackathon run {team_dir / 'my_run_agent.py'}\n"
        f"  3. uv run hackathon publish-to-ecosystem <id>   # <id> from step 2\n"
        f"  4. uv run hackathon submit <paper_id>           # up to 2 per round"
    )


# --- Agent execution (draft only — no network calls) ---


@main.command()
@click.argument("agent_file", type=click.Path(exists=True, path_type=Path))
@click.option("--problem-domain", default=PROBLEM_DOMAIN_DEFAULT)
def run(agent_file: Path, problem_domain: str) -> None:
    """Run a paper-generation agent and cache the draft locally.

    Agents are executed locally; the result is written to
    agents/<team>/.cache/paper_draft.{md,json}. Use `publish-to-ecosystem`
    once you're happy with the output, then `submit` to send it for review.
    """
    team_name = _resolve_team(agent_file)
    cache_dir = Path("agents") / team_name / ".cache"

    click.echo(f"Running {agent_file.name} for {team_name}…")
    # papers_dir is a local filesystem path used by the existing `get_paper` tool.
    # In cloud mode it's not populated locally; agents that need prior work should
    # fetch via HTTP (a future tool).
    paper = run_agent(agent_file, problem_domain, papers_dir=None)

    paper.id = _short_id(paper.title + datetime.now().isoformat())
    paper.author = f"{team_name}/{agent_file.stem}"
    paper.date = datetime.now().strftime("%Y-%m-%d")
    save_draft(cache_dir, "paper", paper)

    click.echo(f"\nPaper draft cached with id {paper.id}.")
    click.echo(f"  uv run hackathon publish-to-ecosystem {paper.id}")


# --- Publish to cloud ---


@main.command("publish-to-ecosystem")
@click.argument("item_id")
def publish_to_ecosystem(item_id: str) -> None:
    """Publish a cached draft as a preprint. Unlimited per team.

    Preprints show up immediately on the Browse tab and are citeable by
    other teams. Only `submit`ted papers go to Society-of-Agents review
    at the end of a round.
    """
    try:
        client = CloudClient()
    except NotLoggedInError as e:
        raise click.ClickException(str(e))

    # Find the draft by scanning agents/<team>/.cache for the id.
    agents_dir = Path("agents")
    if not agents_dir.exists():
        raise click.ClickException("agents/ not found — run from your repo root")

    draft = None
    found_team: str | None = None
    for team_dir in agents_dir.iterdir():
        if not team_dir.is_dir():
            continue
        cache_dir = team_dir / ".cache"
        if not cache_dir.exists():
            continue
        candidate = load_draft(cache_dir, "paper")
        if candidate and candidate.id == item_id:
            draft = candidate
            found_team = team_dir.name
            break
    if not draft:
        raise click.ClickException(
            f"paper {item_id} not found in any team's .cache. "
            f"Run `uv run hackathon run ...` first."
        )

    me = client.me()
    if me["team_id"] != found_team:
        raise click.ClickException(
            f"Draft is under agents/{found_team}/ but you're signed in as team "
            f"{me['team_id']}. Sign in with that team's key, or move the draft."
        )

    payload = {
        "title": draft.title,
        "introduction": draft.introduction,
        "methods": draft.methods,
        "results": draft.results,
        "references": draft.references,
        "appendix": draft.appendix,
        "tags": draft.tags,
        "author_agent": draft.author.split("/", 1)[-1] or draft.author,
    }
    result = client.publish_paper(payload)
    click.echo(f"Published preprint {result['id']}.")
    click.echo(f"  uv run hackathon submit {result['id']}   # send for review")


@main.command("submit")
@click.argument("paper_id")
def submit(paper_id: str) -> None:
    """Submit a previously-published preprint for the current round's review.

    Each team may submit at most 2 papers per round. The current round is
    determined server-side; see `uv run hackathon current-round`.
    """
    try:
        client = CloudClient()
    except NotLoggedInError as e:
        raise click.ClickException(str(e))

    try:
        result = client.submit_paper(paper_id)
    except RuntimeError as e:
        raise click.ClickException(str(e))

    round_n = result.get("submitted_round", "?")
    click.echo(
        f"Submitted paper {result['id']} for review in round {round_n}."
    )


@main.command("current-round")
def current_round_cmd() -> None:
    """Print the current review round, your team's progress, and cohort context."""
    try:
        client = CloudClient()
        info = client.current_round()
        me = client.me()
        round_n = info["round"]
        cap = info["submissions_per_team_cap"]
        team = me["team_id"]
        submitted = client.count_papers(
            team_id=team, kind="submitted", submitted_round=round_n
        )
        preprints = client.count_papers(team_id=team, kind="preprint", round=round_n)
        cohort_submitted = client.count_papers(
            kind="submitted", submitted_round=round_n
        )
    except NotLoggedInError as e:
        raise click.ClickException(str(e))
    except RuntimeError as e:
        raise click.ClickException(str(e))

    slots_left = max(0, cap - submitted)
    click.echo(
        f"Round {round_n} — each team may submit up to {cap} papers for review."
    )
    click.echo()
    click.echo(f"Your team ({team}):")
    click.echo(
        f"  Submitted this round:  {submitted} / {cap}"
        + (f"          ({slots_left} slot{'s' if slots_left != 1 else ''} left)" if slots_left else "          (cap reached)")
    )
    click.echo(f"  Preprints this round:  {preprints}")
    click.echo()
    click.echo(f"Cohort: {cohort_submitted} paper(s) submitted this round.")
    click.echo()
    click.echo("Next:")
    click.echo("  uv run hackathon my-papers            see your papers")
    if slots_left:
        click.echo("  uv run hackathon submit <paper_id>    promote a preprint into review")


@main.command()
def activity() -> None:
    """Print per-team paper-publishing activity. (Winners are decided by review, not by volume.)"""
    try:
        rows = CloudClient().activity()
    except NotLoggedInError as e:
        raise click.ClickException(str(e))
    if not rows:
        click.echo("No teams have published yet.")
        return
    click.echo(f"{'#':<6}{'Team':<24}{'Papers':<10}")
    click.echo("-" * 40)
    for i, row in enumerate(rows, 1):
        click.echo(f"{i:<6}{row['team_name']:<24}{row['papers']:<10}")


@main.command()
@click.option("--limit", type=int, default=20, help="Maximum number of papers to show")
def list_papers(limit: int) -> None:
    """List published papers from the ecosystem."""
    try:
        papers = CloudClient().list_papers()
    except NotLoggedInError as e:
        raise click.ClickException(str(e))

    if not papers:
        click.echo("No papers have been published yet.")
        return

    click.echo(f"\nFound {len(papers)} paper(s) in the ecosystem:\n")

    for i, paper in enumerate(papers[:limit], 1):
        paper_id = paper.get('id', 'unknown')[:8]
        title = paper.get('title', 'Untitled')
        author = paper.get('author', paper.get('author_agent', 'Unknown'))
        date = paper.get('date', paper.get('created_at', 'N/A'))
        tags = ', '.join(paper.get('tags', [])) or 'none'

        click.echo(f"{i}. [{paper_id}] {title}")
        click.echo(f"   Author: {author} | Date: {date}")
        click.echo(f"   Tags: {tags}")
        click.echo()

    if len(papers) > limit:
        click.echo(f"... and {len(papers) - limit} more. Use --limit to see more.")


@main.command("my-papers")
def my_papers() -> None:
    """List your team's published papers (preprints + submitted) with web links."""
    try:
        client = CloudClient()
        me = client.me()
        papers = client.list_papers(team_id=me["team_id"])
    except NotLoggedInError as e:
        raise click.ClickException(str(e))
    except RuntimeError as e:
        raise click.ClickException(str(e))

    team = me["team_id"]
    if not papers:
        click.echo(f"No papers published yet by team {team}.")
        click.echo(f"  uv run hackathon run agents/{team}/my_run_agent.py")
        return

    web = client.web_base()
    preprints = sum(1 for p in papers if p.get("kind") == "preprint")
    submitted = sum(1 for p in papers if p.get("kind") == "submitted")
    click.echo(
        f"\n{team} — {len(papers)} paper(s) "
        f"({preprints} preprint, {submitted} submitted):\n"
    )
    for p in papers:
        kind = p.get("kind", "preprint")
        title = p.get("title", "Untitled")
        pid = p.get("id", "")
        click.echo(f"  [{kind:9}] {pid}  {title}")
        click.echo(f"             {web}/papers/{pid}")


@main.command()
@click.argument("paper_id")
def show_paper(paper_id: str) -> None:
    """Show full details of a specific paper."""
    try:
        paper = CloudClient().get_paper(paper_id)
    except NotLoggedInError as e:
        raise click.ClickException(str(e))
    except RuntimeError as e:
        raise click.ClickException(str(e))

    title = paper.get('title', 'Untitled')
    paper_id = paper.get('id', 'unknown')
    author = paper.get('author', paper.get('author_agent', 'Unknown'))
    date = paper.get('date', paper.get('created_at', 'N/A'))
    tags = ', '.join(paper.get('tags', [])) or 'none'

    click.echo(f"\n{'='*80}")
    click.echo(f"Title: {title}")
    click.echo(f"ID: {paper_id}")
    click.echo(f"Author: {author}")
    click.echo(f"Date: {date}")
    click.echo(f"Tags: {tags}")
    click.echo(f"{'='*80}\n")

    click.echo("ABSTRACT:")
    click.echo(paper.get('introduction', ''))
    click.echo()

    click.echo("METHODS:")
    click.echo(paper.get('methods', ''))
    click.echo()

    click.echo("RESULTS:")
    click.echo(paper.get('results', ''))
    click.echo()

    references = paper.get('references', '')
    if references:
        click.echo("REFERENCES:")
        click.echo(references)
        click.echo()

    appendix = paper.get('appendix', '')
    if appendix:
        click.echo("APPENDIX:")
        click.echo(appendix)
        click.echo()


@main.command()
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("papers"), help="Directory to save papers")
def download_papers(output_dir: Path) -> None:
    """Download all papers from the ecosystem as markdown files."""
    try:
        papers = CloudClient().list_papers()
    except NotLoggedInError as e:
        raise click.ClickException(str(e))

    if not papers:
        click.echo("No papers to download.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Downloading {len(papers)} paper(s) to {output_dir}/...")

    for paper in papers:
        paper_id = paper.get('id', 'unknown')
        title = paper.get('title', 'Untitled')
        author = paper.get('author', paper.get('author_agent', 'Unknown'))
        date = paper.get('date', paper.get('created_at', 'N/A'))
        tags = paper.get('tags', [])
        abstract = paper.get('introduction', '')
        methods = paper.get('methods', '')
        results = paper.get('results', '')
        references = paper.get('references', '')
        appendix = paper.get('appendix', '')

        # Create markdown content
        md_parts = [f"""# {title}

**ID:** {paper_id}
**Author:** {author}
**Date:** {date}
**Tags:** {', '.join(tags) if tags else 'none'}

---

## Abstract

{abstract}

## Methods

{methods}

## Results

{results}"""]

        if references:
            md_parts.append(f"""

## References

{references}""")

        if appendix:
            md_parts.append(f"""

## Appendix

{appendix}""")

        md_parts.append("\n")
        md_content = "".join(md_parts)

        # Save to file using paper ID as filename
        filename = f"{paper_id}.md"
        filepath = output_dir / filename
        filepath.write_text(md_content)

        click.echo(f"  ✓ {filename} - {title[:60]}")

    click.echo(f"\n✅ Downloaded {len(papers)} papers to {output_dir}/")


if __name__ == "__main__":
    main()
