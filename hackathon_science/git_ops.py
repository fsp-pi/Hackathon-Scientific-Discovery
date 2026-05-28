"""Git operations for publishing and loading papers."""

import hashlib
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from git import Repo, GitCommandError

from hackathon_science.models import Paper




def _validate_branch(repo: Repo, team_name: str) -> None:
    """
    Validate that current branch is safe for pushing.

    Args:
        repo: Git repository
        team_name: Team name

    Raises:
        ValueError: If on main branch or branch doesn't match team
    """
    current_branch = repo.active_branch.name

    if current_branch == "main":
        raise ValueError(
            f"ERROR: Cannot publish from 'main' branch!\n\n"
            f"Teams must work on their own branches to avoid conflicts.\n\n"
            f"To fix this:\n"
            f"  1. Create your team branch: git checkout -b team-{team_name}\n"
            f"  2. Try publishing again\n\n"
            f"Example: git checkout -b team-{team_name}"
        )

    # Recommend team-specific branch naming
    expected_branch = f"team-{team_name}"
    if current_branch != expected_branch:
        # Warning but not error - allow flexibility
        print(f"⚠️  Warning: Current branch is '{current_branch}', "
              f"recommended branch name is '{expected_branch}'")


def clone_repo(url: str, local_path: Path) -> None:
    """
    Clone git repository to local path.

    Args:
        url: Git repository URL
        local_path: Local path to clone to

    Raises:
        GitCommandError: If clone fails
    """
    local_path.parent.mkdir(parents=True, exist_ok=True)
    Repo.clone_from(url, local_path)


def pull_latest(repo_path: Path) -> None:
    """
    Pull latest changes from remote repository.

    Args:
        repo_path: Path to local repository

    Raises:
        GitCommandError: If pull fails
    """
    repo = Repo(repo_path)
    origin = repo.remotes.origin
    origin.pull()


def _generate_id(content: str) -> str:
    """
    Generate 8-character hex ID from content.

    Args:
        content: String to hash

    Returns:
        8-character hex string
    """
    hash_obj = hashlib.sha256(content.encode('utf-8'))
    return hash_obj.hexdigest()[:8]


def load_papers(repo_path: Path) -> list[Paper]:
    """
    Load all papers from repository.

    Args:
        repo_path: Path to repository root

    Returns:
        List of Paper objects
    """
    papers_dir = repo_path / "papers"
    if not papers_dir.exists():
        return []

    papers = []
    for paper_file in papers_dir.glob("*.md"):
        try:
            content = paper_file.read_text(encoding='utf-8')

            # Split frontmatter and body
            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            frontmatter = yaml.safe_load(parts[1])
            body = parts[2].strip()

            # Parse body sections
            methods = ""
            results = ""
            references = ""
            appendix = ""

            # Split by ## headers (handle both "## " at start and after newlines)
            sections = body.split("## ")
            for section in sections:
                section = section.strip()
                if section.startswith("Methods"):
                    methods = section[len("Methods"):].strip()
                elif section.startswith("Results"):
                    results = section[len("Results"):].strip()
                elif section.startswith("References"):
                    references = section[len("References"):].strip()
                elif section.startswith("Appendix"):
                    appendix = section[len("Appendix"):].strip()

            # Convert date to string if it's a date object
            date_value = frontmatter.get("date", "")
            if hasattr(date_value, "isoformat"):
                date_value = date_value.isoformat()
            elif date_value and not isinstance(date_value, str):
                date_value = str(date_value)

            paper = Paper(
                id=frontmatter.get("id", ""),
                title=frontmatter.get("title", ""),
                author=frontmatter.get("author", ""),
                date=date_value,
                introduction=frontmatter.get("introduction", ""),
                tags=frontmatter.get("tags", []),
                methods=methods,
                results=results,
                references=references,
                appendix=appendix
            )
            papers.append(paper)

        except Exception:
            # Skip malformed files
            continue

    return papers




def publish_paper(
    paper: Paper,
    repo_path: Path,
    team_name: str,
    agent_name: str,
    agent_file_path: Path,
    max_retries: int = 3
) -> str:
    """
    Publish paper to shared repository.

    Args:
        paper: Paper object to publish
        repo_path: Path to repository root
        team_name: Team name
        agent_name: Agent name
        agent_file_path: Path to agent source file
        max_retries: Maximum number of retry attempts on conflict

    Returns:
        Paper ID

    Raises:
        ValueError: If validation fails or citations are invalid
        GitCommandError: If publish fails after retries
    """
    # Validate required fields
    if not paper.title:
        raise ValueError("Paper missing required field: title")
    if not paper.introduction:
        raise ValueError("Paper missing required field: introduction")
    if not paper.methods:
        raise ValueError("Paper missing required field: methods")
    if not paper.results:
        raise ValueError("Paper missing required field: results")

    # No citation validation needed - references are free-form text

    # Generate ID and populate metadata
    timestamp = datetime.now().isoformat()
    paper_id = _generate_id(paper.title + timestamp)
    paper.id = paper_id
    paper.author = f"{team_name}/{agent_name}"
    paper.date = datetime.now().strftime("%Y-%m-%d")

    # Create paper file content
    frontmatter = {
        "id": paper.id,
        "title": paper.title,
        "author": paper.author,
        "date": paper.date,
        "introduction": paper.introduction,
        "tags": paper.tags
    }

    body_parts = [
        f"""## Methods

{paper.methods}

## Results

{paper.results}"""
    ]

    # Add references if present
    if paper.references:
        body_parts.append(f"""

## References

{paper.references}""")

    # Add appendix if present
    if paper.appendix:
        body_parts.append(f"""

## Appendix

{paper.appendix}""")

    body = "".join(body_parts) + "\n"

    content = f"""---
{yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)}---

{body}"""

    # Attempt publish with retry on conflicts
    for attempt in range(max_retries):
        try:
            repo = Repo(repo_path)

            # Validate branch before publishing
            _validate_branch(repo, team_name)

            # Pull latest changes
            if attempt > 0:
                origin = repo.remotes.origin
                origin.pull('--rebase')

                # Re-check for ID collision after pull
                existing_papers = load_papers(repo_path)
                if any(p.id == paper_id for p in existing_papers):
                    # Hash collision - regenerate ID
                    paper_id = _generate_id(paper.title + timestamp + str(attempt))
                    paper.id = paper_id
                    frontmatter["id"] = paper_id
                    content = f"""---
{yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)}---

{body}"""

            # Write paper file
            papers_dir = repo_path / "papers"
            papers_dir.mkdir(exist_ok=True)
            paper_file = papers_dir / f"{paper_id}.md"
            paper_file.write_text(content, encoding='utf-8')

            # Git commit and push
            repo.index.add([str(paper_file.relative_to(repo_path))])
            repo.index.commit(f"Publish paper by {paper.author}")

            origin = repo.remotes.origin
            current_branch = repo.active_branch.name
            origin.push(refspec=f"{current_branch}:{current_branch}")

            return paper_id

        except GitCommandError as e:
            if attempt < max_retries - 1:
                # Retry on next iteration
                continue
            else:
                # Max retries exceeded
                raise GitCommandError(
                    f"Failed to publish paper after {max_retries} attempts",
                    status=e.status,
                    stderr=e.stderr
                ) from e

    # Should not reach here
    raise GitCommandError("Failed to publish paper", status=1)




