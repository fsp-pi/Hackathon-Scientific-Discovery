"""Tests for review tracker functionality."""

import json

from hackathon_science.tracker import (
    load_tracker,
    save_tracker,
    mark_reviewed,
    get_unreviewed_papers,
    get_previous_review
)
from hackathon_science.models import Paper


class TestLoadTracker:
    """Tests for load_tracker function."""

    def test_load_tracker_missing_file(self, tmp_path):
        """Test that load_tracker returns empty dict when file doesn't exist."""
        cache_dir = tmp_path / ".cache"

        result = load_tracker(cache_dir)

        assert result == {}

    def test_load_tracker_valid_file(self, tmp_path):
        """Test that load_tracker loads valid JSON file."""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()

        tracker_data = {
            "agent1": {
                "paper1": "review1",
                "paper2": "review2"
            },
            "agent2": {
                "paper1": "review3"
            }
        }

        tracker_file = cache_dir / "reviewed.json"
        with open(tracker_file, "w") as f:
            json.dump(tracker_data, f)

        result = load_tracker(cache_dir)

        assert result == tracker_data

    def test_load_tracker_corrupted_file(self, tmp_path):
        """Test that load_tracker returns empty dict for corrupted JSON."""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()

        tracker_file = cache_dir / "reviewed.json"
        tracker_file.write_text("not valid json {{{")

        result = load_tracker(cache_dir)

        assert result == {}

    def test_load_tracker_empty_file(self, tmp_path):
        """Test that load_tracker handles empty file."""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()

        tracker_file = cache_dir / "reviewed.json"
        tracker_file.write_text("")

        result = load_tracker(cache_dir)

        assert result == {}

    def test_load_tracker_creates_cache_dir_if_missing(self, tmp_path):
        """Test that load_tracker doesn't fail if cache dir doesn't exist."""
        cache_dir = tmp_path / ".cache"

        result = load_tracker(cache_dir)

        assert result == {}


class TestSaveTracker:
    """Tests for save_tracker function."""

    def test_save_tracker_creates_cache_dir(self, tmp_path):
        """Test that save_tracker creates cache directory if it doesn't exist."""
        cache_dir = tmp_path / ".cache"
        tracker = {"agent1": {"paper1": "review1"}}

        save_tracker(cache_dir, tracker)

        assert cache_dir.exists()
        assert (cache_dir / "reviewed.json").exists()

    def test_save_tracker_writes_json(self, tmp_path):
        """Test that save_tracker writes valid JSON."""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()

        tracker = {
            "agent1": {
                "paper1": "review1",
                "paper2": "review2"
            },
            "agent2": {
                "paper1": "review3"
            }
        }

        save_tracker(cache_dir, tracker)

        tracker_file = cache_dir / "reviewed.json"
        with open(tracker_file, "r") as f:
            loaded = json.load(f)

        assert loaded == tracker

    def test_save_tracker_overwrites_existing(self, tmp_path):
        """Test that save_tracker overwrites existing file."""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()

        tracker_file = cache_dir / "reviewed.json"
        tracker_file.write_text('{"old": "data"}')

        tracker = {"agent1": {"paper1": "review1"}}
        save_tracker(cache_dir, tracker)

        with open(tracker_file, "r") as f:
            loaded = json.load(f)

        assert loaded == tracker

    def test_save_tracker_empty_dict(self, tmp_path):
        """Test that save_tracker handles empty dictionary."""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir()

        tracker = {}
        save_tracker(cache_dir, tracker)

        tracker_file = cache_dir / "reviewed.json"
        with open(tracker_file, "r") as f:
            loaded = json.load(f)

        assert loaded == {}


class TestMarkReviewed:
    """Tests for mark_reviewed function."""

    def test_mark_reviewed_new_agent(self):
        """Test marking a paper as reviewed for a new agent."""
        tracker = {}

        mark_reviewed(tracker, "agent1", "paper1", "review1")

        assert tracker == {"agent1": {"paper1": "review1"}}

    def test_mark_reviewed_existing_agent(self):
        """Test marking a paper as reviewed for an existing agent."""
        tracker = {"agent1": {"paper1": "review1"}}

        mark_reviewed(tracker, "agent1", "paper2", "review2")

        assert tracker == {
            "agent1": {
                "paper1": "review1",
                "paper2": "review2"
            }
        }

    def test_mark_reviewed_multiple_agents(self):
        """Test marking papers for multiple agents."""
        tracker = {"agent1": {"paper1": "review1"}}

        mark_reviewed(tracker, "agent2", "paper1", "review2")

        assert tracker == {
            "agent1": {"paper1": "review1"},
            "agent2": {"paper1": "review2"}
        }

    def test_mark_reviewed_updates_existing_review(self):
        """Test that marking an already-reviewed paper updates the review ID."""
        tracker = {"agent1": {"paper1": "review1"}}

        mark_reviewed(tracker, "agent1", "paper1", "review2")

        assert tracker == {"agent1": {"paper1": "review2"}}


class TestGetUnreviewedPapers:
    """Tests for get_unreviewed_papers function."""

    @staticmethod
    def papers():
        return [
            Paper(id="paper1", title="Paper 1", introduction="A", methods="M", results="R"),
            Paper(id="paper2", title="Paper 2", introduction="A", methods="M", results="R"),
        ]

    def test_get_unreviewed_papers_all_unreviewed(self):
        """Test filtering when all papers are unreviewed."""
        tracker = {}
        papers = self.papers()

        result = get_unreviewed_papers(tracker, "agent1", papers)

        assert len(result) == 2
        assert result == papers

    def test_get_unreviewed_papers_some_reviewed(self):
        """Test filtering when some papers are reviewed."""
        tracker = {"agent1": {"paper1": "review1"}}
        papers = self.papers()

        result = get_unreviewed_papers(tracker, "agent1", papers)

        assert len(result) == 1
        assert result[0].id == "paper2"

    def test_get_unreviewed_papers_all_reviewed(self):
        """Test filtering when all papers are reviewed."""
        tracker = {
            "agent1": {
                "paper1": "review1",
                "paper2": "review2"
            }
        }
        papers = self.papers()

        result = get_unreviewed_papers(tracker, "agent1", papers)

        assert result == []

    def test_get_unreviewed_papers_different_agent(self):
        """Test that reviews by other agents don't affect filtering."""
        tracker = {"agent1": {"paper1": "review1"}}
        papers = self.papers()

        result = get_unreviewed_papers(tracker, "agent2", papers)

        assert len(result) == 2
        assert result == papers

    def test_get_unreviewed_papers_empty_list(self):
        """Test filtering with empty paper list."""
        tracker = {"agent1": {"paper1": "review1"}}
        papers = []

        result = get_unreviewed_papers(tracker, "agent1", papers)

        assert result == []

    def test_get_unreviewed_papers_missing_paper_id(self):
        """Test filtering with papers that don't have IDs."""
        tracker = {"agent1": {"paper1": "review1"}}
        papers = [
            Paper(id="", title="Untitled 1", introduction="A", methods="M", results="R"),
            Paper(id="", title="Untitled 2", introduction="A", methods="M", results="R"),
        ]

        result = get_unreviewed_papers(tracker, "agent1", papers)

        # Papers without IDs should be included (treated as unreviewed)
        assert len(result) == 2


class TestGetPreviousReview:
    """Tests for get_previous_review function."""

    def test_get_previous_review_exists(self):
        """Test getting a previous review that exists."""
        tracker = {
            "agent1": {
                "paper1": "review1",
                "paper2": "review2"
            }
        }

        result = get_previous_review(tracker, "agent1", "paper1")

        assert result == "review1"

    def test_get_previous_review_not_found(self):
        """Test getting a previous review that doesn't exist."""
        tracker = {"agent1": {"paper1": "review1"}}

        result = get_previous_review(tracker, "agent1", "paper2")

        assert result is None

    def test_get_previous_review_agent_not_found(self):
        """Test getting a previous review when agent doesn't exist."""
        tracker = {"agent1": {"paper1": "review1"}}

        result = get_previous_review(tracker, "agent2", "paper1")

        assert result is None

    def test_get_previous_review_empty_tracker(self):
        """Test getting a previous review from empty tracker."""
        tracker = {}

        result = get_previous_review(tracker, "agent1", "paper1")

        assert result is None
