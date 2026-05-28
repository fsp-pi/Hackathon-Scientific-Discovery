"""Tests for caching operations."""
from hackathon_science.cache import save_draft, load_draft, save_failed_publish, load_failed_publishes, clear_failed_publishes
from hackathon_science.models import Paper


def test_save_paper_draft(tmp_path):
    """Test saving paper draft to cache."""
    cache_dir = tmp_path / ".cache"

    paper = Paper(
        title="Test Paper",
        introduction="Abstract",
        methods="Methods",
        results="Results",
    )

    save_draft(cache_dir, "paper", paper)

    draft_file = cache_dir / "paper_draft.md"
    assert draft_file.exists()

    content = draft_file.read_text()
    assert "Test Paper" in content


def test_load_paper_draft(tmp_path):
    """Test loading paper draft from cache."""
    cache_dir = tmp_path / ".cache"

    paper = Paper(
        id="abc123",
        title="Test Paper",
        introduction="Abstract content",
        methods="Methods content",
        results="Results content",
    )
    save_draft(cache_dir, "paper", paper)

    content = load_draft(cache_dir, "paper")
    assert content is not None
    assert content.title == "Test Paper"
    assert content.introduction == "Abstract content"


def test_load_draft_missing(tmp_path):
    """Test loading draft when file doesn't exist."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()

    content = load_draft(cache_dir, "paper")
    assert content is None


def test_save_string_draft(tmp_path):
    """Test saving string draft to cache."""
    cache_dir = tmp_path / ".cache"

    draft_text = "# Draft Paper\n\nThis is a draft."

    save_draft(cache_dir, "paper", draft_text)

    draft_file = cache_dir / "paper_draft.md"
    assert draft_file.exists()

    content = draft_file.read_text()
    assert content == draft_text


def test_save_failed_publish(tmp_path):
    """Test saving failed publish to queue."""
    cache_dir = tmp_path / ".cache"

    content = {
        "title": "Test Paper",
        "introduction": "Abstract"
    }
    error = "Network timeout"

    save_failed_publish(cache_dir, content, error)

    queue_file = cache_dir / "failed_publish.json"
    assert queue_file.exists()


def test_load_failed_publishes(tmp_path):
    """Test loading failed publish queue."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()

    # Save some failed publishes
    content1 = {"title": "Paper 1"}
    content2 = {"title": "Paper 2"}

    save_failed_publish(cache_dir, content1, "Error 1")
    save_failed_publish(cache_dir, content2, "Error 2")

    queue = load_failed_publishes(cache_dir)
    assert len(queue) == 2
    assert queue[0]["type"] == "paper"
    assert queue[0]["error"] == "Error 1"
    assert queue[1]["type"] == "paper"
    assert queue[1]["error"] == "Error 2"


def test_load_failed_publishes_empty(tmp_path):
    """Test loading empty failed publish queue."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()

    queue = load_failed_publishes(cache_dir)
    assert queue == []


def test_clear_failed_publishes(tmp_path):
    """Test clearing failed publish queue."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()

    # Save some failed publishes
    save_failed_publish(cache_dir, {"title": "Test"}, "Error")

    queue_file = cache_dir / "failed_publish.json"
    assert queue_file.exists()

    clear_failed_publishes(cache_dir)
    assert not queue_file.exists()


def test_clear_failed_publishes_no_file(tmp_path):
    """Test clearing failed publish queue when file doesn't exist."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()

    # Should not raise error
    clear_failed_publishes(cache_dir)
