"""Security helpers: sanitize untrusted content, validate URLs, bound GETs.

The threat model and rules live in /conventions/security.md. This module is the
toolkit those rules require. Every extractor uses these helpers; raw
`client.get()` and unsanitized strings have no place in extractor code.

Three pieces:

- `sanitize_text(s, max_length=)` — strip dangerous Unicode, NFC-normalize,
  collapse whitespace, length-cap.
- `safe_external_url(url)` — http(s) only, public hosts only (no loopback,
  no RFC 1918, no link-local, no IPv6 ULA / loopback / link-local).
- `safe_get_bytes(client, url, max_bytes=)` — URL-validated, size-bounded GET
  that re-checks the URL after redirects. Returns bytes. Caller decodes.

We export two exception types so callers can surface clean errors:

- `UnsafeURLError` — raised pre-request or post-redirect when a URL fails
  `safe_external_url`.
- `ResponseTooLargeError` — raised when a streamed response exceeds the cap.
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit

import httpx

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SecurityError(Exception):
    """Base class for security-policy failures."""


class UnsafeURLError(SecurityError):
    """The URL is not safe to fetch (non-http(s), private host, malformed)."""


class ResponseTooLargeError(SecurityError):
    """The response exceeded the configured byte cap."""


# ---------------------------------------------------------------------------
# sanitize_text
# ---------------------------------------------------------------------------

_ALLOWED_CONTROL = frozenset("\t\n\r")
_WHITESPACE_RUN = re.compile(r"[ \t]+")
_NEWLINE_RUN = re.compile(r"\n{3,}")


def sanitize_text(s: object, max_length: int | None = None) -> str:
    """Sanitize free-form text for safe storage and later display.

    Steps:
      1. Coerce None / non-str to str.
      2. Strip Unicode category-C codepoints (control / format / surrogate /
         private-use / unassigned) **except** tab, newline, carriage return.
         This drops bidi overrides (U+202A–202E, U+2066–2069), zero-width
         joiners (U+200B–200F, U+FEFF), null bytes, surrogate halves, and
         private-use chars that can hide prompt-injection payloads.
      3. NFC-normalize (so visually-identical strings compare equal).
      4. Collapse runs of spaces / tabs to a single space; collapse 3+ newlines
         to a paragraph break (\\n\\n).
      5. Strip leading and trailing whitespace.
      6. Optional length cap — silent truncation; no marker is appended so the
         output is still valid as a slug source.
    """
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)

    # Step 2: strip dangerous category-C codepoints.
    cleaned_chars: list[str] = []
    for c in s:
        if unicodedata.category(c).startswith("C") and c not in _ALLOWED_CONTROL:
            continue
        cleaned_chars.append(c)
    cleaned = "".join(cleaned_chars)

    # Step 3: NFC normalize.
    cleaned = unicodedata.normalize("NFC", cleaned)

    # Step 4: collapse whitespace runs (preserve paragraph structure).
    cleaned = _WHITESPACE_RUN.sub(" ", cleaned)
    cleaned = _NEWLINE_RUN.sub("\n\n", cleaned)

    # Step 5: strip outer whitespace.
    cleaned = cleaned.strip()

    # Step 6: length cap.
    if max_length is not None and len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()

    return cleaned


# ---------------------------------------------------------------------------
# safe_external_url
# ---------------------------------------------------------------------------

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def safe_external_url(url: object) -> bool:
    """True iff `url` is http(s) and the host is **not** loopback / private /
    link-local / reserved.

    Hostnames (e.g. `localhost`) are matched literally; IPs (v4 and v6) are
    checked via the ipaddress module. Anything we can't parse confidently is
    treated as unsafe.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        return False
    host = (parts.hostname or "").strip()
    if not host:
        return False

    lowered = host.lower()
    if lowered in {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}:
        return False
    # Some shenanigans: hostnames that resolve to private space. We can't
    # resolve at this layer without DNS — but for our scout's scope, callers
    # should pin endpoints to known public services. Hostname-based bypasses
    # remain a known residual risk; document in /conventions/security.md if
    # we ever add resolver-aware checking.

    # IP address check
    try:
        ip = ipaddress.ip_address(lowered.strip("[]"))
    except ValueError:
        # Not an IP literal — treat as a public hostname.
        return True
    return not (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


# ---------------------------------------------------------------------------
# safe_get_bytes
# ---------------------------------------------------------------------------

DEFAULT_MAX_BYTES = 10 * 1024 * 1024   # 10 MiB


def safe_get_bytes(
    client: httpx.Client,
    url: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    params: dict[str, str] | None = None,
) -> bytes:
    """URL-validated, size-bounded GET.

    Raises `UnsafeURLError` if the URL fails `safe_external_url` either pre-
    request or after redirects, or `ResponseTooLargeError` if the streamed
    body exceeds `max_bytes`. Other httpx errors propagate.

    Returns the response body as bytes; callers decode (`.decode("utf-8",
    errors="replace")`) or json-parse as appropriate.
    """
    if not safe_external_url(url):
        raise UnsafeURLError(url)

    chunks: list[bytes] = []
    total = 0

    with client.stream("GET", url, params=params) as resp:
        resp.raise_for_status()

        # Re-check the final URL after any redirects.
        final_url = str(resp.url)
        if not safe_external_url(final_url):
            raise UnsafeURLError(f"redirect to {final_url}")

        # Pre-flight: if the server tells us the size and it's too big, fail
        # before reading the body.
        content_length = resp.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > max_bytes:
            raise ResponseTooLargeError(
                f"{url}: content-length={content_length} > {max_bytes}"
            )

        for chunk in resp.iter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise ResponseTooLargeError(
                    f"{url}: body exceeded {max_bytes} bytes"
                )
            chunks.append(chunk)

    return b"".join(chunks)
