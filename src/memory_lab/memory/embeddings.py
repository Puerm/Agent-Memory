"""A replaceable, deterministic semantic-similarity adapter.

The first version intentionally has no network or local model dependency.  Its
token-overlap score keeps every retrieval decision repeatable and inspectable.
"""

from __future__ import annotations

import re


def tokenize(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z_]+", text) if len(token) > 1}


def similarity(query: str, document: str) -> float:
    query_tokens = tokenize(query)
    document_tokens = tokenize(document)
    if not query_tokens or not document_tokens:
        return 0.0
    return round(len(query_tokens & document_tokens) / len(query_tokens | document_tokens), 4)


def estimate_tokens(text: str) -> int:
    return max(1, len(re.findall(r"\S+", text))) if text.strip() else 0
