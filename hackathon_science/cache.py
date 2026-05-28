"""Caching for drafts and failed publishes."""
import json
import time
from pathlib import Path
from typing import Optional, Union
from hackathon_science.models import Paper


def save_draft(cache_dir: Path, draft_type: str, content: Union[Paper, str]) -> None:
    """
    Save draft to cache.

    Args:
        cache_dir: Path to .cache directory
        draft_type: "paper"
        content: Paper or markdown string
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    draft_file = cache_dir / f"{draft_type}_draft.md"
    json_file = cache_dir / f"{draft_type}_draft.json"

    if isinstance(content, Paper):
        # Save JSON for programmatic access
        with open(json_file, "w") as f:
            json.dump(content.__dict__, f, indent=2)

        # Save markdown for human readability
        text_parts = [f"""# {content.title}

## Abstract
{content.introduction}

## Methods
{content.methods}

## Results
{content.results}"""]

        if content.references:
            text_parts.append(f"""

## References
{content.references}""")

        if content.appendix:
            text_parts.append(f"""

## Appendix
{content.appendix}""")

        text_parts.append(f"""

Tags: {', '.join(content.tags)}
""")
        text = "".join(text_parts)
    else:
        text = content

    draft_file.write_text(text)


def load_draft(cache_dir: Path, draft_type: str) -> Optional[Paper]:
    """
    Load draft from cache.

    Args:
        cache_dir: Path to .cache directory
        draft_type: "paper"

    Returns:
        Paper object or None if not found
    """
    json_file = cache_dir / f"{draft_type}_draft.json"

    if not json_file.exists():
        return None

    with open(json_file) as f:
        data = json.load(f)

    if draft_type == "paper":
        return Paper(**data)
    else:
        return None


def save_failed_publish(cache_dir: Path, content: dict, error: str) -> None:
    """
    Save failed publish to queue.

    Args:
        cache_dir: Path to .cache directory
        content: Paper data dict
        error: Error message
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    queue_file = cache_dir / "failed_publish.json"

    # Load existing queue
    if queue_file.exists():
        with open(queue_file) as f:
            queue = json.load(f)
    else:
        queue = []

    # Add new failed item
    queue.append({
        "type": "paper",
        "content": content,
        "error": error,
        "timestamp": time.time()
    })

    # Save queue
    with open(queue_file, "w") as f:
        json.dump(queue, f, indent=2)


def load_failed_publishes(cache_dir: Path) -> list[dict]:
    """
    Load failed publish queue.

    Args:
        cache_dir: Path to .cache directory

    Returns:
        List of failed publish items
    """
    queue_file = cache_dir / "failed_publish.json"

    if not queue_file.exists():
        return []

    with open(queue_file) as f:
        return json.load(f)


def clear_failed_publishes(cache_dir: Path) -> None:
    """
    Clear failed publish queue.

    Args:
        cache_dir: Path to .cache directory
    """
    queue_file = cache_dir / "failed_publish.json"

    if queue_file.exists():
        queue_file.unlink()
