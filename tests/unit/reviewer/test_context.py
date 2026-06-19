"""Tests for scout/reviewer/context.py — context retrieval and scoring."""



from scout.reviewer.context import _score, _tokenize, get_context


class TestTokenize:
    def test_lowercases(self):
        assert _tokenize("Claude Code") == {"claude", "code"}

    def test_splits_on_non_alnum(self):
        assert "aws" in _tokenize("aws-bedrock-integration")
        assert "bedrock" in _tokenize("aws-bedrock-integration")

    def test_empty(self):
        assert _tokenize("") == set()


class TestScore:
    def test_exact_title_match_scores_high(self):
        candidate_tokens = {"claude", "cookbooks"}
        item = {"title": "Claude Cookbooks", "slug": "claude-cookbooks", "tags": []}
        score = _score(candidate_tokens, set(), item)
        assert score > 1.0

    def test_tag_overlap_adds_score(self):
        candidate_tags = {"aws", "bedrock"}
        item = {"title": "Something Else", "slug": "something-else", "tags": ["aws", "bedrock"]}
        score_with_tags = _score(set(), candidate_tags, item)
        score_no_tags = _score(set(), set(), item)
        assert score_with_tags > score_no_tags

    def test_zero_score_unrelated(self):
        candidate_tokens = {"completely", "unrelated"}
        item = {"title": "XYZ QRS", "slug": "xyz-qrs", "tags": ["abc"]}
        score = _score(candidate_tokens, set(), item)
        assert score == 0.0


class TestGetContext:
    def test_returns_empty_for_empty_catalog(self, tmp_path):
        results = get_context("Claude Code", ["ai"], catalog_dir=tmp_path)
        assert results == []

    def test_returns_relevant_items(self, tmp_path):
        (tmp_path / "anthropic.md").write_text(
            "---\nslug: anthropic\ntitle: Anthropic\nkind: org\n"
            "tags: [ai, safety]\n---\nAI safety lab.\n"
        )
        (tmp_path / "unrelated.md").write_text(
            "---\nslug: unrelated\ntitle: Cooking Recipes\nkind: article\n"
            "tags: [food]\n---\nSome food content.\n"
        )
        results = get_context("Anthropic AI safety", ["ai", "safety"], catalog_dir=tmp_path)
        slugs = [r["slug"] for r in results]
        assert "anthropic" in slugs

    def test_skips_schema_files(self, tmp_path):
        (tmp_path / "_schema.md").write_text(
            "---\nslug: _schema\ntitle: Schema\n---\n"
        )
        results = get_context("anything", [], catalog_dir=tmp_path)
        assert all(r["slug"] != "_schema" for r in results)

    def test_top_n_limit(self, tmp_path):
        for i in range(10):
            (tmp_path / f"item-{i}.md").write_text(
                f"---\nslug: item-{i}\ntitle: Claude Tool {i}\nkind: tool\ntags: [claude]\n---\n"
            )
        results = get_context("Claude Tool", ["claude"], top_n=3, catalog_dir=tmp_path)
        assert len(results) <= 3
