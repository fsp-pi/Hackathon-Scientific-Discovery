"""Data models for Papers."""

from dataclasses import dataclass, field


@dataclass
class Paper:
    """Represents a scientific paper."""

    title: str
    introduction: str
    methods: str
    results: str
    references: str = ""
    appendix: str = ""
    id: str = ""
    author: str = ""
    date: str = ""
    tags: list[str] = field(default_factory=list)
