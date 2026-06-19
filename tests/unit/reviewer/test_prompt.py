"""Tests for scout/reviewer/prompt.py — deterministic prompt assembly."""

from scout.reviewer.prompt import build_messages, build_system_blocks


class TestBuildSystemBlocks:
    def test_returns_three_blocks(self):
        blocks = build_system_blocks()
        assert len(blocks) == 3

    def test_all_blocks_have_cache_control(self):
        blocks = build_system_blocks()
        for block in blocks:
            assert block.get("cache_control") == {"type": "ephemeral"}

    def test_first_block_is_system_text(self):
        blocks = build_system_blocks()
        assert "emit_decision" in blocks[0]["text"]
        assert "keep" in blocks[0]["text"]

    def test_second_block_contains_merge_rules(self):
        blocks = build_system_blocks()
        assert "merge" in blocks[1]["text"].lower()
        assert "<rules>" in blocks[1]["text"]

    def test_third_block_contains_schema(self):
        blocks = build_system_blocks()
        assert "<schema>" in blocks[2]["text"]

    def test_deterministic(self):
        assert build_system_blocks() == build_system_blocks()


class TestBuildMessages:
    def test_basic_structure(self):
        messages = build_messages(
            candidate_text="slug: foo\ntitle: Foo Bar",
            context_items=[],
        )
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        content = messages[0]["content"]
        assert any("Foo Bar" in p.get("text", "") for p in content)

    def test_with_context_items(self):
        items = [
            {"slug": "anthropic", "title": "Anthropic", "kind": "org",
             "status": "reviewed", "tags": ["ai"], "body_excerpt": "AI safety company."}
        ]
        messages = build_messages("slug: foo\ntitle: Foo", items)
        joined = " ".join(p.get("text", "") for p in messages[0]["content"])
        assert "anthropic" in joined
        assert "Nearby catalog" in joined

    def test_with_dedup_hints(self):
        messages = build_messages(
            "slug: foo\ntitle: Foo",
            context_items=[],
            dedup_hints={"mergeset_id": "ms-abc123", "duplicates_via_url": "none"},
        )
        joined = " ".join(p.get("text", "") for p in messages[0]["content"])
        assert "ms-abc123" in joined

    def test_with_liveness_hints(self):
        messages = build_messages(
            "slug: foo\ntitle: Foo",
            context_items=[],
            liveness_hints={"url_status": "404", "error_404_count": 3},
        )
        joined = " ".join(p.get("text", "") for p in messages[0]["content"])
        assert "404" in joined

    def test_no_context_no_extra_parts(self):
        messages = build_messages("slug: foo\ntitle: Foo", context_items=[])
        # Should have exactly 1 part (the candidate text)
        assert len(messages[0]["content"]) == 1
