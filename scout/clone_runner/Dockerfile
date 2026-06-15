# scout-clone-runner: per-clone sandbox for the Phase 4 repo extractor.
#
# Boundary, not just hygiene. The host runs this with --network bridge for the
# clone step only, --read-only root, a 120 MB tmpfs at /work, --cap-drop ALL,
# --security-opt no-new-privileges, --pids-limit 256, and -u 65532. See
# conventions/security.md "Container flags (canonical)" for the full list.
FROM alpine:3.20

RUN apk add --no-cache git bash tar coreutils ca-certificates \
 && adduser -D -u 65532 -g '' nonroot

WORKDIR /work
USER 65532

COPY --chown=65532:65532 entrypoint.sh /usr/local/bin/entrypoint.sh

# The container only reads REPO_URL from the env. No other inputs.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
