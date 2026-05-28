"""Tests for Paper dataclass."""

import pytest
from hackathon_science.models import Paper


class TestPaper:
    """Tests for Paper dataclass."""

    def test_paper_creation_with_required_fields(self):
        """Test creating Paper with required fields sets all fields correctly."""
        paper = Paper(
            title="Sample Title",
            introduction="Sample Abstract",
            methods="Sample Methods",
            results="Sample Results",
        )

        assert paper.title == "Sample Title"
        assert paper.introduction == "Sample Abstract"
        assert paper.methods == "Sample Methods"
        assert paper.results == "Sample Results"

    def test_paper_optional_fields_default_correctly(self):
        """Test optional fields default to empty/expected values."""
        paper = Paper(
            title="Sample Title",
            introduction="Sample Abstract",
            methods="Sample Methods",
            results="Sample Results",
        )

        assert paper.id == ""
        assert paper.author == ""
        assert paper.date == ""
        assert paper.tags == []

    def test_paper_creation_with_optional_fields(self):
        """Test creating Paper with optional fields populated."""
        paper = Paper(
            title="Sample Title",
            introduction="Sample Abstract",
            methods="Sample Methods",
            results="Sample Results",
            id="paper-001",
            author="John Doe",
            date="2024-01-15",
            tags=["AI", "ML"],
        )

        assert paper.id == "paper-001"
        assert paper.author == "John Doe"
        assert paper.date == "2024-01-15"
        assert paper.tags == ["AI", "ML"]

    def test_paper_tags_are_mutable_across_instances(self):
        """Test that tags list is independent across Paper instances."""
        paper1 = Paper(
            title="Title 1",
            introduction="Abstract 1",
            methods="Methods 1",
            results="Results 1",
        )
        paper2 = Paper(
            title="Title 2",
            introduction="Abstract 2",
            methods="Methods 2",
            results="Results 2",
        )

        paper1.tags.append("tag1")

        assert paper1.tags == ["tag1"]
        assert paper2.tags == []

