---
name: phase-8-2-persistent-index
title: "Phase 8.2 — Persistent index"
phase: 8
status: done
created_at: 2026-06-17
updated_at: 2026-06-17
completed_at: 2026-06-17
supersedes: []
superseded_by:
related: [phase-8-web-command-center]
locked_decisions:
  - "SQLite is the default storage and the cloud target is Postgres. Both share one SQLAlchemy schema; the connection string is the only thing that switches between them. Alembic migrations target both dialects (no SQLite-only column types, no Postgres-only DDL in migrations without a dialect guard)."
  - "The SQLite file lives at `web/.data/index.sqlite` (gitignored). It is not in the repo root, not under `/tmp`, not under `/scout/state/`. The path is overridable via `AUTOCLAUDE_INDEX_DSN`."
  - "Sync triggers in 8.2: manual `autoclaude-index sync` CLI + `POST /sync` HTTP + a polling reconciler every 60s while the API is up. A real file watcher (`watchfiles`) lands in 8.3, not here."
  - "Indexer dataclasses (`AssetRecord`, `IndexSnapshot`) stay pure — they're the domain shape. SQLAlchemy models live next to the storage code (`web/apps/api/db/`). Conversion is a one-way function `AssetRecord -> ORM row` plus its inverse for reads. We do NOT unify into SQLModel."
  - "Thread JSONL files stay file-backed in 8.2 (the threads router reads them directly through `index.repo_root`). They are not mirrored into the DB; a dedicated `thread_event` table arrives in 8.4 when SSE needs incremental access. The 8.2 DB stores asset records only."
  - "Pydantic API models stay untouched. The wire format is the contract; the DB is an implementation detail. Tests pin the wire shape and would fail if the DB swap leaked through."
  - "Sync is idempotent. Running `autoclaude-index sync` twice in a row on an unchanged repo produces zero row writes. Upserts compare a content hash; only changed rows are written."
  - "Sync is crash-safe. A kill mid-sync leaves the DB in a recoverable state: the next sync converges to the correct snapshot. We do not require an in-flight transaction to complete; we require that the next sync produces the right result."
  - "CachedIndex's interface is preserved. Routers do not learn the word 'session' or 'engine'. The DB swap happens *behind* `CachedIndex.get()` and `CachedIndex.force_rebuild()`."
  - "The asset PK is `path`, not `(bucket, slug)`. The repo's 33 unnamed README.md files all fall back to slug='readme' under the 8.1 indexer; a composite-slug PK would collide on real content. `(bucket, slug)` survives as a non-unique composite index, so `GET /<bucket>/{slug}` still hits an index — it just picks first-seen on slug collisions, matching 8.1's `by_slug()` semantics. Discovered during 8.2 implementation."
  - "Sync runs under a process-wide `threading.Lock`. The reconciler and manual `autoclaude-index sync` both write to the same DB; serialising them avoids interleaved read-modify-write transactions producing unique-constraint failures. Discovered during 8.2 smoke."
  - "`AUTOCLAUDE_INDEX_AUTO_MIGRATE` defaults to `1`. `uv run autoclaude-api` on a fresh checkout creates the DB + applies migrations + drives the initial sync without any manual setup. Production / CI sets it to `0` to keep migrations as an explicit deploy step."
---

# Phase 8.2 — Persistent index

## Goal

Replace the in-memory `CachedIndex` from 8.1 with a SQLite-backed (default) /
Postgres-compatible (cloud) index that survives process restarts, supports
multi-process serving, and gives 8.3 (write-back) a real persistence layer for
the audit log it needs.

The 8.1 indexer (`Indexer.scan()` walking the repo and producing
`AssetRecord`s) stays. What changes is where the snapshot is held: instead of
keeping the list of records in a Python dict in one process, we drain it into
a relational schema that lives on disk. Routers continue to call
`CachedIndex.get()`; the call now reads rows from a session instead of
returning an in-memory list.

The success criterion is invisibility: an operator who hits the same surfaces
they hit in 8.1 sees identical results. The difference is that they can also:

- Restart the API and not pay a cold-walk penalty.
- Run multiple uvicorn workers without each one walking the repo independently.
- Run the rollup-style queries 8.3 / 8.6 will need (joins, aggregates, indexes
  on `bucket`, `slug`, `updated_at`) without slurping everything into memory.

## Non-goals (out of scope for this milestone)

- **Write-back to markdown.** The DB is read-only relative to the repo. Writes
  happen in 8.3 via the editor + git commit pipeline.
- **A real file watcher.** `watchfiles` / inotify lands in 8.3 when same-machine
  writes need to invalidate quickly. 8.2 uses a 60-second polling reconciler.
- **Vector / full-text search.** `pgvector` and the LLM-backed search are 8.6.
  v1 search remains the substring scan from 8.1.
- **Multiple repos in one DB.** The index is scoped to a single
  `AUTOCLAUDE_REPO_ROOT`. Sharding across repos is a future concern.
- **Migration tooling beyond Alembic.** No `aerich`, no `yoyo`, no custom DSL.
- **Schema changes to `AssetRecord`.** The DB rows mirror the record shape;
  expanding the schema is its own change (and starts in
  `/catalog/_schema/asset.schema.md` per the maintenance process).

## Constraints (inherited and new)

Inherited from Phase 8:

- **Markdown is canonical.** Deleting `web/.data/index.sqlite` and running
  `autoclaude-index sync` must restore full functionality. The DB is derived.
- **Routers do no I/O.** Storage stays behind `CachedIndex`. Routers receive a
  snapshot-shaped view, not a session.
- **API surface is typed.** Pydantic models are unchanged.
- **Schema flows from the catalog.** Adding a column starts in
  `/catalog/_schema/asset.schema.md` and `/conventions/frontmatter.md`.

New for 8.2:

- **One schema, two dialects.** Anything that can't migrate cleanly to Postgres
  doesn't ship. We use SQLAlchemy's `JSON` type (which becomes `JSONB`-ish on
  Postgres and `TEXT` on SQLite under the hood) for blob fields, ISO strings
  for dates (not native `DATE` — frontmatter dates are strings on the wire),
  and `FLOAT` for `mtime`.
- **Determinism.** Two `autoclaude-index sync` runs on the same repo produce
  identical row contents. Upserts compare a content hash; no-op runs write
  zero rows.

## Design

### 1. Storage layout

```
web/
  .data/                       gitignored. v1 only contains index.sqlite.
    index.sqlite               default SQLite file. Created on first sync.
  apps/api/
    db/                        new for 8.2
      __init__.py              re-exports the public surface
      models.py                SQLAlchemy ORM models (Asset, IndexMeta)
      session.py               engine + sessionmaker factory; DSN resolution
      sync.py                  Indexer.scan() -> upsert into DB
      query.py                 ORM-backed read API (returns AssetRecord)
  migrations/                  new for 8.2 — Alembic env
    env.py
    script.py.mako
    versions/
      0001_initial.py          creates asset, index_meta
    alembic.ini                migration config; reads DSN from env
```

The Alembic config lives under `/web/migrations/` (not `/migrations/`) so it
stays scoped to the web app. The `alembic.ini` path is configured into
`autoclaude-index`'s entry point.

### 2. Schema (initial revision `0001`)

```python
# web/apps/api/db/models.py (sketch)

class Asset(Base):
    __tablename__ = "asset"

    # Primary key is `path`. See "Why `path` not `(bucket, slug)`" below.
    path = Column(String(1024), primary_key=True)

    bucket = Column(String(32), nullable=False)
    slug = Column(String(255), nullable=False)
    kind = Column(String(64), nullable=True, index=True)
    title = Column(String(512), nullable=True)
    status = Column(String(32), nullable=True, index=True)
    quality = Column(Integer, nullable=True)

    tags = Column(JSON, nullable=False, default=list)
    source = Column(JSON, nullable=True)
    discovered = Column(JSON, nullable=True)
    relations = Column(JSON, nullable=True)
    issues = Column(JSON, nullable=False, default=list)

    created_at = Column(String(10), nullable=True)   # ISO YYYY-MM-DD on the wire
    updated_at = Column(String(10), nullable=True, index=True)
    mtime = Column(Float, nullable=False)
    body = Column(Text, nullable=False, default="")

    # Sync hygiene
    content_hash = Column(String(64), nullable=False, index=True)
    sync_run_id = Column(String(64), nullable=False, index=True)


class IndexMeta(Base):
    """Single-row table with sync state."""

    __tablename__ = "index_meta"

    id = Column(Integer, primary_key=True)            # always 1
    repo_root = Column(String(1024), nullable=False)
    last_sync_at = Column(Float, nullable=False)      # epoch seconds
    last_sync_run_id = Column(String(64), nullable=False)
    last_sync_record_count = Column(Integer, nullable=False, default=0)
    schema_version = Column(String(16), nullable=False)  # matches Alembic head
```

Why `path` not `(bucket, slug)`:

- An earlier draft of this plan picked `(bucket, slug)` as the composite
  primary key. Implementation surfaced a problem: the 8.1 indexer falls
  back to `slug='readme'` when a README.md lacks an explicit `name:` field,
  and the repo has 33 such READMEs — they collide on every `(bucket, slug)`
  PK.
- `path` is the natural unique identifier: the filesystem guarantees one
  record per path, and `Indexer.scan()` never emits two records for the
  same file. Picking it as the PK matches reality without contorting the
  indexer or fabricating synthetic slugs.
- `(bucket, slug)` becomes a non-unique composite index. The most common
  lookup pattern (`GET /<bucket>/{slug}`) still hits the index; on slug
  collision the route picks first-seen, matching 8.1's `by_slug()` semantics.

Schema versioning: `IndexMeta.schema_version` is compared at startup to
Alembic's head revision. A mismatch is a hard error with a clear message
("run `autoclaude-index upgrade`"). 8.2 ships with revision `0001`.

### 3. Sync engine

```python
# web/apps/api/db/sync.py (sketch)

def sync(
    indexer: Indexer,
    session_factory: sessionmaker,
    *,
    run_id: str | None = None,
) -> SyncResult:
    """Walk the repo, diff against the DB, upsert changed rows.

    Idempotent: a no-op run produces zero writes. Crash-safe: a partial run
    leaves stale rows from the previous sync_run_id in place — they get
    swept on the next sync's reconciliation pass.
    """
    snapshot = indexer.scan()
    run_id = run_id or _new_run_id()

    with session_factory() as session, session.begin():
        # 1. Upsert asset rows. Compute content_hash per record; only write
        #    rows whose hash changed.
        existing = _existing_assets_by_pk(session)
        for record in snapshot.records:
            new_hash = _hash_record(record)
            pk = (record.bucket, record.slug_for_pk())
            current = existing.get(pk)
            if current and current.content_hash == new_hash:
                # No-op: stamp sync_run_id so reconciliation knows this row
                # is current. Single column update; cheap.
                current.sync_run_id = run_id
                continue
            _upsert_asset(session, record, new_hash, run_id)

        # 2. Reconciliation pass: any asset row whose sync_run_id is older
        #    than this run was either deleted from the repo or moved buckets.
        #    Delete it.
        _delete_stale(session, run_id)

        # 3. Bump IndexMeta.
        _stamp_meta(session, snapshot, run_id)

    return SyncResult(
        run_id=run_id,
        records=len(snapshot.records),
        rows_written=...,
        rows_deleted=...,
    )
```

Idempotency proof: the `content_hash` is computed from the same record fields
that the router would serialize. Two scans of the same filesystem produce
identical hashes; rows whose hash matches the existing row's hash skip the
write and only bump `sync_run_id`. A second invocation with no changes writes
zero data columns; only the lightweight `sync_run_id` stamp moves.

Crash-safety proof: rows the sync was about to delete (because their files
were removed) stay in the DB until the next successful sync. They show up to
readers as ghost entries with a previous `sync_run_id`. The reconciliation
pass on the next sync removes them. A reader catching a ghost between syncs
is not worse than the in-memory behavior of 8.1 — the cache there is also
populated from a snapshot that lags reality by up to the polling interval.

The `_hash_record` function takes everything that ends up on the wire
(`path`, `kind`, `title`, `status`, `quality`, `tags`, `source`, `discovered`,
`relations`, `issues`, `created_at`, `updated_at`, `body`). It does not hash
`mtime` — mtime alone changing without content changing (e.g. `touch`) should
NOT cause a write. This matches the 8.1 watch-dir cache's intent.

### 4. Polling reconciler

When the FastAPI app is up, a background coroutine wakes every 60 seconds and
calls `sync()`. The reconciler is a thin wrapper around the same sync engine
the CLI uses. It is started in the FastAPI lifespan handler and cancelled on
shutdown.

```python
# web/apps/api/main.py (excerpt of the lifespan change)
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_reconciler_loop(cfg))
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
```

The reconciler is best-effort. Sync errors are logged and the loop continues.
The interval is `AUTOCLAUDE_INDEX_RECONCILE_INTERVAL` (default 60).
Setting it to `0` disables the loop entirely (useful in tests).

### 5. CachedIndex stays, swaps backing store

```python
# web/apps/api/cache.py (sketch after 8.2)

class CachedIndex:
    """Same public interface as 8.1. Now reads from the DB instead of an
    in-process snapshot."""

    def __init__(self, repo_root: Path, session_factory) -> None:
        self._repo_root = repo_root
        self._session_factory = session_factory

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    def get(self) -> IndexSnapshot:
        """Materialise a snapshot from the DB. Cheap — single query + iter."""
        with self._session_factory() as session:
            rows = session.execute(select(Asset).order_by(Asset.path)).scalars().all()
            records = [_row_to_record(r) for r in rows]
            meta = session.get(IndexMeta, 1)
            return IndexSnapshot(
                records=records,
                scan_mtime_ceiling=meta.last_sync_at if meta else 0.0,
                repo_root=self._repo_root.as_posix(),
            )

    def force_rebuild(self) -> IndexSnapshot:
        sync(Indexer(self._repo_root), self._session_factory)
        return self.get()
```

The routers (and `routers/_filters.py`) keep using `IndexSnapshot`. The only
change visible from the router side: `get()` no longer caches in-process. We
rely on the DB to be fast enough that a per-request query is acceptable for
the page sizes we render.

If profiling shows the per-request materialise is too expensive, we add a
short-lived in-process cache keyed off `IndexMeta.last_sync_at` — but we
don't add it speculatively.

### 6. CLI: `autoclaude-index`

```sh
uv run autoclaude-index sync              # walks repo, drains into DB
uv run autoclaude-index sync --verbose    # log each upsert
uv run autoclaude-index status            # prints IndexMeta + counts
uv run autoclaude-index upgrade           # alembic upgrade head
uv run autoclaude-index reset             # drop tables, run migrations, re-sync
```

The entry point is `tools/index.py:main`. It is exposed via
`[project.scripts]` in `pyproject.toml`.

`reset` is destructive and prompts unless `--yes` is passed.

### 7. Config

New env vars (documented in the runbook):

| Var                                       | Default                              | What it controls                                |
| ----------------------------------------- | ------------------------------------ | ----------------------------------------------- |
| `AUTOCLAUDE_INDEX_DSN`                    | `sqlite:///web/.data/index.sqlite`   | SQLAlchemy connection string                    |
| `AUTOCLAUDE_INDEX_RECONCILE_INTERVAL`     | `60`                                 | seconds between reconciler runs; `0` disables    |
| `AUTOCLAUDE_INDEX_AUTO_MIGRATE`           | `1`                                  | if `1`, API runs `alembic upgrade head` on boot. Default ON so `uv run autoclaude-api` works on a fresh checkout; production / CI sets `0` to make migrations an explicit deploy step. |

DSN resolution: if `AUTOCLAUDE_INDEX_DSN` is unset and the default SQLite
path's parent directory doesn't exist, we create it. The path is resolved
relative to `AUTOCLAUDE_REPO_ROOT`, not the CWD.

### 8. Test surface

New tests:

```
tests/unit/web/
  test_db_sync.py             single-record upserts, hash-stable no-op,
                              delete-stale, ghost-row tolerance
  test_db_query.py            ORM -> AssetRecord round-trip
  test_db_session.py          DSN resolution, default SQLite path creation
  test_index_cli.py           argparse surface, status/sync/reset exit codes

tests/integration/web/
  test_persistent_index.py    end-to-end: create temp repo, sync, read via
                              CachedIndex, mutate file, sync again, see diff
  test_idempotency.py         sync twice on unchanged repo -> zero row writes
                              on the second call (assert via SyncResult)
  test_alembic_upgrade.py     fresh DB -> alembic upgrade head -> sync works
```

Existing tests adapt minimally: the `client` fixture now wires a per-test
SQLite file (under `tmp_path`) and runs an initial sync before the first
request. Tests that mutate the fixture repo call `POST /sync` (existing
endpoint, unchanged URL) to re-converge.

### 9. Failure modes & required handling

| Failure                                                | Action                                                                  |
| ------------------------------------------------------ | ----------------------------------------------------------------------- |
| DB file missing on API boot                            | Auto-create via migrations if `AUTOCLAUDE_INDEX_AUTO_MIGRATE=1`; else clear startup error pointing at `autoclaude-index upgrade` |
| Schema version mismatch                                | Hard error; refuse to serve; runbook explains `autoclaude-index upgrade` |
| Sync raises on a single record                         | Log + skip that record (record path in error); rest of sync continues; sync returns `success=False`; reconciler logs but continues looping |
| DB locked (SQLite, concurrent sync + reconciler)       | Reconciler holds advisory lock (`IndexMeta` row update with `with_for_update` on Postgres, SQLite naturally serializes); on contention, second waiter logs + skips that tick |
| `web/.data/` directory not writable                    | Sync fails with a clear "permissions" error; suggested fix in runbook    |
| Repo root changed since last sync                      | First sync detects `IndexMeta.repo_root` mismatch; logs warning; truncates the asset table and starts fresh |

### 10. Migration safety on Postgres

The 8.5 cloud deploy will run the same Alembic migrations against Postgres.
Constraints we enforce on every migration:

- **No SQLite-only column types.** No `BLOB`, no `JSON1`-extension types. Use
  SQLAlchemy's `JSON` / `Text` / `String(n)` / `Integer` / `Float`.
- **No Postgres-only DDL without dialect guards.** If a migration needs
  `CREATE INDEX ... USING gin`, gate it on `op.get_bind().dialect.name`.
- **Migrations are reversible.** `downgrade()` is implemented and tested in
  `test_alembic_upgrade.py`.
- **No data backfills in DDL migrations.** Data conversions live in separate
  data-migration steps so DDL can roll back cleanly.

## Resolved open questions

The session prompt named four open questions. Their resolutions:

**Q1. SQLite-only for 8.2, or SQLite-default-with-Postgres-via-DSN?**
SQLite-default-with-Postgres-via-DSN. Same schema for both, default DSN is
SQLite, override via `AUTOCLAUDE_INDEX_DSN`. Migrations cover both dialects.
Rationale: writing the schema dialect-portable now is cheap; rewriting it for
8.5 cloud deploy after we've written 8.3 write-back against a SQLite-only
schema would be expensive.

**Q2. Where does the SQLite file live?**
`web/.data/index.sqlite`. Gitignored. Overridable via `AUTOCLAUDE_INDEX_DSN`.
Rationale: it's web-app state; it belongs under `/web/`. Not in the repo
root, not under `/scout/state/` (that's scout-pipeline state with a different
lifecycle).

**Q3. Sync triggers: manual only, or also a file watcher?**
Manual `autoclaude-index sync` + `POST /sync` + a 60s polling reconciler.
No `watchfiles` watcher until 8.3. Rationale: a watcher is the right answer
once writes happen on the same machine and we need sub-second invalidation;
in 8.2 the writes still happen out-of-band (editor + git commit) and a 60s
reconcile is well within operator tolerance.

**Q4. Schema versioning: keep indexer dataclasses + add SQLAlchemy models, or
unify into SQLModel?**
Keep them separate. `AssetRecord` is the domain shape; SQLAlchemy models are
storage. The conversion lives in `web/apps/api/db/sync.py` and `query.py`.
Rationale: SQLModel couples the two and makes both harder to change
independently. The catalog-schema-first maintenance process from Phase 8
already requires schema changes to flow `_schema → models → wire → UI`; a
storage layer inserted between `_schema` and `models` is one more thing
that has to move when the schema does.

## Task breakdown

| #  | Task                                                                                          | Notes                                |
| -- | --------------------------------------------------------------------------------------------- | ------------------------------------ |
| 1  | Add SQLAlchemy + Alembic to pyproject `web` group + `dev` group. Add `aiosqlite` for async.   | Bump uv.lock.                        |
| 2  | Land `web/apps/api/db/models.py` (Asset, ThreadDay, IndexMeta).                                |                                      |
| 3  | Land `web/apps/api/db/session.py` (engine, sessionmaker, DSN resolution).                      |                                      |
| 4  | Land `web/migrations/` (alembic.ini, env.py, script.py.mako, 0001 initial).                    | Migrations target both dialects.     |
| 5  | Land `web/apps/api/db/sync.py` (hash-based upsert, reconciliation pass).                       |                                      |
| 6  | Land `web/apps/api/db/query.py` (ORM → AssetRecord).                                           |                                      |
| 7  | Refactor `web/apps/api/cache.py` so `CachedIndex` reads from the DB. Preserve interface.       | Routers don't change.                |
| 8  | Add polling reconciler in FastAPI lifespan. Honor `AUTOCLAUDE_INDEX_RECONCILE_INTERVAL`.       |                                      |
| 9  | Add `tools/index.py` + `autoclaude-index` console script: `sync`, `status`, `upgrade`, `reset`.|                                      |
| 10 | Update `web/apps/api/settings.py` to surface the new env vars.                                 |                                      |
| 11 | Update `web/apps/api/routers/stats.py` to surface DB snapshot mtime correctly.                 | `snapshot_mtime` = `last_sync_at`.   |
| 12 | Unit tests: `test_db_sync.py`, `test_db_query.py`, `test_db_session.py`, `test_index_cli.py`.  |                                      |
| 13 | Integration tests: `test_persistent_index.py`, `test_idempotency.py`, `test_alembic_upgrade.py`.| Per-test SQLite under `tmp_path`.    |
| 14 | Adapt existing `tests/integration/web/conftest.py` to bootstrap the DB before serving.         | Run migrations + initial sync.       |
| 15 | Update `/conventions/web-app.md` § "Routers do not do I/O" with DB clause.                     |                                      |
| 16 | Update `/command-center/runbooks/web-app.md` with new env vars + `autoclaude-index` section.   | Bump `last_verified`.                |
| 17 | Update `.gitignore` to exclude `web/.data/`.                                                    |                                      |
| 18 | Update `CLAUDE.md` to mention `autoclaude-index sync` in the commands section.                 |                                      |
| 19 | Quality gate: ruff, pytest, integration. Manual: `autoclaude-index sync` twice + sqlite count.  |                                      |
| 20 | Commit as one logical change. Mark this plan `status: done`, set `completed_at`.                |                                      |

## Quality gate (must all pass before commit)

```sh
uv run ruff check scout/ web/ tests/
uv run pytest -q
uv run pytest tests/integration -q
uv run pytest tests/unit/web tests/integration/web -q

# Smoke (manual)
uv run autoclaude-index upgrade           # alembic head; creates web/.data/index.sqlite
uv run autoclaude-index sync              # first sync; rows written > 0
uv run autoclaude-index sync              # second sync; rows_written == 0
sqlite3 web/.data/index.sqlite "select count(*) from asset"   # > 0

AUTOCLAUDE_API_PORT=8000 uv run autoclaude-api &
curl -s http://localhost:8000/health | jq .records      # > 0
curl -s -X POST http://localhost:8000/sync | jq .stats.total
kill %1
```

## Idempotency check (REQUIRED for 8.2)

Two `autoclaude-index sync` invocations in a row on an unchanged repo must
produce `rows_written == 0` on the second call. Asserted in
`test_idempotency.py`. The smoke section reproduces it manually.

Crash recovery is verified by `test_persistent_index.py`:

1. Start a sync.
2. Simulate a crash mid-sync (raise inside the session).
3. Run a clean sync afterwards.
4. Assert the DB matches the on-disk state.

## Commit message (template)

```
Phase 8.2: web command center — persistent index

- web/apps/api/db: SQLAlchemy models (Asset, ThreadDay, IndexMeta),
  session/engine factory, hash-based idempotent sync engine,
  ORM -> AssetRecord query layer.
- web/migrations: Alembic 0001 initial schema. SQLite default;
  Postgres-compatible (no dialect-only types or DDL).
- tools/index.py + `autoclaude-index` script: sync / status / upgrade
  / reset subcommands. `sync` is idempotent and crash-safe.
- web/apps/api/cache.py: CachedIndex now reads from the DB. Routers
  unchanged.
- web/apps/api/main.py: lifespan-driven 60s polling reconciler.
- web/apps/api/settings.py: AUTOCLAUDE_INDEX_DSN,
  AUTOCLAUDE_INDEX_RECONCILE_INTERVAL, AUTOCLAUDE_INDEX_AUTO_MIGRATE.
- Tests: unit (sync, query, session, CLI) + integration (persistence,
  idempotency, alembic upgrade).
- conventions/web-app.md, command-center/runbooks/web-app.md,
  CLAUDE.md, .gitignore: updated.
- docs/plans/phase-8-2-persistent-index.md: status -> done.
```

## When this plan becomes stale

Status flips to `done` when the 8.2 commit lands. If a later milestone
fundamentally changes how persistence works (e.g. dropping SQLAlchemy for
a different ORM, swapping SQLite for DuckDB), that milestone gets a new
plan that `supersedes: [phase-8-2-persistent-index]`. Until then this is
the authoritative design for the persistent index layer.
