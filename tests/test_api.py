import pandas as pd
import pytest
from fastapi.testclient import TestClient

from rag_pipeline import results
from rag_pipeline.api import app

client = TestClient(app)


def test_verdict_labels():
    df = pd.DataFrame({"correct": [True, True, False, False],
                       "correct_strict": [True, False, False, False],
                       "hallucinated": [False, False, False, True]})
    assert list(results.verdict(df)) == ["correct (both)", "lenient only", "abstained", "wrong"]


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_summary_has_every_mode_and_split():
    body = client.get("/api/summary").json()
    assert {(r["mode"], r["split"]) for r in body["runs"]} == {
        (m, s) for m in results.MODES for s in ("tune", "test", "all")}
    assert body["pop_threshold"] > 0 and 0 < body["conf_threshold"] <= 1


def test_frontier_pareto_is_subset_of_grid():
    body = client.get("/api/frontier").json()
    grid = {(r["pop_threshold"], r["conf_threshold"]) for r in body["grid"]}
    assert {(r["pop_threshold"], r["conf_threshold"]) for r in body["pareto"]} <= grid
    assert [m["mode"] for m in body["modes"]] == results.MODES


@pytest.mark.parametrize("split, n", [("test", 500), ("tune", 500), ("all", 1000)])
def test_by_popularity_covers_split(split, n):
    rows = client.get("/api/by-popularity", params={"split": split}).json()
    assert len(rows) == 10 and sum(r["n"] for r in rows) == n
    assert all(0 <= r[m] <= 1 for r in rows for m in results.MODES)


def test_questions_nest_each_mode():
    rows = client.get("/api/questions").json()
    assert len(rows) == 1000
    q = rows[0]
    assert isinstance(q["answers"], list)
    for m in results.MODES:
        assert set(q[m]) == set(results.MODE_FIELDS) | {"verdict"}
