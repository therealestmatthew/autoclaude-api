#!/usr/bin/env bash
# scout-clone-runner entrypoint.
#
# Reads REPO_URL from env. Clones shallow, walks the allowlist, builds a tar
# of allowlisted files (plus a manifest.json) and writes it to stdout. Exits
# nonzero if the clone fails or caps are exceeded. NEVER executes anything
# from the cloned repo — this script only reads files, hashes bytes, and
# writes a tar.
set -euo pipefail

: "${REPO_URL:?REPO_URL env var is required}"

CLONE_DIR=/work/clone
OUT_DIR=/work/out
MAX_FILE_BYTES=$((1 * 1024 * 1024))      # 1 MB
MAX_TOTAL_BYTES=$((100 * 1024 * 1024))   # 100 MB
MAX_FILE_COUNT=5000

mkdir -p "$OUT_DIR"

# Status / warnings go to stderr; tar bytes go to stdout. Don't mix.
log() { printf '%s\n' "$*" >&2; }

log "[clone-runner] cloning $REPO_URL"
git clone \
  --depth 1 \
  --no-tags \
  --filter=blob:none \
  --no-recurse-submodules \
  --quiet \
  "$REPO_URL" "$CLONE_DIR" >&2

cd "$CLONE_DIR"
COMMIT_SHA=$(git rev-parse HEAD)
log "[clone-runner] HEAD=$COMMIT_SHA"

# Path allowlist. Anchored to clone root. We do this in two passes:
#   1. find candidates by name pattern;
#   2. enforce per-file size + total size + file count + symlink-escape caps.
#
# `find -L` is intentionally NOT used; we want to detect (and reject) symlinks
# rather than follow them.
CANDIDATES_FILE=$(mktemp -p /work)
trap 'rm -f "$CANDIDATES_FILE"' EXIT

# Directory allowlist: .claude/, agents/, skills/, prompts/.
find . -type f \( \
  -path './.claude/*' -o \
  -path './agents/*' -o \
  -path './skills/*' -o \
  -path './prompts/*' \
\) -print >> "$CANDIDATES_FILE"

# Top-level file allowlist: mcp.json, README*, LICENSE*, *.md.
find . -maxdepth 1 -type f \( \
  -name 'mcp.json' -o \
  -name 'README*' -o \
  -name 'LICENSE*' -o \
  -name '*.md' \
\) -print >> "$CANDIDATES_FILE"

# Reject symlinks anywhere under the allowlisted dirs (defense in depth; the
# host re-validates).
SYMLINKS=$(find . -type l \( \
  -path './.claude/*' -o \
  -path './agents/*' -o \
  -path './skills/*' -o \
  -path './prompts/*' \
\) -print | head -1 || true)
if [ -n "$SYMLINKS" ]; then
  log "[clone-runner] SECURITY: symlink found at $SYMLINKS — aborting"
  exit 2
fi

# De-dup candidates and sort for determinism.
sort -u "$CANDIDATES_FILE" -o "$CANDIDATES_FILE"

TOTAL_BYTES=0
FILE_COUNT=0
KEPT_FILE=$(mktemp -p /work)
MANIFEST=$(mktemp -p /work)
WARNINGS=$(mktemp -p /work)
trap 'rm -f "$CANDIDATES_FILE" "$KEPT_FILE" "$MANIFEST" "$WARNINGS"' EXIT

printf '{"repo_url":"%s","commit_sha":"%s","files":[' \
  "$REPO_URL" "$COMMIT_SHA" >> "$MANIFEST"
FIRST=1

while IFS= read -r path; do
  # Strip leading ./ for cleaner relpaths.
  rel=${path#./}

  # Hard count cap.
  FILE_COUNT=$((FILE_COUNT + 1))
  if [ "$FILE_COUNT" -gt "$MAX_FILE_COUNT" ]; then
    log "[clone-runner] WARN: file count cap ($MAX_FILE_COUNT) exceeded; truncating"
    printf 'file-count-cap-exceeded\n' >> "$WARNINGS"
    break
  fi

  # Per-file size cap.
  size=$(stat -c '%s' "$path" 2>/dev/null || echo 0)
  if [ "$size" -gt "$MAX_FILE_BYTES" ]; then
    log "[clone-runner] WARN: skipping oversize file $rel ($size bytes)"
    printf 'skipped-oversize:%s\n' "$rel" >> "$WARNINGS"
    continue
  fi

  # Cumulative size cap.
  new_total=$((TOTAL_BYTES + size))
  if [ "$new_total" -gt "$MAX_TOTAL_BYTES" ]; then
    log "[clone-runner] WARN: total size cap ($MAX_TOTAL_BYTES) exceeded; truncating"
    printf 'total-size-cap-exceeded\n' >> "$WARNINGS"
    break
  fi
  TOTAL_BYTES=$new_total

  sha=$(sha256sum "$path" | cut -d' ' -f1)
  printf '%s\n' "$rel" >> "$KEPT_FILE"
  if [ "$FIRST" -eq 1 ]; then FIRST=0; else printf ',' >> "$MANIFEST"; fi
  printf '{"relpath":"%s","size":%d,"sha256":"%s"}' \
    "$rel" "$size" "$sha" >> "$MANIFEST"
done < "$CANDIDATES_FILE"

# Warnings array.
printf '],"warnings":[' >> "$MANIFEST"
FIRST=1
if [ -s "$WARNINGS" ]; then
  while IFS= read -r w; do
    if [ "$FIRST" -eq 1 ]; then FIRST=0; else printf ',' >> "$MANIFEST"; fi
    printf '"%s"' "$w" >> "$MANIFEST"
  done < "$WARNINGS"
fi
printf ']}\n' >> "$MANIFEST"

cp "$MANIFEST" "$OUT_DIR/manifest.json"

log "[clone-runner] kept $(wc -l < "$KEPT_FILE" | tr -d ' ') files, ${TOTAL_BYTES} bytes total"

# Tar (kept files + manifest.json) → stdout.
# `tar -T -` reads file list from stdin. Manifest goes in under a fixed name.
cp "$MANIFEST" "$CLONE_DIR/.scout-manifest.json"
printf '.scout-manifest.json\n' >> "$KEPT_FILE"
tar -c --no-recursion -T "$KEPT_FILE"
