"""Round-trip serialisation between markdown documents and the
frontmatter dict + body parts the editor uses.

We use ruamel.yaml? No — keeping the dep list small. PyYAML covers
the round-trip; we lose YAML comments on rewrite (acceptable; the
catalog convention has no important comments inside frontmatter
blocks). Block style is preserved by passing `default_flow_style=False`.
"""

from __future__ import annotations

from typing import Any

import yaml


def split_document(text: str) -> tuple[str, str]:
    """Split a markdown document into (frontmatter_yaml, body).

    Returns ('', body) if the document has no frontmatter — callers
    should treat that as missing and either reject or auto-add.
    """
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    frontmatter = parts[1].strip("\n")
    body = parts[2].lstrip("\n")
    return frontmatter, body


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse frontmatter from a full document. Returns {} on absence
    or parse failure (callers can distinguish via the trailing
    `issues` channel; we don't here)."""
    fm_text, _ = split_document(text)
    if not fm_text:
        return {}
    try:
        parsed = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_body(text: str) -> str:
    _, body = split_document(text)
    return body


def render_document(frontmatter: dict[str, Any], body: str) -> str:
    """Render a full markdown document.

    Frontmatter is YAML in block style with sort_keys=False to preserve
    intentional ordering. The body is appended verbatim with a single
    newline separator after the closing `---`.
    """
    fm_yaml = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10_000,  # don't wrap long URLs
    ).rstrip("\n")
    if not body.endswith("\n"):
        body = body + "\n"
    return f"---\n{fm_yaml}\n---\n\n{body}"


def replace_frontmatter(text: str, frontmatter: dict[str, Any]) -> str:
    """Replace the frontmatter of an existing document, preserving body."""
    body = parse_body(text)
    return render_document(frontmatter, body)


def replace_body(text: str, body: str) -> str:
    """Replace the body, preserving frontmatter (re-rendered from parse)."""
    fm = parse_frontmatter(text)
    return render_document(fm, body)
