import numpy as np
import pandas as pd

from rag_pipeline.etl import chunk_text, stratified_sample


def test_chunk_text_sizes_and_headers():
    text = "== History ==\n" + " ".join(f"w{i}" for i in range(250)) + "\n\nshort tail"
    chunks = chunk_text(text, chunk_words=100)
    assert [len(c.split()) for c in chunks] == [100, 100, 52]
    assert "==" not in " ".join(chunks)


def test_chunk_text_respects_max():
    assert len(chunk_text(" ".join(["x"] * 1000), chunk_words=10, max_chunks=5)) == 5


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_stratified_sample_covers_popularity_range():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"id": range(5000), "s_pop": (10 ** rng.uniform(0, 6, 5000)).astype(int)})
    s = stratified_sample(df, 500, seed=1)
    assert len(s) == 500
    assert s["id"].is_unique
    assert s["s_pop"].min() < 10 and s["s_pop"].max() > 100_000
    # deterministic
    assert s["id"].tolist() == stratified_sample(df, 500, seed=1)["id"].tolist()
