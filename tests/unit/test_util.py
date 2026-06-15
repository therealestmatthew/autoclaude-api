"""Tests for scout/_util.py — slugify, canonical_github_url, parse_frontmatter."""

from scout._util import canonical_github_url, parse_frontmatter, slugify


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_strips_punctuation(self):
        assert slugify("Claude Code: Best Practices!") == "claude-code-best-practices"

    def test_collapses_spaces_and_dashes(self):
        assert slugify("foo   bar---baz") == "foo-bar-baz"

    def test_strips_leading_trailing_dashes(self):
        assert slugify("---hello---") == "hello"

    def test_empty_input(self):
        assert slugify("") == "unnamed"

    def test_only_punctuation(self):
        assert slugify("!!!") == "unnamed"

    def test_unicode_dropped(self):
        # Non-ASCII alphanumerics collapse into dashes; we ASCII-only by design.
        out = slugify("Café Résumé")
        assert out == "caf-r-sum"

    def test_max_length(self):
        out = slugify("a" * 200)
        assert len(out) <= 60

    def test_truncation_trims_trailing_dash(self):
        # If max_length lands mid-collapse, the trailing dash gets trimmed.
        out = slugify("aaa bbb ccc", max_length=4)
        assert out == "aaa"


class TestCanonicalGithubUrl:
    def test_plain_repo(self):
        assert canonical_github_url("https://github.com/foo/bar") == "https://github.com/foo/bar"

    def test_strips_trailing_slash(self):
        assert canonical_github_url("https://github.com/foo/bar/") == "https://github.com/foo/bar"

    def test_strips_tree_path(self):
        assert (
            canonical_github_url("https://github.com/foo/bar/tree/main/skills/x")
            == "https://github.com/foo/bar"
        )

    def test_strips_blob_path(self):
        assert (
            canonical_github_url("https://github.com/foo/bar/blob/main/README.md")
            == "https://github.com/foo/bar"
        )

    def test_strips_dot_git(self):
        assert canonical_github_url("https://github.com/foo/bar.git") == "https://github.com/foo/bar"

    def test_non_github_passthrough(self):
        assert canonical_github_url("https://example.com/foo") == "https://example.com/foo"

    def test_non_github_trims_trailing_slash(self):
        assert canonical_github_url("https://example.com/foo/") == "https://example.com/foo"


class TestParseFrontmatter:
    def test_basic(self):
        text = "---\nname: foo\nkind: agent\n---\n\nbody"
        out = parse_frontmatter(text)
        assert out == {"name": "foo", "kind": "agent"}

    def test_no_frontmatter(self):
        assert parse_frontmatter("just a body, no fences") == {}

    def test_no_closing_fence(self):
        assert parse_frontmatter("---\nname: foo\nstill in fence") == {}

    def test_malformed_yaml(self):
        # Unterminated quoted string inside frontmatter — yaml raises, we swallow.
        assert parse_frontmatter("---\nname: \"unterminated\n---\n") == {}

    def test_non_dict_yaml(self):
        # A bare list in frontmatter — not what we want; return empty dict.
        assert parse_frontmatter("---\n- foo\n- bar\n---\n") == {}

    def test_nested(self):
        text = (
            "---\n"
            "name: foo\n"
            "source:\n"
            "  url: https://example.com\n"
            "  alternates:\n"
            "    - url: https://other.example\n"
            "---\nbody"
        )
        out = parse_frontmatter(text)
        assert out["source"]["url"] == "https://example.com"
        assert out["source"]["alternates"][0]["url"] == "https://other.example"
