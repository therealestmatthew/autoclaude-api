"""Adversarial coverage of scout/_security.py.

The module is the security toolkit every extractor depends on; if these tests
go red, the whole ingest pipeline is unsafe. Treat this file as a contract,
not as a behavioral snapshot.
"""

from __future__ import annotations

import httpx
import pytest

from scout._security import (
    DEFAULT_MAX_BYTES,
    ResponseTooLargeError,
    UnsafeURLError,
    safe_external_url,
    safe_get_bytes,
    sanitize_text,
)

# ---------------------------------------------------------------------------
# sanitize_text
# ---------------------------------------------------------------------------

class TestSanitizeText:
    def test_strips_null_bytes(self):
        assert sanitize_text("hello\x00world") == "helloworld"

    def test_strips_bidi_overrides(self):
        # U+202E RIGHT-TO-LEFT OVERRIDE inside a benign string.
        s = "innocent‮title"
        out = sanitize_text(s)
        assert "‮" not in out
        assert out == "innocenttitle"

    def test_strips_other_bidi_chars(self):
        # U+202A..202E and U+2066..2069 are all control format chars (Cf).
        s = "a‪b‫c⁦d⁩e"
        out = sanitize_text(s)
        for ch in ("‪", "‫", "⁦", "⁩"):
            assert ch not in out
        assert out == "abcde"

    def test_strips_zero_width(self):
        s = "vis​ible‌word‍"
        out = sanitize_text(s)
        for ch in ("​", "‌", "‍"):
            assert ch not in out

    def test_strips_byte_order_mark(self):
        assert sanitize_text("﻿hello") == "hello"

    def test_strips_surrogate_halves(self):
        # Build a string containing an unpaired surrogate via chr().
        s = "ok" + chr(0xD800) + "x"
        out = sanitize_text(s)
        assert chr(0xD800) not in out
        assert out == "okx"

    def test_strips_private_use_area(self):
        s = "testend"
        out = sanitize_text(s)
        assert "" not in out
        assert out == "testend"

    def test_preserves_newline_and_carriage_return(self):
        # Newline + carriage return survive sanitization. Tabs are *kept* (not
        # stripped as control chars) but the whitespace-collapse rule then
        # folds them into a single space; that's the contract — paragraph
        # structure preserved, column structure not.
        s = "line1\nline2\rline3"
        out = sanitize_text(s)
        assert "\n" in out
        assert "\r" in out

    def test_tab_is_not_stripped_as_control_char(self):
        # Tab is in the allowlist, so a tab between two non-whitespace tokens
        # collapses to a single space (not deleted).
        assert sanitize_text("a\tb") == "a b"

    def test_collapses_space_and_tab_runs(self):
        assert sanitize_text("a    b\t\tc \t d") == "a b c d"

    def test_collapses_three_or_more_newlines(self):
        assert sanitize_text("a\n\n\n\n\nb") == "a\n\nb"
        # Two newlines stay as two.
        assert sanitize_text("a\n\nb") == "a\n\nb"

    def test_nfc_normalizes(self):
        # "café" composed vs decomposed should be equal after sanitize.
        composed = "café"          # é as one codepoint
        decomposed = "café"       # e + combining acute
        assert sanitize_text(composed) == sanitize_text(decomposed) == "café"

    def test_none_returns_empty_string(self):
        assert sanitize_text(None) == ""

    def test_non_string_is_coerced(self):
        assert sanitize_text(42) == "42"
        assert sanitize_text(["a", "b"]) == "['a', 'b']"

    def test_silent_truncate_at_max_length(self):
        s = "x" * 500
        out = sanitize_text(s, max_length=100)
        assert len(out) == 100
        # No truncation marker — output is bare.
        assert "…" not in out
        assert "..." not in out

    def test_truncate_strips_trailing_whitespace(self):
        # If the cut lands in a run of spaces, strip them.
        s = "abc" + " " * 50
        out = sanitize_text(s, max_length=10)
        assert out == "abc"

    def test_strips_outer_whitespace(self):
        assert sanitize_text("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# safe_external_url
# ---------------------------------------------------------------------------

class TestSafeExternalURL:
    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com",
            "https://example.com/",
            "https://github.com/foo/bar",
            "http://example.com:8080/path",
            "https://api.example.org/v1/resource?x=1",
        ],
    )
    def test_allows_public_http(self, url: str):
        assert safe_external_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "javascript:alert(1)",
            "file:///etc/passwd",
            "ftp://example.com/x",
            "data:text/html,<script>x</script>",
        ],
    )
    def test_rejects_dangerous_schemes(self, url: str):
        assert safe_external_url(url) is False

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/",
            "http://localhost.localdomain/",
            "http://127.0.0.1/",
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://172.16.0.5/",
            "http://169.254.169.254/latest/",   # AWS / cloud metadata
        ],
    )
    def test_rejects_private_ipv4(self, url: str):
        assert safe_external_url(url) is False

    @pytest.mark.parametrize(
        "url",
        [
            "http://[::1]/",
            "http://[fe80::1]/",
        ],
    )
    def test_rejects_private_ipv6(self, url: str):
        assert safe_external_url(url) is False

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "not a url",
            "https://",
            "://nohost",
        ],
    )
    def test_rejects_malformed(self, url: str):
        assert safe_external_url(url) is False

    def test_rejects_non_string(self):
        assert safe_external_url(None) is False
        assert safe_external_url(42) is False


# ---------------------------------------------------------------------------
# safe_get_bytes
# ---------------------------------------------------------------------------

def _mock_client(handler) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    )


class TestSafeGetBytes:
    def test_returns_bytes_on_normal_response(self):
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"payload")

        client = _mock_client(handler)
        out = safe_get_bytes(client, "https://example.com/x")
        assert out == b"payload"

    def test_rejects_unsafe_url_pre_request(self):
        # Use a handler that would raise if it were ever called, to prove the
        # rejection happens before any network call.
        def handler(req: httpx.Request) -> httpx.Response:
            raise AssertionError("handler should not be invoked")

        client = _mock_client(handler)
        with pytest.raises(UnsafeURLError):
            safe_get_bytes(client, "http://127.0.0.1/secret")

    def test_rejects_redirect_to_private_ip(self):
        # First hit on the public URL → 301 to 127.0.0.1. httpx follows it,
        # and safe_get_bytes re-checks the final URL.
        def handler(req: httpx.Request) -> httpx.Response:
            host = req.url.host
            if host == "example.com":
                return httpx.Response(
                    301, headers={"location": "http://127.0.0.1/leak"}
                )
            return httpx.Response(200, content=b"should not get here")

        client = _mock_client(handler)
        with pytest.raises(UnsafeURLError):
            safe_get_bytes(client, "https://example.com/start")

    def test_rejects_when_content_length_exceeds_max(self):
        # Server promises a huge body via content-length.
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-length": str(DEFAULT_MAX_BYTES + 1)},
                content=b"x",
            )

        client = _mock_client(handler)
        with pytest.raises(ResponseTooLargeError):
            safe_get_bytes(client, "https://example.com/big", max_bytes=100)

    def test_rejects_when_streamed_body_exceeds_max(self):
        # No content-length header but the actual body is too large.
        big_body = b"x" * 1000

        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=big_body)

        client = _mock_client(handler)
        with pytest.raises(ResponseTooLargeError):
            safe_get_bytes(client, "https://example.com/big", max_bytes=100)

    def test_passes_params_through(self):
        captured = {}

        def handler(req: httpx.Request) -> httpx.Response:
            captured["query"] = dict(req.url.params)
            return httpx.Response(200, content=b"ok")

        client = _mock_client(handler)
        out = safe_get_bytes(
            client,
            "https://example.com/search",
            params={"q": "claude", "limit": "10"},
        )
        assert out == b"ok"
        assert captured["query"] == {"q": "claude", "limit": "10"}
