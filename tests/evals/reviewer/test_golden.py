"""Eval test: run the reviewer against the golden set.

Requires a real ANTHROPIC_API_KEY. Gate: only runs when RUN_REVIEWER_EVALS=1.

Gates (per-class; only enforced when >= 5 labeled samples):
  discard precision >= 0.95
  keep    precision >= 0.85
  keep    recall    >= 0.70
  Brier score       <= 0.20
"""

import os

import pytest

RUN_EVALS = os.environ.get("RUN_REVIEWER_EVALS", "") == "1"


@pytest.mark.skipif(not RUN_EVALS, reason="Set RUN_REVIEWER_EVALS=1 to run")
def test_golden_set_gates():

    import anthropic

    from scout._util import parse_frontmatter
    from scout.reviewer.agent import review_candidate
    from scout.reviewer.context import get_context
    from scout.reviewer.eval import EvalResult, _load_golden

    golden = _load_golden()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    assert api_key, "ANTHROPIC_API_KEY must be set for eval tests"

    client = anthropic.Anthropic(api_key=api_key)
    result = EvalResult()

    from pathlib import Path
    REPO_ROOT = Path(__file__).resolve().parents[4]

    for item in golden:
        slug = item["candidate_slug"]
        candidate_path = item.get("candidate_path", f"scout/queue/{slug}.md")
        expected_action = item["expected_action"]

        full_path = REPO_ROOT / candidate_path
        if not full_path.exists():
            result.skipped.append(slug)
            continue

        from scout.reviewer.context import _split_body
        text = full_path.read_text()
        fm = parse_frontmatter(text)
        body = _split_body(text)
        tags = fm.get("tags") or []
        title = fm.get("title") or slug
        context_items = get_context(title, tags)

        from scout.reviewer.agent import make_candidate_text
        candidate_text = make_candidate_text(slug, fm, body)

        try:
            decision, usage, model_used = review_candidate(
                client=client,
                candidate_text=candidate_text,
                context_items=context_items,
            )
            result.add_prediction(expected_action, decision.action, decision.confidence)
        except Exception as exc:
            result.errors.append({"slug": slug, "error": str(exc)})

    print("\n" + result.render())

    passes, failures = result.passes_gates()
    assert passes, "Eval gate failures:\n" + "\n".join(f"  - {f}" for f in failures)
