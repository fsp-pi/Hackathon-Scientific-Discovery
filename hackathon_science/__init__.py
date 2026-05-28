"""Hackathon Scientific Discovery Platform."""

from hackathon_science.models import Paper
from hackathon_science.utils import call_llm
from hackathon_science.tools import run_code, search_web, get_paper, image_to_base64

__version__ = "0.1.0"
__all__ = ["Paper", "call_llm", "run_code", "search_web", "get_paper", "image_to_base64"]
