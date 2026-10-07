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


@pytest.fixture
def dist(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log(1)")
    monkeypatch.setattr("rag_pipeline.api.WEB_DIST", tmp_path)
    return tmp_path


@pytest.mark.parametrize("path", ["/", "/frontier", "/questions", "/privacy", "/terms"])
def test_pages_serve_app(dist, path):
    r = client.get(path)
    assert r.status_code == 200 and "root" in r.text


def test_unknown_page_serves_app_with_404(dist):
    r = client.get("/no-such-page")
    assert r.status_code == 404 and "root" in r.text


def test_unknown_api_is_json_404(dist):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["detail"] == "Unknown API endpoint"


def test_assets_are_cached_and_traversal_blocked(dist):
    r = client.get("/assets/app-abc123.js")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    assert client.get("/..%2F..%2Fpyproject.toml").status_code == 404
