"""Parse LLM responses for file proposals and present them for user confirmation.

When the LLM suggests creating or modifying files, it uses fenced code blocks
with the file path as the info string. This module parses those blocks and
implements a propose-then-confirm workflow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FileProposal:
    """A proposed file write extracted from an LLM response."""

    path: str
    content: str


_FENCE_PATTERN = re.compile(
    r"```(\S+)\n(.*?)```",
    re.DOTALL,
)

# File-like path patterns (must contain a slash or dot to distinguish from language tags)
_PATH_LIKE = re.compile(r"[./]")


def parse_proposals(response: str) -> list[FileProposal]:
    """Extract file proposals from fenced code blocks in an LLM response.

    A fenced block is treated as a file proposal if its info string looks like
    a file path (contains '/' or '.'). Plain language tags like ``sql`` or
    ``python`` are ignored.
    """
    proposals = []
    for match in _FENCE_PATTERN.finditer(response):
        info_string = match.group(1)
        content = match.group(2)
        if _PATH_LIKE.search(info_string):
            proposals.append(FileProposal(path=info_string, content=content))
    return proposals
