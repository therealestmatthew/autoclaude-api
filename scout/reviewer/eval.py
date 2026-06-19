"""Eval harness for the reviewer agent.

Loads golden.jsonl, runs the reviewer against each item (with proposal POST
mocked), and scores action-match per class. Gates:

  discard precision >= 0.95   (false-discard is recoverable; 5% annoyance)
  keep    precision >= 0.85   (false-keep pollutes catalog forever)
  keep    recall    >= 0.70   (false-discard of a real asset is hard to recover)
  Brier score       <= 0.20   (high-confidence wrongs are worse)

Merge precision is reported but NOT gated until the golden set has >= 10 labeled
merge examples (catalog is too thin for clean merges in v0).

Run via:
  uv run scout review --evals
  RUN_REVIEWER_EVALS=1 uv run pytest tests/evals/reviewer/ -q
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .._util import parse_frontmatter
from .agent import ReviewerError, make_candidate_text, review_candidate
from .context import _split_body, get_context

REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN_PATH = Path(__file__).resolve().parent / "evals" / "golden.jsonl"
_QUEUE_DIR = REPO_ROOT / "scout" / "queue"

_MERGE_GATE_MIN_SAMPLES = 10


@dataclass
class EvalResult:
    total: int = 0
    correct: int = 0

    # Per-class tallies: {action: {tp, fp, fn}}
    class_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    brier_sum: float = 0.0
    brier_n: int = 0

    skipped: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def add_prediction(
        self,
        expected: str,
        predicted: str,
        confidence: float,
    ) -> None:
        self.total += 1
        correct = expected == predicted
        if correct:
            self.correct += 1

        # Per-class TP/FP/FN
        for cls in ("keep", "merge", "discard"):
            if cls not in self.class_stats:
                self.class_stats[cls] = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
            is_pos_pred = predicted == cls
            is_pos_true = expected == cls
            if is_pos_pred and is_pos_true:
                self.class_stats[cls]["tp"] += 1
            elif is_pos_pred and not is_pos_true:
                self.class_stats[cls]["fp"] += 1
            elif not is_pos_pred and is_pos_true:
                self.class_stats[cls]["fn"] += 1
            else:
                self.class_stats[cls]["tn"] += 1

        # Brier score contribution: (conf_correct - 1)^2 for correct, (conf_wrong)^2 for wrong
        # Using the calibration-aware variant: MSE of P(correct class) vs 1.
        p_correct = confidence if correct else (1.0 - confidence)
        self.brier_sum += (p_correct - 1.0) ** 2
        self.brier_n += 1

    def precision(self, cls: str) -> float | None:
        s = self.class_stats.get(cls, {})
        tp = s.get("tp", 0)
        fp = s.get("fp", 0)
        return tp / (tp + fp) if (tp + fp) > 0 else None

    def recall(self, cls: str) -> float | None:
        s = self.class_stats.get(cls, {})
        tp = s.get("tp", 0)
        fn = s.get("fn", 0)
        return tp / (tp + fn) if (tp + fn) > 0 else None

    def brier_score(self) -> float | None:
        return self.brier_sum / self.brier_n if self.brier_n > 0 else None

    def action_match(self) -> float | None:
        return self.correct / self.total if self.total > 0 else None

    def sample_count(self, cls: str) -> int:
        s = self.class_stats.get(cls, {})
        return s.get("tp", 0) + s.get("fn", 0)  # true positives = TP + FN

    def passes_gates(self) -> tuple[bool, list[str]]:
        """Return (passes, list_of_failures)."""
        failures = []

        discard_p = self.precision("discard")
        if discard_p is not None and self.sample_count("discard") >= 5 and discard_p < 0.95:
            failures.append(f"discard precision {discard_p:.2f} < 0.95")

        keep_p = self.precision("keep")
        if keep_p is not None and self.sample_count("keep") >= 5 and keep_p < 0.85:
            failures.append(f"keep precision {keep_p:.2f} < 0.85")

        keep_r = self.recall("keep")
        if keep_r is not None and self.sample_count("keep") >= 5 and keep_r < 0.70:
            failures.append(f"keep recall {keep_r:.2f} < 0.70")

        brier = self.brier_score()
        if brier is not None and self.brier_n >= 5 and brier > 0.20:
            failures.append(f"Brier score {brier:.3f} > 0.20")

        merge_p = self.precision("merge")
        n_merge = self.sample_count("merge")
        if n_merge >= _MERGE_GATE_MIN_SAMPLES and merge_p is not None and merge_p < 0.70:
            failures.append(
                f"merge precision {merge_p:.2f} < 0.70"
                f" (gate active at >= {_MERGE_GATE_MIN_SAMPLES} samples)"
            )

        return (len(failures) == 0, failures)

    def render(self) -> str:
        n_skip = len(self.skipped)
        n_err = len(self.errors)
        am = self.action_match()
        lines = [
            f"Eval results — {self.total} items ({n_skip} skipped, {n_err} errors)",
            f"  action match:      {am:.2%}" if am is not None else "  action match:      n/a",
        ]
        for cls in ("keep", "merge", "discard"):
            p = self.precision(cls)
            r = self.recall(cls)
            n = self.sample_count(cls)
            gate_note = " [GATE]" if n >= 5 else f" [report-only, n={n}]"
            p_str = f"{p:.2%}" if p is not None else "n/a"
            r_str = f"{r:.2%}" if r is not None else "n/a"
            lines.append(f"  {cls:<8} precision={p_str} recall={r_str}{gate_note}")
        brier = self.brier_score()
        brier_str = (
            f"  Brier score:       {brier:.3f}" if brier is not None else "  Brier score:       n/a"
        )
        lines.append(brier_str)

        passes, failures = self.passes_gates()
        if passes:
            lines.append("\n  ✓ All gates passed.")
        else:
            lines.append("\n  ✗ Gate failures:")
            for f in failures:
                lines.append(f"    - {f}")
        return "\n".join(lines)


def _load_golden() -> list[dict]:
    if not _GOLDEN_PATH.exists():
        raise FileNotFoundError(f"golden set not found: {_GOLDEN_PATH}")
    items = []
    for line in _GOLDEN_PATH.read_text().splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def _load_candidate(candidate_path: str) -> tuple[dict, str] | None:
    """Load frontmatter + body from a queue candidate path."""
    full_path = REPO_ROOT / candidate_path
    if not full_path.exists():
        return None
    text = full_path.read_text()
    fm = parse_frontmatter(text)
    body = _split_body(text)
    return fm, body


def run_evals(verbose: bool = False) -> int:
    """Run the eval harness. Returns 0 if all gates pass, 1 otherwise."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Evals require real API calls.\n"
            "Set RUN_REVIEWER_EVALS=1 and ANTHROPIC_API_KEY=... to run."
        )

    golden = _load_golden()
    client = anthropic.Anthropic(api_key=api_key)
    result = EvalResult()

    for item in golden:
        slug = item["candidate_slug"]
        candidate_path = item.get("candidate_path", f"scout/queue/{slug}.md")
        expected_action = item["expected_action"]

        loaded = _load_candidate(candidate_path)
        if loaded is None:
            if verbose:
                print(f"  skip {slug}: candidate file not found")
            result.skipped.append(slug)
            continue

        fm, body = loaded
        tags = fm.get("tags") or []
        title = fm.get("title") or slug
        context_items = get_context(title, tags)
        candidate_text = make_candidate_text(slug, fm, body)

        try:
            decision, usage, model_used = review_candidate(
                client=client,
                candidate_text=candidate_text,
                context_items=context_items,
            )
        except ReviewerError as exc:
            result.errors.append({"slug": slug, "error": str(exc)})
            if verbose:
                print(f"  ! error on {slug}: {exc}")
            continue

        result.add_prediction(expected_action, decision.action, decision.confidence)

        if verbose:
            match_str = "✓" if decision.action == expected_action else "✗"
            print(
                f"  {match_str} {slug}: expected={expected_action} "
                f"got={decision.action} conf={decision.confidence:.2f}"
            )

    print(result.render())
    passes, _ = result.passes_gates()
    return 0 if passes else 1
