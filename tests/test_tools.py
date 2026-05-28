"""Tests for agent tools."""

import pytest
import subprocess
from unittest.mock import Mock, patch

from hackathon_science.tools import run_code, search_web, get_paper


class TestRunCode:
    """Tests for run_code function."""

    def test_run_code_executes_simple_command(self):
        """Test that run_code executes Python code in a subprocess."""
        with patch("hackathon_science.tools.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["python3", "script.py"],
                returncode=0,
                stdout="Hello, World!\n",
                stderr="",
            )

            result = run_code("print('Hello, World!')")

            assert result == "Hello, World!\n"
            mock_run.assert_called_once()
            assert mock_run.call_args.kwargs["timeout"] == 300

    def test_run_code_with_custom_timeout(self):
        """Test that run_code accepts custom timeout."""
        with patch("hackathon_science.tools.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["python3", "script.py"],
                returncode=0,
                stdout="output",
                stderr="",
            )

            result = run_code("print('output')", timeout=600)

            assert result == "output"
            assert mock_run.call_args.kwargs["timeout"] == 600

    def test_run_code_returns_combined_output(self):
        """Test that run_code returns combined stdout and stderr."""
        with patch("hackathon_science.tools.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["python3", "script.py"],
                returncode=0,
                stdout="stdout\n",
                stderr="stderr",
            )

            result = run_code("print('stdout')")

            assert "stdout" in result
            assert "stderr" in result

    def test_run_code_reports_nonzero_return_code(self):
        """Test that run_code includes non-zero process status."""
        with patch("hackathon_science.tools.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["python3", "script.py"],
                returncode=2,
                stdout="",
                stderr="bad",
            )

            result = run_code("raise SystemExit(2)")

            assert "bad" in result
            assert "Process exited with code 2" in result

    def test_run_code_handles_errors(self):
        """Test that run_code handles execution errors."""
        with patch("hackathon_science.tools.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Execution failed")

            result = run_code("invalid python")

            assert result == "Error executing code: Execution failed"


class TestSearchWeb:
    """Tests for search_web function."""

    def test_search_web_returns_results(self):
        """Test that search_web returns search results."""
        with patch('hackathon_science.tools.DDGS') as mock_ddgs_class:
            mock_ddgs = Mock()
            mock_ddgs.text.return_value = [
                {
                    'title': 'Test Result',
                    'href': 'https://example.com',
                    'body': 'This is a test snippet'
                }
            ]
            mock_ddgs_class.return_value = mock_ddgs

            results = search_web("test query")

            assert len(results) == 1
            assert results[0]['title'] == 'Test Result'
            assert results[0]['url'] == 'https://example.com'
            assert results[0]['snippet'] == 'This is a test snippet'
            mock_ddgs.text.assert_called_once_with("test query", max_results=10)

    def test_search_web_with_custom_max_results(self):
        """Test that search_web accepts custom max_results."""
        with patch('hackathon_science.tools.DDGS') as mock_ddgs_class:
            mock_ddgs = Mock()
            mock_ddgs.text.return_value = []
            mock_ddgs_class.return_value = mock_ddgs

            results = search_web("test query", max_results=5)

            mock_ddgs.text.assert_called_once_with("test query", max_results=5)

    def test_search_web_multiple_results(self):
        """Test that search_web handles multiple results."""
        with patch('hackathon_science.tools.DDGS') as mock_ddgs_class:
            mock_ddgs = Mock()
            mock_ddgs.text.return_value = [
                {
                    'title': 'Result 1',
                    'href': 'https://example1.com',
                    'body': 'Snippet 1'
                },
                {
                    'title': 'Result 2',
                    'href': 'https://example2.com',
                    'body': 'Snippet 2'
                }
            ]
            mock_ddgs_class.return_value = mock_ddgs

            results = search_web("test query")

            assert len(results) == 2
            assert results[0]['title'] == 'Result 1'
            assert results[1]['title'] == 'Result 2'

    def test_search_web_empty_results(self):
        """Test that search_web handles empty results."""
        with patch('hackathon_science.tools.DDGS') as mock_ddgs_class:
            mock_ddgs = Mock()
            mock_ddgs.text.return_value = []
            mock_ddgs_class.return_value = mock_ddgs

            results = search_web("test query")

            assert results == []

    def test_search_web_handles_errors(self):
        """Test that search_web handles search errors."""
        with patch('hackathon_science.tools.DDGS') as mock_ddgs_class:
            mock_ddgs = Mock()
            mock_ddgs.text.side_effect = Exception("Search failed")
            mock_ddgs_class.return_value = mock_ddgs

            with pytest.raises(Exception, match="Search failed"):
                search_web("test query")


class TestGetPaper:
    """Tests for get_paper function."""

    def test_get_paper_returns_paper_dict(self, tmp_path):
        """Test that get_paper returns paper as dict."""
        papers_dir = tmp_path / "papers"
        papers_dir.mkdir()

        paper_content = """---
id: paper123
title: Test Paper
author: John Doe
date: 2024-01-15
introduction: Abstract text
tags:
  - AI
---

## Methods
Methods text

## Results
Results text

## Conclusion
Conclusion text
"""
        (papers_dir / "paper123.md").write_text(paper_content)

        result = get_paper("paper123", tmp_path)

        assert result is not None
        assert result['id'] == 'paper123'
        assert result['title'] == 'Test Paper'
        assert result['author'] == 'John Doe'
        assert result['introduction'] == 'Abstract text'
        assert result['methods'] == 'Methods text'
        assert result['results'] == 'Results text'

    def test_get_paper_returns_none_for_nonexistent_paper(self, tmp_path):
        """Test that get_paper returns None for nonexistent paper ID."""
        papers_dir = tmp_path / "papers"
        papers_dir.mkdir()

        result = get_paper("nonexistent", tmp_path)

        assert result is None

    def test_get_paper_searches_multiple_papers(self, tmp_path):
        """Test that get_paper searches through multiple papers."""
        papers_dir = tmp_path / "papers"
        papers_dir.mkdir()

        paper1 = """---
id: paper1
title: Paper 1
author: Author 1
date: 2024-01-15
introduction: Abstract 1
tags: []
---

## Methods
Methods 1

## Results
Results 1

## Conclusion
Conclusion 1
"""
        paper2 = """---
id: paper2
title: Paper 2
author: Author 2
date: 2024-01-16
introduction: Abstract 2
tags: []
---

## Methods
Methods 2

## Results
Results 2

## Conclusion
Conclusion 2
"""
        (papers_dir / "paper1.md").write_text(paper1)
        (papers_dir / "paper2.md").write_text(paper2)

        result = get_paper("paper2", tmp_path)

        assert result is not None
        assert result['id'] == 'paper2'
        assert result['title'] == 'Paper 2'

    def test_get_paper_returns_all_fields(self, tmp_path):
        """Test that get_paper returns all paper fields."""
        papers_dir = tmp_path / "papers"
        papers_dir.mkdir()

        paper_content = """---
id: paper123
title: Full Paper
author: Jane Smith
date: 2024-01-15
introduction: Abstract
tags:
  - ML
  - AI
  - paper456
---

## Methods
Methods

## Results
Results

## Conclusion
Conclusion
"""
        (papers_dir / "paper123.md").write_text(paper_content)

        result = get_paper("paper123", tmp_path)

        assert result is not None
        assert 'id' in result
        assert 'title' in result
        assert 'author' in result
        assert 'date' in result
        assert 'tags' in result
        assert 'introduction' in result
        assert 'methods' in result
        assert 'results' in result
        assert result['tags'] == ['ML', 'AI', 'paper456']

    def test_get_paper_no_papers_directory(self, tmp_path):
        """Test that get_paper handles missing papers directory."""
        result = get_paper("paper123", tmp_path)

        assert result is None
