"""Code analysis module.

Provides standalone analyzers and an orchestrator for comprehensive code quality analysis.

Analyzers:
- complexity: Lizard complexity analysis
- style: flake8 style checking
- formatting: Black formatting verification
- types: mypy type checking
- file_length: File length analysis for AI-friendly architecture

Each analyzer can be run standalone or orchestrated via core.main().
"""

from .complexity import analyze_complexity
from .style import analyze_style
from .formatting import analyze_formatting
from .types import analyze_types
from .file_length import analyze_file_length

__all__ = [
    "analyze_complexity",
    "analyze_style",
    "analyze_formatting",
    "analyze_types",
    "analyze_file_length",
]
