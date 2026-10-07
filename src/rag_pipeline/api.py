"""Read-only JSON API over results/*.csv, plus the built dashboard (web/dist) at /.

Dashboard pages are client-side routes: known ones get index.html with 200, anything else gets
index.html with 404 so the app renders its own not-found page and crawlers see a real 404.

Run: uvicorn rag_pipeline.api:app --reload
"""
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from rag_pipeline import results
from rag_pipeline.config import ROOT

WEB_DIST = ROOT / "web" / "dist"
N_BUCKETS = 10
PAGES = {"", "frontier", "questions", "privacy", "terms"}

app = FastAPI(title="RAG decision pipeline explorer")


@lru_cache
def data() -> dict[str, pd.DataFrame]:
    return results.load()


def records(df: pd.DataFrame) -> list[dict]:
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/summary")
def summary() -> dict:
    s = data()["summary"]
    pop_t, conf_t = results.chosen_thresholds(s)
    return {"model": s["model"].iloc[0], "pop_threshold": pop_t, "conf_threshold": conf_t,
            "runs": records(s.drop(columns=["run_id", "model", "pop_threshold", "conf_threshold"]))}


@app.get("/api/frontier")
def frontier() -> dict:
    """Every threshold pair on the tune split, the Pareto subset, and the three modes."""
    d = data()
    modes = d["summary"][d["summary"]["split"] == "tune"]
    return {"grid": records(d["grid"]), "pareto": records(d["pareto"]),
            "modes": records(modes[["mode", "accuracy", "retrieval_rate", "pop_threshold", "conf_threshold"]])}


@app.get("/api/by-popularity")
def by_popularity(split: str = "test") -> list[dict]:
    """Accuracy per mode in each popularity decile (deciles cut over all 1,000 questions)."""
    p = data()["predictions"].copy()
    p["bucket"] = pd.qcut(np.log10(p["s_pop"] + 1), N_BUCKETS, labels=False)
    edges = p.groupby("bucket")["s_pop"].agg(["min", "max"])
    if split != "all":
        p = p[p["split"] == split]
    acc = p.groupby("bucket")[[f"{m}_correct" for m in results.MODES]].mean()
    acc.columns = results.MODES
    return records(edges.join(acc).join(p.groupby("bucket").size().rename("n")).reset_index())


@app.get("/api/questions")
def questions() -> list[dict]:
    """Every question with each mode's answer nested; small enough to filter in the browser."""
    p = data()["predictions"]
    base = p[["question_id", "question", "prop", "s_pop", "answers", "split"]]
    out = records(base)
    for mode in results.MODES:
        m = p[[f"{mode}_{f}" for f in results.MODE_FIELDS]].copy()
        m.columns = results.MODE_FIELDS
        m["verdict"] = results.verdict(m)
        for row, rec in zip(out, records(m)):
            row[mode] = rec
    return out


@app.get("/{path:path}", include_in_schema=False)
def web(path: str) -> FileResponse:
    if path.startswith("api/"):
        raise HTTPException(404, "Unknown API endpoint")
    dist = WEB_DIST.resolve()
    index = dist / "index.html"
    if not index.exists():
        raise HTTPException(404, "Dashboard not built: run `npm run build` in web/")
    file = (dist / path).resolve()
    if path and file.is_file() and file.is_relative_to(dist):
        # Vite fingerprints everything under assets/, so it can be cached forever.
        cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
        return FileResponse(file, headers={"Cache-Control": cache})
    status = 200 if path.strip("/") in PAGES else 404
    return FileResponse(index, status_code=status, headers={"Cache-Control": "no-cache"})
