"""Review tracking to prevent duplicate reviews."""

import json
from pathlib import Path
from typing import Optional

from hackathon_science.models import Paper


def load_tracker(cache_dir: Path) -> dict:
    """Load review tracker from cache directory.

    Reads the reviewed.json file from the cache directory and returns
    the tracking data. Returns an empty dict if the file doesn't exist
    or is corrupted.

    Args:
        cache_dir: Path to cache directory (typically .cache)

    Returns:
        Dictionary mapping agent names to their reviewed papers:
        {agent_name: {paper_id: review_id}}
    """
    tracker_file = cache_dir / "reviewed.json"

    if not tracker_file.exists():
        return {}

    try:
        with open(tracker_file, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, IOError):
        return {}


def save_tracker(cache_dir: Path, tracker: dict) -> None:
    """Save review tracker to cache directory.

    Writes the tracking data to reviewed.json in the cache directory.
    Creates the cache directory if it doesn't exist.

    Args:
        cache_dir: Path to cache directory (typically .cache)
        tracker: Dictionary mapping agent names to their reviewed papers
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    tracker_file = cache_dir / "reviewed.json"

    with open(tracker_file, "w") as f:
        json.dump(tracker, f, indent=2)


def mark_reviewed(tracker: dict, agent_name: str, paper_id: str, review_id: str) -> None:
    """Mark a paper as reviewed by an agent.

    Updates the tracker dictionary in-place to record that an agent
    has reviewed a specific paper.

    Args:
        tracker: Dictionary mapping agent names to their reviewed papers
        agent_name: Name of the reviewing agent
        paper_id: ID of the paper being reviewed
        review_id: ID of the review that was created
    """
    if agent_name not in tracker:
        tracker[agent_name] = {}

    tracker[agent_name][paper_id] = review_id


def get_unreviewed_papers(tracker: dict, agent_name: str, papers: list[Paper]) -> list[Paper]:
    """Filter papers to only those not yet reviewed by the agent.

    Returns a list of papers that the specified agent has not yet reviewed.

    Args:
        tracker: Dictionary mapping agent names to their reviewed papers
        agent_name: Name of the agent
        papers: List of papers to filter

    Returns:
        List of papers that have not been reviewed by the agent
    """
    if agent_name not in tracker:
        return papers

    reviewed_ids = set(tracker[agent_name].keys())

    return [paper for paper in papers if paper.id not in reviewed_ids]


def get_previous_review(tracker: dict, agent_name: str, paper_id: str) -> Optional[str]:
    """Get the review ID for a previously reviewed paper.

    Returns the review ID if the agent has already reviewed this paper,
    or None if no review exists.

    Args:
        tracker: Dictionary mapping agent names to their reviewed papers
        agent_name: Name of the agent
        paper_id: ID of the paper

    Returns:
        Review ID if found, None otherwise
    """
    if agent_name not in tracker:
        return None

    return tracker[agent_name].get(paper_id)
