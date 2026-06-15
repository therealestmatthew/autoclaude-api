---
name: scout-clone-runner-readme
title: "scout-clone-runner"
kind: readme
status: active
updated_at: 2026-06-15
---

# scout-clone-runner

The per-clone sandbox image for the Phase 4 repo extractor. Built locally
on first use; never pulled from a registry.

## What it is

A minimal Alpine + git image whose entrypoint:

1. Reads `$REPO_URL`.
2. `git clone --depth 1 --no-tags --filter=blob:none --no-recurse-submodules`.
3. Walks an allowlist of paths (`.claude/`, `agents/`, `skills/`,
   `prompts/`, top-level `README*`, `LICENSE*`, `*.md`, `mcp.json`).
4. Rejects any symlink found inside the allowlisted dirs.
5. Enforces per-file (1 MB), total (100 MB), and count (5000) caps.
6. Writes a tar of allowlisted files to **stdout**, plus a
   `.scout-manifest.json` describing each file (relpath, size, sha256, and
   the commit SHA / repo URL the clone was made from).

Status / warnings go to **stderr** so they never collide with the tar bytes
on stdout.

The host (`scout/_container.py`, `scout/extractors/repo.py`) runs this image
with a locked set of flags — read-only root, tmpfs `/work`, `--cap-drop ALL`,
`--security-opt no-new-privileges`, `--pids-limit 256`, non-root uid
`65532`. The canonical flag list lives in `conventions/security.md` under
"Container flags (canonical)".

## Build

```sh
# v1 builds locally — no registry dependency.
docker build -t scout-clone-runner scout/clone_runner/
```

`RepoExtractor` builds it on first invocation if a `scout-clone-runner`
image is not already present locally.

## Why so spartan

The container is the boundary. The image stays small (`apk add` is the
only customization on top of `alpine:3.20`) so the trust surface is small
and the cache hits the docker layer cache every rebuild.

Nothing in this image executes content from the cloned repo. It only reads
files, hashes bytes, and writes a tar. If you find yourself wanting to add
a Python interpreter, a build tool, or *anything* that could run
repo-supplied code, push back — that defeats the purpose of the sandbox.

## Updating the entrypoint

Any change to `entrypoint.sh` is a security-relevant change. Update the
unit tests in `tests/unit/test_repo_extractor_paths.py` /
`test_container_wrapper.py` in the same commit and re-run the smoke test
on a known-good public repo.
